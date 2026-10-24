import { execFileSync, type SpawnOptions } from 'node:child_process'
import path from 'node:path'

type Platform = NodeJS.Platform

/** Runs a program and returns what it printed. Replaced in tests. */
export type Runner = (file: string, args: string[], env?: NodeJS.ProcessEnv) => string

const run: Runner = (file, args, env) =>
  execFileSync(file, args, { encoding: 'utf8', windowsHide: true, timeout: 20_000, stdio: ['ignore', 'pipe', 'ignore'], env })

/**
 * How a background program is started. On macOS and Linux it leads its own process group, so one
 * signal reaches the helpers it starts (llama-server). Windows has no process groups, and
 * `detached` there would give the program its own console window instead, so it is not set.
 */
export function spawnOptions(platform: Platform = process.platform): Pick<SpawnOptions, 'detached' | 'windowsHide'> {
  return { detached: platform !== 'win32', windowsHide: true }
}

/**
 * Stops a program and everything it started. Windows has no polite signal for a console program, so
 * the tree is ended outright with `taskkill /T /F` (documented: /T includes the child processes, /F is
 * forceful). This only finds the children while the parent is still alive, which is why the supervisor
 * stops the parent this way rather than waiting for it to exit first.
 */
export function killTree(pid: number, signal: NodeJS.Signals, platform: Platform = process.platform, exec: Runner = run): void {
  try {
    if (platform === 'win32') exec('taskkill', ['/PID', String(pid), '/T', '/F'])
    else process.kill(-pid, signal) // the program leads its own process group
  } catch {
    // already gone
  }
}

/**
 * What is running under a pid, to tell our own program from a recycled pid: the full command line on
 * macOS and Linux, only the program's file name on Windows (`tasklist` shows no more than that).
 */
export function programOf(pid: number, platform: Platform = process.platform, exec: Runner = run): string | null {
  try {
    if (platform === 'win32') {
      const line = exec('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH']).trim()
      return /^"([^"]+)"/.exec(line)?.[1] ?? null // a CSV row starts with the image name; "INFO: ..." means none
    }
    return exec('ps', ['-p', String(pid), '-o', 'command=']).trim() || null
  } catch {
    return null
  }
}

/** Whether what `programOf` found is the program recorded earlier. */
export function sameProgram(found: string | null, command: string, platform: Platform = process.platform): boolean {
  if (!found) return false
  if (platform === 'win32') return path.win32.basename(command).toLowerCase() === found.toLowerCase()
  return found.includes(command)
}

/**
 * Process ids of every program running from inside `dir` (Windows only; elsewhere process groups already
 * cover this). It catches helpers that outlived a program that crashed, which `taskkill /T` can no
 * longer reach because Windows does not re-parent them. Matching on the folder keeps it away from a
 * system-wide Ollama or any program that is not ours.
 */
export function pidsRunningUnder(dir: string, platform: Platform = process.platform, exec: Runner = run): number[] {
  if (platform !== 'win32') return []
  const script =
    '$d = $env:SLOTHSHOT_PROGRAMS_DIR; ' +
    'Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($d, [System.StringComparison]::OrdinalIgnoreCase) } | ' +
    'ForEach-Object { $_.ProcessId }'
  try {
    const out = exec('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], {
      ...process.env,
      SLOTHSHOT_PROGRAMS_DIR: dir.endsWith(path.win32.sep) ? dir : dir + path.win32.sep,
    })
    return out
      .split(/\r?\n/)
      .map(line => Number.parseInt(line.trim(), 10))
      .filter(pid => Number.isInteger(pid) && pid > 0 && pid !== process.pid)
  } catch {
    return []
  }
}

/** Ends whatever is still running from `dir`. Returns how many programs it stopped. */
export function sweepPrograms(dir: string, platform: Platform = process.platform, exec: Runner = run): number {
  const pids = pidsRunningUnder(dir, platform, exec)
  for (const pid of pids) killTree(pid, 'SIGKILL', platform, exec)
  return pids.length
}

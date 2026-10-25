import type { RecommendedModel, SetupProgress, SetupStep } from '~/types/api'
import { formatBytes } from './format'

/** "12.4 MB/s", or null when nothing has arrived yet to measure. */
export function formatSpeed(bytesPerSecond: number | null): string | null {
  if (!bytesPerSecond || bytesPerSecond <= 0) return null
  return `${formatBytes(bytesPerSecond)}/s`
}

/** "about 4 minutes left". Deliberately vague: a precise wrong number is worse than a rough one. */
export function formatEta(seconds: number | null): string | null {
  if (seconds === null || !Number.isFinite(seconds) || seconds <= 0) return null
  if (seconds < 60) return 'less than a minute left'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `about ${minutes} minute${minutes === 1 ? '' : 's'} left`
  const hours = Math.round(seconds / 3600)
  return `about ${hours} hour${hours === 1 ? '' : 's'} left`
}

/** The line under the bar: how much of how much, how fast, how long left. */
export function downloadLine(step: SetupStep): string | null {
  if (step.state !== 'running' || step.total <= 0) return null
  const parts = [`${formatBytes(step.completed)} of ${formatBytes(step.total)}`]
  const speed = formatSpeed(step.speed_bps)
  if (speed) parts.push(speed)
  const eta = formatEta(step.eta_s)
  if (eta) parts.push(eta)
  return parts.join(' · ')
}

/** What the user is told a model will cost them, before anything is downloaded. */
export function modelCost(model: RecommendedModel): string {
  const size = model.size_exact ? formatBytes(model.size_bytes) : `about ${formatBytes(model.size_bytes)}`
  return `${size} to download · needs ${model.ram_gb} GB of memory · ${model.license}`
}

/** Whether the wizard should offer to pick up where it stopped. */
export function canResume(progress: SetupProgress): boolean {
  return (
    ['paused', 'failed', 'interrupted'].includes(progress.state)
    && progress.model !== null
    && progress.steps.some(step => step.completed > 0)
  )
}

export function isBusy(progress: SetupProgress): boolean {
  return progress.state === 'running'
}

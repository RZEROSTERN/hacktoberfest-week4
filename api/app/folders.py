"""Finding the folder screenshots land in, and deciding which folders may be watched.

Each platform is handled by its own branch; nothing is shared by accident:

- macOS keeps the user's chosen location in the `com.apple.screencapture` domain under
  `location`. When that key is absent, screenshots go to the Desktop.
- Windows 11 puts them in `%USERPROFILE%\\Pictures\\Screenshots`, which moves inside OneDrive
  when Pictures is backed up, so both are offered.
- Linux has no specification for a screenshots folder. The pictures folder itself is
  specified (XDG user directories); the `Screenshots` subfolder is a convention GNOME and KDE
  both follow, so it is offered first and the pictures folder second.

None of these are assumed to exist: only folders actually present are returned.
"""

import os
import subprocess
import sys
from pathlib import Path

from app.errors import ApiError

# The folder Slothshot creates inside a watched folder. Never scanned: it holds this app's own
# output, and re-reading it would analyse everything a second time under a new name.
ORGANIZED_DIR_NAME = "Slothshot"

_MAC_DOMAIN = "com.apple.screencapture"


def _run_defaults(domain: str, key: str) -> str | None:
    """Reads one macOS preference. Returns None when it is not set or `defaults` is unavailable."""
    try:
        completed = subprocess.run(
            ["defaults", "read", domain, key],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


def _xdg_pictures(home: Path, env: dict[str, str]) -> Path:
    """The XDG pictures directory: the environment first, then user-dirs.dirs, then the default."""
    from_env = env.get("XDG_PICTURES_DIR")
    if from_env:
        return Path(os.path.expandvars(from_env)).expanduser()

    config_home = env.get("XDG_CONFIG_HOME")
    config = Path(config_home).expanduser() if config_home else home / ".config"
    user_dirs = config / "user-dirs.dirs"
    try:
        for line in user_dirs.read_text("utf-8").splitlines():
            if not line.startswith("XDG_PICTURES_DIR="):
                continue
            raw = line.split("=", 1)[1].strip().strip('"')
            # The file writes paths as "$HOME/Pictures".
            return Path(raw.replace("$HOME", str(home))).expanduser()
    except OSError:
        pass
    return home / "Pictures"


def detect_screenshot_folders(
    home: Path | None = None,
    platform: str | None = None,
    env: dict[str, str] | None = None,
) -> list[Path]:
    """Folders this OS is likely to put screenshots in, most likely first. Existing ones only."""
    home = home or Path.home()
    platform = platform or sys.platform
    env = env if env is not None else dict(os.environ)

    candidates: list[Path] = []
    if platform == "darwin":
        configured = _run_defaults(_MAC_DOMAIN, "location")
        if configured:
            candidates.append(Path(configured).expanduser())
        candidates.append(home / "Desktop")
    elif platform == "win32":
        profile = Path(env.get("USERPROFILE", str(home)))
        candidates.append(profile / "Pictures" / "Screenshots")
        onedrive = env.get("OneDrive") or env.get("OneDriveConsumer")
        if onedrive:
            candidates.append(Path(onedrive) / "Pictures" / "Screenshots")
    else:
        pictures = _xdg_pictures(home, env)
        candidates.append(pictures / "Screenshots")
        candidates.append(pictures)

    seen: set[Path] = set()
    found: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_dir():
            found.append(resolved)
    return found


def is_inside(child: Path, parent: Path) -> bool:
    """True when `child` is `parent` or sits underneath it."""
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_folder(path: Path, already_watched: list[Path]) -> Path:
    """Check a folder the user wants to add. Returns the resolved path or raises ApiError."""
    try:
        resolved = path.expanduser().resolve()
    except OSError as exc:
        raise ApiError(400, "folder_not_found") from exc

    if not resolved.exists():
        raise ApiError(400, "folder_not_found")
    if not resolved.is_dir():
        raise ApiError(400, "not_a_folder")
    if ORGANIZED_DIR_NAME in resolved.parts:
        # Watching our own output would re-sort files that are already sorted.
        raise ApiError(400, "cannot_watch_organized")
    if not os.access(resolved, os.R_OK | os.X_OK):
        raise ApiError(400, "folder_unreadable")

    for watched in already_watched:
        if resolved == watched:
            raise ApiError(409, "folder_already_watched")
        if is_inside(resolved, watched):
            raise ApiError(409, "folder_inside_watched")
    return resolved

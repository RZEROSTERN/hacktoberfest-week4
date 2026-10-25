"""SQLite tables.

Two rules shape this schema:

- Nothing is ever deleted, so every file operation is recorded in `Change` as a pair of paths
  that can be walked backwards. Undo replays the journal in reverse; it never guesses.
- A screenshot is identified by the SHA-256 of its bytes, not by its path, so a file that is
  renamed or moved outside the app is still recognised and never analysed twice.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Category(StrEnum):
    RECEIPT = "receipt"
    CONVERSATION = "conversation"
    CODE = "code"
    TICKET_OR_BOOKING = "ticket or booking"
    DOCUMENT = "document"
    SOCIAL_MEDIA = "social media"
    MEME = "meme"
    DESIGN = "design"
    ERROR_MESSAGE = "error message"
    OTHER = "other"


class ShotStatus(StrEnum):
    PENDING = "pending"  # found on disk, not analysed yet
    ANALYZED = "analyzed"
    SKIPPED = "skipped"  # the model's answer could not be parsed, even after one retry
    MISSING = "missing"  # the file is no longer where the journal says it is


class RunStatus(StrEnum):
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"  # the first run stops here until the user approves
    ORGANIZING = "organizing"
    DONE = "done"
    PAUSED = "paused"  # the machine woke up, went on battery, or left the schedule window
    CANCELLED = "cancelled"
    FAILED = "failed"


class ChangeKind(StrEnum):
    MOVE = "move"  # covers renames: both are a from_path -> to_path pair
    CREATE_DIR = "create_dir"


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class WatchedFolder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(unique=True, index=True)
    added_at: datetime = Field(default_factory=_now)
    enabled: bool = True
    # True for the folder detected from the OS, so the UI can label it and the user can still
    # remove it.
    detected: bool = False


class Screenshot(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    # Identity and duplicate detection.
    #
    # NOT unique: two files can hold identical bytes, and both are real files the app has to
    # manage. The row identifies a file; the hash identifies its content. A second copy gets
    # its own row and is sent to Review like any other duplicate.
    content_hash: str = Field(index=True)  # SHA-256 of the file's bytes
    perceptual_hash: str | None = Field(default=None, index=True)  # 64-bit dHash, hex

    # Where the file is. `original_path` is where it was first seen and is what undo restores.
    original_path: str
    current_path: str = Field(index=True)
    size_bytes: int
    width: int | None = None
    height: int | None = None
    captured_at: datetime | None = None  # from the file's mtime; used for the date prefix
    first_seen_at: datetime = Field(default_factory=_now)

    # Analysis. Null until the model has run.
    status: ShotStatus = Field(default=ShotStatus.PENDING, index=True)
    skip_reason: str | None = None
    analyzed_at: datetime | None = None
    model_tag: str | None = None  # which model produced the fields below
    prompt_version: str | None = None

    slug: str | None = None
    category: Category | None = Field(default=None, index=True)
    description: str | None = None
    # Only stored when the screenshot is NOT sensitive, or when the user has explicitly turned
    # on indexing of sensitive text. Never written to a log either way.
    extracted_text: str | None = None
    sensitive: bool = Field(default=False, index=True)
    expiry_hint: str | None = None  # the model's words, e.g. "flight on 3 May 2026"
    expired: bool = Field(default=False, index=True)

    # Set when this file is an exact or near copy of another, which sends it to Review.
    duplicate_of_id: int | None = Field(default=None, foreign_key="screenshot.id", index=True)


class Run(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    status: RunStatus = Field(default=RunStatus.SCANNING, index=True)
    # True for a run the user started from the "Sort now" button rather than the scheduler.
    manual: bool = False

    found: int = 0
    analyzed: int = 0
    skipped: int = 0
    organized: int = 0
    duplicates: int = 0
    expired: int = 0
    # Bytes held by the duplicates and expired items sitting in Review, for the morning card.
    reviewable_bytes: int = 0


class Change(SQLModel, table=True):
    """One reversible file operation. The journal; undo reads it backwards.

    A row is written BEFORE the operation and marked `applied` after it succeeds, so a crash
    mid-run leaves a record that undo can verify against the filesystem rather than a silent gap.
    """

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    screenshot_id: int | None = Field(default=None, foreign_key="screenshot.id", index=True)
    kind: ChangeKind
    from_path: str | None = None  # null for create_dir
    to_path: str
    applied: bool = Field(default=False, index=True)
    applied_at: datetime | None = None
    undone_at: datetime | None = Field(default=None, index=True)


class SetupState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"  # the user paused; resuming continues where it stopped
    FAILED = "failed"  # a download or check failed; trying again continues where it stopped
    COMPAT_FAILED = "compat_failed"  # the model downloaded but cannot read an image
    INTERRUPTED = "interrupted"  # the app was closed mid-run; the user is asked before resuming
    DONE = "done"


class SetupRun(SQLModel, table=True):
    """The last model setup (first launch or Settings), kept so it can resume after a restart."""

    id: int = Field(default=1, primary_key=True)
    state: SetupState = SetupState.IDLE
    model_tag: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    overall_fraction: float = 0.0
    error_code: str | None = None
    updated_at: datetime = Field(default_factory=_now)

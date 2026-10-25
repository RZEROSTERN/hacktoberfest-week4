/** Mirrors the api's models. Kept hand-written and small rather than generated. */

export type Category =
  | 'receipt'
  | 'conversation'
  | 'code'
  | 'ticket or booking'
  | 'document'
  | 'social media'
  | 'meme'
  | 'design'
  | 'error message'
  | 'other'

export type ShotStatus = 'pending' | 'analyzed' | 'skipped' | 'missing'

export type RunStatus =
  | 'scanning'
  | 'analyzing'
  | 'awaiting_approval'
  | 'organizing'
  | 'done'
  | 'paused'
  | 'cancelled'
  | 'failed'

export interface AppStatus {
  vision_model: string | null
  index_sensitive_text: boolean
  max_image_px: number
}

export interface RunSummary {
  id: number
  status: RunStatus
  started_at: string
  finished_at: string | null
  found: number
  analyzed: number
  skipped: number
  organized: number
  duplicates: number
  expired: number
  reviewable_bytes: number
}

export interface Summary {
  run_id: number | null
  finished_at: string | null
  sorted_count: number
  skipped_count: number
  duplicates_waiting: number
  expired_waiting: number
  reclaimable_bytes: number
  total_indexed: number
}

export interface SearchHit {
  id: number
  path: string
  slug: string | null
  category: Category | null
  description: string | null
  sensitive: boolean
  in_review: boolean
  snippet: string | null
}

export interface SearchResults {
  query: string
  count: number
  hits: SearchHit[]
}

export interface Schedule {
  enabled: boolean
  windowStart: string
  windowEnd: string
  requireIdle: boolean
  idleThresholdSeconds: number
  pauseOnBattery: boolean
}

export interface AppSettings {
  vision_model: string | null
  index_sensitive_text: boolean
  max_image_px: number
  schedule: Schedule
  paused: boolean
}

export interface RecommendedModel {
  model: string
  title: string
  recommended: boolean
  size_bytes: number
  size_exact: boolean
  ram_gb: number
  max_image_px: number
  license: string
  note: string
}

export type SetupState =
  | 'idle' | 'running' | 'paused' | 'failed' | 'compat_failed' | 'interrupted' | 'done'

export interface SetupStep {
  id: string
  label: string
  state: 'pending' | 'running' | 'done' | 'failed'
  detail: string | null
  skipped: boolean
  completed: number
  total: number
  speed_bps: number | null
  eta_s: number | null
}

export interface SetupProgress {
  state: SetupState
  model: string | null
  steps: SetupStep[]
  error_code: string | null
  overall: { fraction: number, completed_bytes: number, total_bytes: number }
}

export interface SetupStatus {
  ready: boolean
  ollama_reachable: boolean
  model: { model: string | null, state: string }
  compat_ok: boolean
  run: { state: SetupState, model: string | null, fraction: number }
  recommended: RecommendedModel[]
}

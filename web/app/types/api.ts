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

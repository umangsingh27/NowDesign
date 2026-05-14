export type Theme = 'dark' | 'light'
export type LogoType = 'nowpurchase' | 'metalcloud' | 'combined'
export type SessionState = 'BRIEF' | 'DIALOGUE' | 'GENERATING' | 'REVIEW' | 'APPROVED'
export type Emotion = 'inspiring' | 'professional' | 'urgent' | 'celebratory' | 'informative'
export type PostPurpose =
  | 'product_feature' | 'testimonial' | 'announcement' | 'insight'
  | 'event' | 'case_study' | 'team' | 'product_launch'

export interface Brief {
  headline: string
  emotion: Emotion
  purpose: PostPurpose
  body_copy?: string
  stat?: string
  attribution?: string
  cta?: string
  requested_by?: string
  logo_type: LogoType
  theme: Theme
}

export interface GenerationEvent {
  event: 'status_update' | 'image_ready' | 'state_change' | 'error'
  data: Record<string, unknown>
}

export interface ComplianceCriterion {
  score: number
  max: number
  notes: string
}

export interface ComplianceReport {
  total_score: number
  max_score: number
  passed: boolean
  issues: string[]
  criteria_detail: Record<string, ComplianceCriterion>
}

export interface SessionSummary {
  id: string
  created_at: string
  state: string
  logo_type: LogoType
  theme: Theme
  compliance_score?: number
  user_rating?: number
  requested_by?: string
  image_url?: string
}

import { Brief, SessionState, ComplianceReport } from './types'

export interface SessionMachineState {
  appState:         SessionState
  sessionId:        string | null
  brief:            Brief | null
  imageUrl:         string | null
  complianceScore:  number | null
  complianceReport: ComplianceReport | null
  progressMessage:  string
  progressPct:      number
  plannerQuestions: string[]
  revisionCount:    number
  error:            string | null
}

export const INITIAL_STATE: SessionMachineState = {
  appState:         'BRIEF',
  sessionId:        null,
  brief:            null,
  imageUrl:         null,
  complianceScore:  null,
  complianceReport: null,
  progressMessage:  '',
  progressPct:      0,
  plannerQuestions: [],
  revisionCount:    0,
  error:            null,
}

export type SessionAction =
  | { type: 'START_GENERATING'; brief: Brief }
  | { type: 'SET_SESSION_ID'; sessionId: string }
  | { type: 'PROGRESS'; message: string; pct: number }
  | { type: 'ENTER_DIALOGUE'; questions: string[] }
  | { type: 'IMAGE_READY'; imageUrl: string; score: number; report?: ComplianceReport }
  | { type: 'ENTER_REVIEW' }
  | { type: 'SUBMIT_FEEDBACK' }
  | { type: 'APPROVED'; imageUrl: string }
  | { type: 'ERROR'; message: string }
  | { type: 'RESET' }

export function sessionReducer(
  state: SessionMachineState,
  action: SessionAction
): SessionMachineState {
  switch (action.type) {
    case 'START_GENERATING':
      return { ...state, appState: 'GENERATING', brief: action.brief,
               progressPct: 0, progressMessage: 'Starting...', error: null }
    case 'SET_SESSION_ID':
      return { ...state, sessionId: action.sessionId }
    case 'PROGRESS':
      return { ...state, progressMessage: action.message, progressPct: action.pct }
    case 'ENTER_DIALOGUE':
      return { ...state, appState: 'DIALOGUE', plannerQuestions: action.questions }
    case 'IMAGE_READY':
      return { ...state, imageUrl: action.imageUrl,
               complianceScore: action.score,
               complianceReport: action.report ?? null }
    case 'ENTER_REVIEW':
      return { ...state, appState: 'REVIEW', progressPct: 100 }
    case 'SUBMIT_FEEDBACK':
      return { ...state, appState: 'GENERATING', revisionCount: state.revisionCount + 1,
               progressPct: 0, progressMessage: 'Applying changes...' }
    case 'APPROVED':
      return { ...state, appState: 'APPROVED', imageUrl: action.imageUrl }
    case 'ERROR':
      return { ...state, error: action.message, appState: 'BRIEF' }
    case 'RESET':
      return INITIAL_STATE
    default:
      return state
  }
}

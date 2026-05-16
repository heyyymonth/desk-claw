export type Priority = 'low' | 'normal' | 'high' | 'urgent';
export type Decision = 'schedule' | 'decline' | 'clarify' | 'defer';
export type RiskLevel = 'low' | 'medium' | 'high';
export type ModelStatus = 'used' | 'unavailable' | 'invalid_output' | 'not_configured';
export type ModelProvider = 'openai' | 'anthropic' | 'gemini' | 'mock';
export type DraftTone = 'concise' | 'warm' | 'firm';
export type FeedbackDecision = 'accepted' | 'edited' | 'rejected' | 'wrong';
export type MeetingType =
  | 'intro'
  | 'internal'
  | 'customer'
  | 'investor'
  | 'candidate'
  | 'vendor'
  | 'partner'
  | 'board'
  | 'legal_hr'
  | 'personal'
  | 'other';
export type DraftType = 'accept' | 'decline' | 'clarify' | 'defer';

export interface TimeWindow {
  start: string;
  end: string;
}

export interface MeetingIntent {
  title: string;
  requester: string;
  duration_minutes: number;
  priority: Priority;
  meeting_type?: MeetingType;
  attendees: string[];
  preferred_windows?: TimeWindow[];
  constraints: string[];
  missing_fields: string[];
  sensitivity?: RiskLevel;
  async_candidate?: boolean;
  escalation_required?: boolean;
}

export interface MeetingRequest {
  raw_text: string;
  intent: MeetingIntent;
}

export interface ExecutiveRules {
  executive_name: string;
  timezone: string;
  working_hours: {
    start: string;
    end: string;
  };
  protected_blocks: Array<{
    label: string;
    start: string;
    end: string;
  }>;
  preferences: string[];
}

export interface Recommendation {
  decision: Decision;
  confidence: number;
  rationale: string[];
  risks: Array<{
    level: RiskLevel;
    message: string;
  }>;
  risk_level?: RiskLevel;
  safe_action?: string;
  proposed_slots: Array<{
    start: string;
    end: string;
    reason: string;
  }>;
  model_status: ModelStatus;
}

export interface DraftResponse {
  subject: string;
  body: string;
  tone: DraftTone;
  draft_type?: DraftType;
  model_status: ModelStatus;
}

export interface ParseRequestResponse {
  parsed_request: MeetingRequest;
  recommendation: Recommendation;
  draft_response: DraftResponse;
  next_steps: string[];
}

export interface CalendarContext {
  timezone?: string;
  availability?: TimeWindow[];
  busy_blocks?: Array<TimeWindow & { title?: string }>;
  assumptions?: string[];
  missing_context?: string[];
}

export interface DecisionLogEntry {
  id?: number | string;
  created_at?: string;
  meeting_request: MeetingRequest;
  recommendation: Recommendation;
  final_decision: string;
  notes?: string;
}

export interface HealthStatus {
  status?: string;
  model?: string;
  model_provider?: ModelProvider;
  model_runtime?: string;
  api_key_configured?: boolean;
}

export type Priority = "low" | "normal" | "high" | "urgent";
export type Decision = "schedule" | "decline" | "clarify" | "defer";
export type RiskLevel = "low" | "medium" | "high";
export type ModelStatus = "used" | "unavailable" | "invalid_output" | "not_configured";
export type Tone = "concise" | "warm" | "firm";

export interface TimeWindow {
  start: string;
  end: string;
}

export interface MeetingIntent {
  title: string;
  requester: string;
  duration_minutes: number;
  priority: Priority;
  attendees: string[];
  preferred_windows: TimeWindow[];
  constraints: string[];
  missing_fields: string[];
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
  protected_blocks: Array<TimeWindow & { label: string }>;
  preferences: string[];
}

export interface RecommendationRisk {
  level: RiskLevel;
  message: string;
}

export interface ProposedSlot extends TimeWindow {
  reason: string;
}

export interface Recommendation {
  decision: Decision;
  confidence: number;
  rationale: string[];
  risks: RecommendationRisk[];
  proposed_slots: ProposedSlot[];
  model_status: ModelStatus;
}

export interface DraftResponse {
  subject: string;
  body: string;
  tone: Tone;
  model_status: ModelStatus;
}

export interface DecisionLogEntry {
  id: number;
  created_at: string;
  meeting_request: MeetingRequest;
  recommendation: Recommendation;
  final_decision: string;
  notes: string;
}

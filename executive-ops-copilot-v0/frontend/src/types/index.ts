export type Priority = 'low' | 'normal' | 'high' | 'urgent';
export type Decision = 'schedule' | 'decline' | 'clarify' | 'defer';
export type RiskLevel = 'low' | 'medium' | 'high';
export type ModelStatus = 'used' | 'unavailable' | 'invalid_output' | 'not_configured';
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
  backend?: string;
  ollama?: ModelStatus | 'available' | 'unknown' | 'configured';
  model_status?: ModelStatus;
  model?: string;
  adk_model?: string;
  model_runtime?: string;
}

export interface AiOperationMetric {
  operation: string;
  total: number;
  success_rate: number;
  adk_coverage: number;
  avg_latency_ms: number;
  tool_calls_avg: number;
  model_status_counts: Record<string, number>;
}

export interface AiEventSummary {
  id: string;
  created_at: string;
  operation: string;
  model_name: string;
  model_status: ModelStatus;
  runtime: string;
  agent_name?: string | null;
  latency_ms: number;
  status: string;
  error_code?: string | null;
  tool_calls: string[];
}

export interface AiToolMetric {
  tool_name: string;
  calls: number;
  failure_count: number;
  success_rate: number;
  avg_latency_ms: number;
  failure_reasons: Record<string, number>;
}

export interface AiInsight {
  severity: 'info' | 'warning' | 'critical';
  title: string;
  detail: string;
  operation?: string;
  agent_name?: string | null;
  reason: string;
}

export interface AiMetrics {
  total_events: number;
  success_rate: number;
  adk_coverage: number;
  tool_call_coverage: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  model_status_counts: Record<string, number>;
  operation_metrics: AiOperationMetric[];
  tool_metrics: AiToolMetric[];
  insights: AiInsight[];
  slowest_events: AiEventSummary[];
  recent_failures: AiEventSummary[];
}

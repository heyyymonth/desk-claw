export type Priority = 'low' | 'normal' | 'high' | 'urgent';
export type RiskLevel = 'low' | 'medium' | 'high';
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

export interface TimeWindow {
  start: string;
  end: string;
}

export interface ExpectedIntent {
  title: string;
  requester: string;
  duration_minutes: number;
  priority: Priority;
  meeting_type: MeetingType;
  attendees: string[];
  preferred_windows: TimeWindow[];
  constraints: string[];
  missing_fields: string[];
  sensitivity: RiskLevel;
  async_candidate: boolean;
  escalation_required: boolean;
}

export interface EvalCase {
  id: string;
  name: string;
  description: string;
  prompt: string;
  expected: ExpectedIntent;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FieldDiff {
  field: string;
  expected: unknown;
  actual: unknown;
  passed: boolean;
  message: string;
}

export interface EvalCaseResult {
  id: string;
  run_id: string;
  case_id: string;
  case_name: string;
  status: 'passed' | 'failed' | 'invalid_output' | 'provider_error';
  passed: boolean;
  score: number;
  latency_ms: number | null;
  provider: string | null;
  model: string | null;
  raw_output: string;
  normalized_output: Record<string, unknown> | null;
  expected: ExpectedIntent;
  diffs: FieldDiff[];
  error: string | null;
  created_at: string;
}

export interface EvalRun {
  id: string;
  created_at: string;
  total_cases: number;
  passed_cases: number;
  pass_rate: number;
  avg_latency_ms: number | null;
  results?: EvalCaseResult[];
}

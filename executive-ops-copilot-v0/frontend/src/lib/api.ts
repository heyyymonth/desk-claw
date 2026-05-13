import type { CalendarContext, DecisionLogEntry, ExecutiveRules, MeetingRequest, Recommendation } from '../types';
import { accountApi } from './accountApi';
import { adminApi } from './adminApi';
import { setActorIdentity } from './apiClient';
import { systemApi } from './systemApi';
import { workflowApi } from './workflowApi';

export { setActorIdentity };
export type { ActorIdentity } from './apiClient';

export const api = {
  ...systemApi,
  ...adminApi,
  ...workflowApi,
  ...accountApi,
};

export function getDefaultRules(): Promise<ExecutiveRules> {
  return api.defaultRules();
}

export function parseRequest(rawText: string): Promise<MeetingRequest> {
  return api.parseRequest(rawText);
}

export function getRecommendation(meetingRequest: MeetingRequest, rules: ExecutiveRules, calendar?: CalendarContext): Promise<Recommendation> {
  return api.recommendation(meetingRequest, rules, calendar);
}

export function getDraftResponse(meetingRequest: MeetingRequest, recommendation: Recommendation) {
  return api.draftResponse(meetingRequest, recommendation);
}

export function logDecision(
  meetingRequest: MeetingRequest,
  recommendation: Recommendation,
  finalDecision: string,
  notes: string,
): Promise<DecisionLogEntry> {
  return api.logDecision({
    meeting_request: meetingRequest,
    recommendation,
    final_decision: finalDecision,
    notes,
  });
}

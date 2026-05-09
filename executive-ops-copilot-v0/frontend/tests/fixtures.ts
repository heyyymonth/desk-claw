import type { DraftResponse, ExecutiveRules, MeetingRequest, Recommendation } from '../src/types';

export const meetingRequest: MeetingRequest = {
  raw_text: 'Can Taylor meet with Jordan next Tuesday for 30 minutes?',
  intent: {
    title: 'Partner sync',
    requester: 'Jordan Lee',
    duration_minutes: 30,
    priority: 'normal',
    attendees: ['Taylor', 'Jordan Lee'],
    preferred_windows: [
      {
        start: '2026-05-12T16:00:00-07:00',
        end: '2026-05-12T16:30:00-07:00',
      },
    ],
    constraints: ['Prefer afternoon'],
    missing_fields: ['Requester timezone'],
  },
};

export const rules: ExecutiveRules = {
  executive_name: 'Taylor',
  timezone: 'America/Los_Angeles',
  working_hours: { start: '09:00', end: '17:00' },
  protected_blocks: [],
  preferences: ['Keep Fridays light', 'Prefer customer meetings before 3 PM'],
};

export const recommendation: Recommendation = {
  decision: 'schedule',
  confidence: 0.82,
  rationale: ['Requested window fits working hours.', 'No protected block conflict.'],
  risks: [{ level: 'medium', message: 'Requester timezone is missing.' }],
  proposed_slots: [
    {
      start: '2026-05-12T16:00:00-07:00',
      end: '2026-05-12T16:30:00-07:00',
      reason: 'Open calendar window with enough buffer.',
    },
  ],
  model_status: 'used',
};

export const draft: DraftResponse = {
  subject: 'Re: Partner sync',
  body: 'Taylor can meet next Tuesday at 4:00 PM PT.',
  tone: 'warm',
  model_status: 'used',
};

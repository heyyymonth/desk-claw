import { useMutation, useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { CalendarContextPanel } from './components/CalendarContextPanel';
import { DecisionFeedbackControls } from './components/DecisionFeedbackControls';
import { DecisionLogView } from './components/DecisionLogView';
import { DraftResponsePanel } from './components/DraftResponsePanel';
import { ExecutiveRulesPanel } from './components/ExecutiveRulesPanel';
import { RecommendationCard } from './components/RecommendationCard';
import { RequestIntakePanel } from './components/RequestIntakePanel';
import { StatusIndicator } from './components/StatusIndicator';
import { ErrorState } from './components/ui';
import { api } from './lib/api';
import type {
  CalendarContext,
  DecisionLogEntry,
  DraftResponse,
  ExecutiveRules,
  FeedbackDecision,
  MeetingRequest,
  Recommendation,
} from './types';

const starterRules: ExecutiveRules = {
  executive_name: 'Executive',
  timezone: 'America/Los_Angeles',
  working_hours: { start: '09:00', end: '17:00' },
  protected_blocks: [],
  preferences: ['Avoid moving protected focus time without explicit approval.'],
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function App() {
  const [rawText, setRawText] = useState('');
  const [validationError, setValidationError] = useState('');
  const [meetingRequest, setMeetingRequest] = useState<MeetingRequest>();
  const [rules, setRules] = useState<ExecutiveRules>(starterRules);
  const [calendarContext, setCalendarContext] = useState<CalendarContext>();
  const [recommendation, setRecommendation] = useState<Recommendation>();
  const [draft, setDraft] = useState<DraftResponse>();
  const [localDecisions, setLocalDecisions] = useState<DecisionLogEntry[]>([]);

  const healthQuery = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15000 });
  const rulesQuery = useQuery({ queryKey: ['default-rules'], queryFn: api.defaultRules });
  const calendarQuery = useQuery<CalendarContext>({ queryKey: ['mock-calendar'], queryFn: api.mockCalendar });
  const decisionsQuery = useQuery({ queryKey: ['decisions'], queryFn: api.decisions, retry: false });

  useEffect(() => {
    if (rulesQuery.data) {
      setRules(rulesQuery.data);
    }
  }, [rulesQuery.data]);

  useEffect(() => {
    if (calendarQuery.data) {
      setCalendarContext(calendarQuery.data);
    }
  }, [calendarQuery.data]);

  const parseMutation = useMutation({
    mutationFn: api.parseRequest,
    onSuccess: (data) => {
      setMeetingRequest(data);
      setRecommendation(undefined);
      setDraft(undefined);
    },
  });

  const recommendationMutation = useMutation({
    mutationFn: () => {
      if (!meetingRequest) {
        throw new Error('Parse a request before generating a recommendation.');
      }
      return api.recommendation(meetingRequest, rules);
    },
    onSuccess: (data) => {
      setRecommendation(data);
      setDraft(undefined);
    },
  });

  const draftMutation = useMutation({
    mutationFn: () => {
      if (!meetingRequest || !recommendation) {
        throw new Error('Generate a recommendation before drafting a response.');
      }
      return api.draftResponse(meetingRequest, recommendation);
    },
    onSuccess: setDraft,
  });

  const logDecisionMutation = useMutation({
    mutationFn: (entry: Omit<DecisionLogEntry, 'id' | 'created_at'>) => api.logDecision(entry),
    onSuccess: (entry, variables) => {
      setLocalDecisions((current) => [entry ?? variables, ...current]);
    },
    onError: (_error, variables) => {
      setLocalDecisions((current) => [
        { ...variables, id: `local-${Date.now()}`, created_at: new Date().toISOString() },
        ...current,
      ]);
    },
  });

  const decisionEntries = useMemo(
    () => [...localDecisions, ...(decisionsQuery.data ?? [])],
    [localDecisions, decisionsQuery.data],
  );

  const handleParse = () => {
    if (!rawText.trim()) {
      setValidationError('Paste a meeting request before parsing.');
      return;
    }
    setValidationError('');
    parseMutation.mutate(rawText);
  };

  const handleFeedback = (finalDecision: FeedbackDecision, notes: string) => {
    if (!meetingRequest || !recommendation) {
      return;
    }
    const finalNotes =
      finalDecision === 'edited' && draft
        ? [
            notes || 'Draft edited before use.',
            `Edited draft subject: ${draft.subject}`,
            `Edited draft body: ${draft.body}`,
          ].join('\n')
        : notes;
    logDecisionMutation.mutate({
      meeting_request: meetingRequest,
      recommendation,
      final_decision: finalDecision,
      notes: finalNotes,
    });
  };

  const topError =
    parseMutation.error ?? recommendationMutation.error ?? draftMutation.error ?? logDecisionMutation.error;

  return (
    <main className="min-h-screen bg-[#eef2f6]">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 lg:px-6">
        <header className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div>
            <h1 className="text-2xl font-bold text-ink">Scheduling Decision Workbench</h1>
            <p className="mt-1 max-w-3xl text-sm text-steel">
              Parse one request, review assumptions, generate a recommendation, draft a response, and log the human decision.
            </p>
          </div>
          <StatusIndicator health={healthQuery.data} isLoading={healthQuery.isLoading} error={healthQuery.error} />
        </header>

        {topError ? <ErrorState message={errorMessage(topError, 'FastAPI request failed.')} /> : null}

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="min-w-0 space-y-5">
            <RequestIntakePanel
              rawText={rawText}
              onRawTextChange={(value) => {
                setRawText(value);
                setValidationError('');
              }}
              onParse={handleParse}
              parsedRequest={meetingRequest}
              isParsing={parseMutation.isPending}
              error={parseMutation.error ? errorMessage(parseMutation.error, 'Could not parse request.') : undefined}
              validationError={validationError}
            />
            <RecommendationCard
              recommendation={recommendation}
              rules={rules}
              onGenerate={() => recommendationMutation.mutate()}
              disabled={!meetingRequest}
              isLoading={recommendationMutation.isPending}
            />
            <DraftResponsePanel
              draft={draft}
              onDraftChange={setDraft}
              onGenerate={() => draftMutation.mutate()}
              disabled={!meetingRequest || !recommendation}
              isLoading={draftMutation.isPending}
            />
            <DecisionFeedbackControls
              onSubmit={handleFeedback}
              disabled={!meetingRequest || !recommendation}
              isLogging={logDecisionMutation.isPending}
            />
          </div>

          <aside className="min-w-0 space-y-5">
            <ExecutiveRulesPanel
              rules={rules}
              onChange={setRules}
              error={rulesQuery.error ? 'FastAPI default rules are unavailable. Starter rules are shown.' : undefined}
            />
            <CalendarContextPanel
              calendar={calendarContext}
              onChange={setCalendarContext}
              meetingRequest={meetingRequest}
              error={calendarQuery.error ? 'FastAPI mock calendar is unavailable. Calendar impact may be incomplete.' : undefined}
            />
            <DecisionLogView entries={decisionEntries} />
          </aside>
        </div>
      </div>
    </main>
  );
}

import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCircle2, ClipboardList, FileText, PenLine, Route, ShieldCheck, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CalendarContextPanel } from './components/CalendarContextPanel';
import { DecisionFeedbackControls } from './components/DecisionFeedbackControls';
import { DecisionLogView } from './components/DecisionLogView';
import { DraftResponsePanel } from './components/DraftResponsePanel';
import { ExecutiveRulesPanel } from './components/ExecutiveRulesPanel';
import { RecommendationCard } from './components/RecommendationCard';
import { RequestIntakePanel } from './components/RequestIntakePanel';
import { StatusIndicator } from './components/StatusIndicator';
import { WorkWeekCalendar } from './components/WorkWeekCalendar';
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

const workflowSteps = [
  {
    label: 'Paste the request',
    detail: 'Add the email or message exactly as received.',
    icon: ClipboardList,
  },
  {
    label: 'Review details',
    detail: 'Confirm requester, timing, risk, and missing context.',
    icon: CheckCircle2,
  },
  {
    label: 'Get guidance',
    detail: 'Generate a scheduling recommendation for review.',
    icon: Route,
  },
  {
    label: 'Prepare reply',
    detail: 'Draft, edit, and log the final human decision.',
    icon: PenLine,
  },
];

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
  const activeStep = draft
    ? 4
    : recommendation
      ? 3
      : meetingRequest
        ? 2
        : rawText.trim()
          ? 1
          : 0;

  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 lg:px-6">
        <header className="flex flex-col justify-between gap-4 border-b border-white/70 pb-5 md:flex-row md:items-center">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-white/35 bg-gradient-to-br from-[#4b5563] to-[#1f2937] text-white shadow-[0_16px_32px_rgba(31,38,50,0.24)]">
              <ShieldCheck size={26} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h1 className="text-2xl font-bold text-ink">desk.ai</h1>
                <span className="rounded-md border border-white/70 bg-white/60 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brandDark shadow-sm">
                  Executive Ops Workbench
                </span>
              </div>
              <p className="mt-1 max-w-3xl text-sm text-steel">
                A calm, auditable workspace for turning inbound meeting requests into reviewed scheduling decisions.
              </p>
            </div>
          </div>
          <StatusIndicator health={healthQuery.data} isLoading={healthQuery.isLoading} error={healthQuery.error} />
        </header>

        {topError ? <ErrorState message={errorMessage(topError, 'FastAPI request failed.')} /> : null}

        <section className="rounded-lg border border-white/70 bg-white/55 p-4 shadow-[0_18px_44px_rgba(31,38,50,0.10)] backdrop-blur-md">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-line bg-white/80 text-brandDark shadow-sm">
                <Sparkles size={18} aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-ink">Your guided scheduling review</h2>
                <p className="mt-1 max-w-2xl text-sm text-steel">
                  Work left to right: capture the request, check what desk.ai understood, review the recommendation, then approve the response.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-md border border-line bg-white/70 px-3 py-2 text-sm text-steel shadow-sm">
              <FileText size={16} aria-hidden="true" />
              <span>Every AI step is logged for audit.</span>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {workflowSteps.map((step, index) => {
              const Icon = step.icon;
              const isComplete = activeStep > index;
              const isCurrent = activeStep === index;
              return (
                <div
                  key={step.label}
                  className={`rounded-lg border px-3 py-3 shadow-sm ${
                    isComplete || isCurrent
                      ? 'border-[#b9c0ca] bg-white/80'
                      : 'border-white/70 bg-white/45'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-md ${
                        isComplete ? 'bg-brandDark text-white' : 'border border-line bg-white/75 text-brand'
                      }`}
                    >
                      <Icon size={16} aria-hidden="true" />
                    </div>
                    <div className="text-sm font-semibold text-ink">{step.label}</div>
                  </div>
                  <p className="mt-2 text-sm text-steel">{step.detail}</p>
                </div>
              );
            })}
          </div>
        </section>

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
            <WorkWeekCalendar
              calendar={calendarContext}
              rules={rules}
              recommendation={recommendation}
              meetingRequest={meetingRequest}
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

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Activity,
  Bell,
  Building2,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  FileText,
  Gauge,
  Home,
  KeyRound,
  LockKeyhole,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  PenLine,
  Route,
  Settings,
  SlidersHorizontal,
  Sparkles,
  UserCircle,
  Users,
  Workflow,
  type LucideIcon,
} from 'lucide-react';
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

const enterpriseSignals = [
  { label: 'Requests reviewed', value: '1.8k', detail: 'this quarter', icon: Activity },
  { label: 'Avg. cycle time', value: '4m', detail: 'request to draft', icon: Gauge },
  { label: 'Audit coverage', value: '100%', detail: 'human decision log', icon: LockKeyhole },
];

const trustMarks = ['Northstar Ops', 'Atlas Finance', 'Forge AI', 'Helio Systems', 'Summit Cloud'];

type PageId = 'home' | 'admin' | 'account' | 'settings';

const pages = [
  { id: 'home' as const, label: 'Home', detail: 'Chat and calendar', icon: Home },
  { id: 'admin' as const, label: 'Admin Center', detail: 'Intake, drafts, logs', icon: Workflow },
  { id: 'account' as const, label: 'Account', detail: 'Plan and seats', icon: UserCircle },
  { id: 'settings' as const, label: 'Settings', detail: 'Security and AI controls', icon: Settings },
];

const commandPrompts = [
  'Find a safe 30 minute window with Support leadership.',
  'Summarize today\'s calendar risk before the 2 PM board prep.',
  'Draft a concise reply asking for missing attendee context.',
];

const brandLogoSrc = '/brand/desk-ai-logo.jpeg';

export function App() {
  const [activePage, setActivePage] = useState<PageId>('home');
  const [isNavPinned, setIsNavPinned] = useState(false);
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

  const navExpanded = isNavPinned;

  return (
    <main className="min-h-screen">
      <div className="flex min-h-screen">
        <aside
          className={`group/sidebar fixed inset-y-0 left-0 z-30 hidden border-r border-white/20 bg-[linear-gradient(180deg,#2d3542,#171d27)] text-white shadow-[18px_0_48px_rgba(31,38,50,0.20)] transition-[width] duration-200 lg:block ${
            isNavPinned ? 'w-64' : 'w-20 hover:w-64'
          }`}
        >
          <div className={`flex h-full flex-col ${isNavPinned ? 'p-3' : 'px-3 py-3 group-hover/sidebar:p-3'}`}>
            <div className="flex min-h-14 items-center gap-3 border-b border-white/10 pb-3">
              <BrandLogo variant="mark" className="h-10 w-10 shrink-0" />
              <div className={`min-w-0 ${navExpanded ? 'block' : 'hidden group-hover/sidebar:block'}`}>
                <div className="font-bold leading-tight text-white">desk.ai</div>
                <div className="text-xs text-white/52">Ops command suite</div>
              </div>
            </div>

            <nav className="mt-4 space-y-2" aria-label="Primary pages">
              {pages.map((page) => {
                const Icon = page.icon;
                const isActive = activePage === page.id;
                return (
                  <button
                    key={page.id}
                    type="button"
                    aria-label={page.label}
                    onClick={() => setActivePage(page.id)}
                    className={`flex h-12 w-full items-center rounded-lg border text-left text-sm transition ${
                      isActive
                        ? 'border-white/20 bg-white text-brandDark shadow-[0_14px_34px_rgba(0,0,0,0.24)]'
                        : 'border-white/[0.08] bg-white/[0.04] text-white/72 hover:bg-white/[0.10] hover:text-white'
                    } ${navExpanded ? 'gap-3 px-3 justify-start' : 'justify-center group-hover/sidebar:justify-start group-hover/sidebar:gap-3 group-hover/sidebar:px-3'}`}
                  >
                    <Icon size={18} aria-hidden="true" />
                    <span className={`min-w-0 ${navExpanded ? 'block' : 'hidden group-hover/sidebar:block'}`}>
                      <span className="block truncate font-semibold">{page.label}</span>
                      <span className={`block truncate text-xs ${isActive ? 'text-steel' : 'text-white/45'}`}>{page.detail}</span>
                    </span>
                  </button>
                );
              })}
            </nav>

            <button
              type="button"
              onClick={() => setIsNavPinned((current) => !current)}
              className={`mt-auto flex h-11 w-full items-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-sm font-semibold text-white/72 hover:bg-white/[0.10] hover:text-white ${
                navExpanded ? 'gap-3 px-3 justify-start' : 'justify-center group-hover/sidebar:justify-start group-hover/sidebar:gap-3 group-hover/sidebar:px-3'
              }`}
            >
              {isNavPinned ? <PanelLeftClose size={18} aria-hidden="true" /> : <PanelLeftOpen size={18} aria-hidden="true" />}
              <span className={`${navExpanded ? 'block' : 'hidden group-hover/sidebar:block'}`}>
                {isNavPinned ? 'Unpin rail' : 'Pin rail'}
              </span>
            </button>
          </div>
        </aside>

        <div className={`min-w-0 flex-1 transition-[padding] duration-200 ${isNavPinned ? 'lg:pl-64' : 'lg:pl-20'}`}>
          <div className="sticky top-0 z-20 border-b border-white/35 bg-[linear-gradient(180deg,rgba(67,76,91,0.96),rgba(36,43,55,0.94))] px-4 py-3 text-white shadow-[0_18px_46px_rgba(31,38,50,0.18)] backdrop-blur-xl lg:px-6">
            <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto_1fr] items-center gap-x-3 gap-y-2">
              <div className="flex min-w-0 items-center gap-2">
                <BrandLogo variant="mark" className="h-9 w-9 shrink-0" />
                <span className="hidden text-xs font-semibold uppercase tracking-wide text-white/62 sm:inline">Executive Ops Workbench</span>
              </div>
              <div className="flex justify-center">
                <BrandLogo variant="wordmark" className="h-9" />
              </div>
              <div className="col-span-3 row-start-2 flex min-w-0 justify-center sm:col-span-1 sm:col-start-3 sm:row-start-1 sm:justify-end">
                <StatusIndicator health={healthQuery.data} isLoading={healthQuery.isLoading} error={healthQuery.error} />
              </div>
            </div>
          </div>

          <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 lg:px-6">
            <div className="flex flex-wrap gap-2 lg:hidden">
              {pages.map((page) => {
                const Icon = page.icon;
                return (
                  <button
                    key={page.id}
                    type="button"
                    aria-label={page.label}
                    onClick={() => setActivePage(page.id)}
                    className={`inline-flex min-h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold shadow-sm ${
                      activePage === page.id ? 'border-brandDark bg-brandDark text-white' : 'border-line bg-white/70 text-brandDark'
                    }`}
                  >
                    <Icon size={16} aria-hidden="true" />
                    {page.label}
                  </button>
                );
              })}
            </div>

            {topError ? <ErrorState message={errorMessage(topError, 'FastAPI request failed.')} /> : null}

            {activePage === 'home' ? (
              <HomePage
                activeStep={activeStep}
                calendarContext={calendarContext}
                rules={rules}
                recommendation={recommendation}
                meetingRequest={meetingRequest}
                onOpenAdmin={() => setActivePage('admin')}
              />
            ) : null}

            {activePage === 'admin' ? (
              <AdminCenter
                activeStep={activeStep}
                rawText={rawText}
                onRawTextChange={(value) => {
                  setRawText(value);
                  setValidationError('');
                }}
                onParse={handleParse}
                meetingRequest={meetingRequest}
                isParsing={parseMutation.isPending}
                parseError={parseMutation.error ? errorMessage(parseMutation.error, 'Could not parse request.') : undefined}
                validationError={validationError}
                calendarContext={calendarContext}
                rules={rules}
                recommendation={recommendation}
                onGenerateRecommendation={() => recommendationMutation.mutate()}
                isRecommendationLoading={recommendationMutation.isPending}
                draft={draft}
                onDraftChange={setDraft}
                onGenerateDraft={() => draftMutation.mutate()}
                isDraftLoading={draftMutation.isPending}
                onFeedback={handleFeedback}
                isLogging={logDecisionMutation.isPending}
                onRulesChange={setRules}
                rulesError={rulesQuery.error ? 'FastAPI default rules are unavailable. Starter rules are shown.' : undefined}
                onCalendarChange={setCalendarContext}
                calendarError={calendarQuery.error ? 'FastAPI mock calendar is unavailable. Calendar impact may be incomplete.' : undefined}
                decisionEntries={decisionEntries}
              />
            ) : null}

            {activePage === 'account' ? <AccountPage /> : null}
            {activePage === 'settings' ? <SettingsPage /> : null}
          </div>
        </div>
      </div>
    </main>
  );
}

function BrandLogo({
  variant = 'wordmark',
  className = '',
}: {
  variant?: 'mark' | 'wordmark' | 'inline';
  className?: string;
}) {
  const showText = variant !== 'mark';
  return (
    <div className={`inline-flex items-center gap-2 ${className}`} aria-label="desk.ai">
      <div className="relative flex aspect-square h-full min-h-8 items-center justify-center overflow-hidden rounded-lg border border-white/18 bg-[linear-gradient(145deg,#5d6876,#1e2733_58%,#111821)] shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_12px_30px_rgba(18,24,33,0.28)]">
        <img
          src={brandLogoSrc}
          alt="desk.ai"
          className="h-full w-full object-cover"
        />
      </div>
      {showText ? (
        <span className={`font-bold tracking-tight ${variant === 'inline' ? 'text-xs uppercase text-steel' : 'text-white'}`}>
          desk.ai
        </span>
      ) : null}
    </div>
  );
}

function HomePage({
  activeStep,
  calendarContext,
  rules,
  recommendation,
  meetingRequest,
  onOpenAdmin,
}: {
  activeStep: number;
  calendarContext?: CalendarContext;
  rules: ExecutiveRules;
  recommendation?: Recommendation;
  meetingRequest?: MeetingRequest;
  onOpenAdmin: () => void;
}) {
  return (
    <>
      <section className="relative overflow-hidden rounded-lg border border-white/75 bg-[linear-gradient(145deg,rgba(255,255,255,0.90),rgba(238,241,245,0.70))] shadow-[0_28px_70px_rgba(31,38,50,0.14)] backdrop-blur-xl">
        <div className="absolute inset-x-8 top-0 h-px bg-white/95" aria-hidden="true" />
        <div className="absolute right-0 top-0 h-56 w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.96),transparent_68%)]" aria-hidden="true" />
        <div className="relative grid gap-5 p-4 lg:grid-cols-[minmax(0,1fr)_420px] lg:p-5">
          <div className="min-w-0">
            <div className="inline-flex max-w-full items-center gap-2 rounded-md border border-line/80 bg-white/70 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-brandDark shadow-sm">
              <Building2 size={14} aria-hidden="true" />
              <span className="truncate">Exec command center</span>
            </div>
            <div className="mt-4 max-w-3xl">
              <h2 className="text-[2rem] font-bold leading-tight text-ink md:text-5xl">
                Resolve high-stakes calendar requests from one polished command surface.
              </h2>
              <p className="mt-3 max-w-2xl text-base leading-7 text-steel">
                Home keeps the assistant chat and executive calendar in view. Admin Center holds intake, generation, approvals, and logs.
              </p>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {enterpriseSignals.map((signal) => {
                const Icon = signal.icon;
                return (
                  <div key={signal.label} className="rounded-lg border border-white/80 bg-white/[0.62] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.86),0_10px_24px_rgba(31,38,50,0.08)]">
                    <div className="flex items-center justify-between gap-2 text-steel">
                      <span className="text-xs font-semibold uppercase tracking-wide">{signal.label}</span>
                      <Icon size={15} aria-hidden="true" />
                    </div>
                    <div className="mt-2 text-2xl font-bold text-ink">{signal.value}</div>
                    <div className="text-xs font-medium text-steel">{signal.detail}</div>
                  </div>
                );
              })}
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-steel">
              <span className="mr-1 text-brandDark">Trusted workflow pattern</span>
              {trustMarks.map((mark) => (
                <span key={mark} className="rounded-md border border-line/80 bg-white/[0.58] px-2.5 py-1 shadow-sm">
                  {mark}
                </span>
              ))}
            </div>
          </div>

          <LiveDecisionCanvas activeStep={activeStep} />
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.82fr)_minmax(420px,1fr)]">
        <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
          <div className="flex min-h-14 items-center justify-between gap-3 border-b border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.74),rgba(255,255,255,0.44))] px-4 py-3">
            <div className="flex items-center gap-2">
              <MessageSquare size={18} className="text-brandDark" aria-hidden="true" />
              <h2 className="text-base font-semibold text-ink">Command chat</h2>
            </div>
            <button
              type="button"
              onClick={onOpenAdmin}
              className="rounded-md border border-line bg-white/75 px-3 py-2 text-sm font-semibold text-brandDark shadow-sm hover:bg-brandSoft"
            >
              Open Admin Center
            </button>
          </div>
          <div className="space-y-4 p-4">
            <div className="rounded-lg border border-line bg-white/58 p-3 shadow-sm">
              <BrandLogo variant="inline" className="h-5" />
              <p className="mt-2 text-sm leading-6 text-ink">
                I can help triage inbound meeting requests, explain calendar conflicts, and prepare auditable replies. Operational actions live in Admin Center.
              </p>
            </div>
            <div className="space-y-2">
              {commandPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={onOpenAdmin}
                  className="flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-white/65 px-3 py-3 text-left text-sm text-brandDark shadow-sm hover:bg-white"
                >
                  <span>{prompt}</span>
                  <Route size={15} aria-hidden="true" />
                </button>
              ))}
            </div>
            <textarea
              aria-label="Command chat message"
              className="min-h-28 w-full resize-y rounded-md border border-line bg-white/80 px-3 py-2 text-sm shadow-inner"
              placeholder="Ask desk.ai what needs attention before you open the admin workflow."
            />
          </div>
        </section>

        <WorkWeekCalendar
          calendar={calendarContext}
          rules={rules}
          recommendation={recommendation}
          meetingRequest={meetingRequest}
        />
      </div>
    </>
  );
}

function AdminCenter({
  activeStep,
  rawText,
  onRawTextChange,
  onParse,
  meetingRequest,
  isParsing,
  parseError,
  validationError,
  calendarContext,
  rules,
  recommendation,
  onGenerateRecommendation,
  isRecommendationLoading,
  draft,
  onDraftChange,
  onGenerateDraft,
  isDraftLoading,
  onFeedback,
  isLogging,
  onRulesChange,
  rulesError,
  onCalendarChange,
  calendarError,
  decisionEntries,
}: {
  activeStep: number;
  rawText: string;
  onRawTextChange: (value: string) => void;
  onParse: () => void;
  meetingRequest?: MeetingRequest;
  isParsing: boolean;
  parseError?: string;
  validationError?: string;
  calendarContext?: CalendarContext;
  rules: ExecutiveRules;
  recommendation?: Recommendation;
  onGenerateRecommendation: () => void;
  isRecommendationLoading: boolean;
  draft?: DraftResponse;
  onDraftChange: (draft: DraftResponse) => void;
  onGenerateDraft: () => void;
  isDraftLoading: boolean;
  onFeedback: (decision: FeedbackDecision, notes: string) => void;
  isLogging: boolean;
  onRulesChange: (rules: ExecutiveRules) => void;
  rulesError?: string;
  onCalendarChange: (calendar: CalendarContext) => void;
  calendarError?: string;
  decisionEntries: DecisionLogEntry[];
}) {
  return (
    <>
      <section className="rounded-lg border border-white/70 bg-white/55 p-4 shadow-[0_18px_44px_rgba(31,38,50,0.10)] backdrop-blur-md">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-line bg-white/80 text-brandDark shadow-sm">
              <Sparkles size={18} aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">Admin Center</h2>
              <p className="mt-1 max-w-2xl text-sm text-steel">
                The operational workspace for intake, recommendations, draft generation, feedback, rules, calendar assumptions, and audit logs.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-line bg-white/70 px-3 py-2 text-sm text-steel shadow-sm">
            <FileText size={16} aria-hidden="true" />
            <span>Every AI step is logged for audit.</span>
          </div>
        </div>
        <WorkflowStepper activeStep={activeStep} />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="min-w-0 space-y-5">
          <RequestIntakePanel
            rawText={rawText}
            onRawTextChange={onRawTextChange}
            onParse={onParse}
            parsedRequest={meetingRequest}
            isParsing={isParsing}
            error={parseError}
            validationError={validationError}
          />
          <RecommendationCard
            recommendation={recommendation}
            rules={rules}
            onGenerate={onGenerateRecommendation}
            disabled={!meetingRequest}
            isLoading={isRecommendationLoading}
          />
          <DraftResponsePanel
            draft={draft}
            onDraftChange={onDraftChange}
            onGenerate={onGenerateDraft}
            disabled={!meetingRequest || !recommendation}
            isLoading={isDraftLoading}
          />
          <DecisionFeedbackControls
            onSubmit={onFeedback}
            disabled={!meetingRequest || !recommendation}
            isLogging={isLogging}
          />
        </div>

        <aside className="min-w-0 space-y-5">
          <ExecutiveRulesPanel rules={rules} onChange={onRulesChange} error={rulesError} />
          <CalendarContextPanel
            calendar={calendarContext}
            onChange={onCalendarChange}
            meetingRequest={meetingRequest}
            error={calendarError}
          />
          <DecisionLogView entries={decisionEntries} />
        </aside>
      </div>
    </>
  );
}

function LiveDecisionCanvas({ activeStep }: { activeStep: number }) {
  return (
    <div className="min-w-0 rounded-lg border border-[#c9ced7] bg-[#151a22] p-3 text-white shadow-[0_24px_60px_rgba(22,26,34,0.30)]">
      <div className="flex min-w-0 items-center justify-between gap-2 border-b border-white/10 pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white/10">
            <Workflow size={17} aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold">Live decision canvas</div>
            <div className="text-xs text-white/[0.58]">Intake, policy, calendar, response</div>
          </div>
        </div>
        <span className="hidden shrink-0 rounded-md border border-white/10 bg-white/[0.08] px-2 py-1 text-xs font-semibold text-white/[0.76] sm:inline-flex">
          Review mode
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {workflowSteps.map((step, index) => {
          const Icon = step.icon;
          const isComplete = activeStep > index;
          const isCurrent = activeStep === index;
          return (
            <div
              key={step.label}
              className={`flex min-w-0 items-center gap-3 rounded-md border px-3 py-2 ${
                isComplete || isCurrent ? 'border-white/[0.18] bg-white/[0.12]' : 'border-white/[0.08] bg-white/[0.04]'
              }`}
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-md ${isComplete ? 'bg-white text-brandDark' : 'bg-white/10 text-white/[0.82]'}`}>
                <Icon size={15} aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{step.label}</div>
                <div className="truncate text-xs text-white/[0.56]">{step.detail}</div>
              </div>
              <div className={`h-2 w-2 rounded-full ${isComplete || isCurrent ? 'bg-white' : 'bg-white/[0.22]'}`} />
            </div>
          );
        })}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-md border border-white/[0.08] bg-white/[0.05] p-2">
          <div className="font-semibold text-white">SSO</div>
          <div className="mt-1 text-white/50">ready</div>
        </div>
        <div className="rounded-md border border-white/[0.08] bg-white/[0.05] p-2">
          <div className="font-semibold text-white">SOC 2</div>
          <div className="mt-1 text-white/50">aligned</div>
        </div>
        <div className="rounded-md border border-white/[0.08] bg-white/[0.05] p-2">
          <div className="font-semibold text-white">Logs</div>
          <div className="mt-1 text-white/50">complete</div>
        </div>
      </div>
    </div>
  );
}

function WorkflowStepper({ activeStep }: { activeStep: number }) {
  return (
    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {workflowSteps.map((step, index) => {
        const Icon = step.icon;
        const isComplete = activeStep > index;
        const isCurrent = activeStep === index;
        return (
          <div
            key={step.label}
            className={`rounded-lg border px-3 py-3 shadow-sm ${
              isComplete || isCurrent ? 'border-[#b9c0ca] bg-white/80' : 'border-white/70 bg-white/45'
            }`}
          >
            <div className="flex items-center gap-2">
              <div className={`flex h-8 w-8 items-center justify-center rounded-md ${isComplete ? 'bg-brandDark text-white' : 'border border-line bg-white/75 text-brand'}`}>
                <Icon size={16} aria-hidden="true" />
              </div>
              <div className="text-sm font-semibold text-ink">{step.label}</div>
            </div>
            <p className="mt-2 text-sm text-steel">{step.detail}</p>
          </div>
        );
      })}
    </div>
  );
}

function AccountPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
        <div className="border-b border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.74),rgba(255,255,255,0.44))] px-4 py-4">
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-steel">
            <CreditCard size={17} aria-hidden="true" />
            Account and subscription
          </div>
          <h2 className="mt-2 text-2xl font-bold text-ink">Enterprise plan for Northstar Customer Ops</h2>
        </div>
        <div className="grid gap-3 p-4 md:grid-cols-3">
          <MetricCard label="Seats" value="42 / 60" detail="18 available" />
          <MetricCard label="Monthly usage" value="71%" detail="18.4k AI actions" />
          <MetricCard label="Renewal" value="Nov 15" detail="annual agreement" />
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
        <div className="border-b border-line/80 bg-white/50 px-4 py-4">
          <h2 className="text-base font-semibold text-ink">Billing contacts</h2>
        </div>
        <div className="space-y-3 p-4 text-sm">
          <InfoRow label="Owner" value="Dana Lee, VP Executive Operations" />
          <InfoRow label="Billing admin" value="Priya Shah, Finance Operations" />
          <InfoRow label="Invoice email" value="ap@northstar-ops.example" />
          <InfoRow label="Support tier" value="Enterprise, 24/7 priority" />
        </div>
      </section>

      <section className="xl:col-span-2 overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
        <div className="border-b border-line/80 bg-white/50 px-4 py-4">
          <h2 className="text-base font-semibold text-ink">Usage by workspace</h2>
        </div>
        <div className="grid gap-3 p-4 md:grid-cols-3">
          <MetricCard label="Executive office" value="8.2k" detail="AI actions" />
          <MetricCard label="Customer escalations" value="6.1k" detail="AI actions" />
          <MetricCard label="Board operations" value="4.1k" detail="AI actions" />
        </div>
      </section>
    </div>
  );
}

function SettingsPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <SettingsSection
        icon={KeyRound}
        title="Security controls"
        items={[
          ['SSO provider', 'Okta SAML enforced'],
          ['Session policy', '12 hour expiry, device trust required'],
          ['Data retention', 'Decision logs retained for 365 days'],
        ]}
      />
      <SettingsSection
        icon={SlidersHorizontal}
        title="AI governance"
        items={[
          ['Autonomy level', 'Draft and recommend only'],
          ['Calendar write access', 'Disabled for V0'],
          ['Sensitive context', 'Redaction before model calls'],
        ]}
      />
      <SettingsSection
        icon={Bell}
        title="Notifications"
        items={[
          ['Escalation alerts', 'High-risk requests notify admins'],
          ['Daily digest', 'Sent at 4:30 PM Pacific'],
          ['Audit export', 'Weekly CSV to compliance folder'],
        ]}
      />
      <SettingsSection
        icon={Users}
        title="Team permissions"
        items={[
          ['Assistants', 'Can parse, draft, and submit feedback'],
          ['Admins', 'Can edit rules and calendar assumptions'],
          ['Executives', 'Read-only approvals dashboard'],
        ]}
      />
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border border-white/80 bg-white/[0.62] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.86),0_10px_24px_rgba(31,38,50,0.08)]">
      <div className="text-xs font-semibold uppercase tracking-wide text-steel">{label}</div>
      <div className="mt-2 text-2xl font-bold text-ink">{value}</div>
      <div className="text-xs font-medium text-steel">{detail}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-md border border-line bg-white/58 px-3 py-2">
      <span className="font-semibold text-steel">{label}</span>
      <span className="text-right text-ink">{value}</span>
    </div>
  );
}

function SettingsSection({
  icon: Icon,
  title,
  items,
}: {
  icon: LucideIcon;
  title: string;
  items: [string, string][];
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
      <div className="flex items-center gap-2 border-b border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.74),rgba(255,255,255,0.44))] px-4 py-4">
        <Icon size={18} className="text-brandDark" aria-hidden="true" />
        <h2 className="text-base font-semibold text-ink">{title}</h2>
      </div>
      <div className="space-y-3 p-4 text-sm">
        {items.map(([label, value]) => (
          <InfoRow key={label} label={label} value={value} />
        ))}
      </div>
    </section>
  );
}

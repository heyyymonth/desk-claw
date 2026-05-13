import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Bell,
  Building2,
  CreditCard,
  FileText,
  Gauge,
  KeyRound,
  LogOut,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Route,
  SlidersHorizontal,
  Sparkles,
  UserCircle,
  UserPen,
  Users,
  Workflow,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { AiTechnicalDashboardPage } from './components/AiTechnicalDashboard';
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
import {
  brandLogoSrc,
  commandPrompts,
  enterpriseSignals,
  pages,
  personas,
  starterRules,
  trustMarks,
  workflowSteps,
  type PageId,
  type PersonaId,
} from './config/appConfig';
import { api, setActorIdentity } from './lib/api';
import type {
  CalendarContext,
  DecisionLogEntry,
  DraftResponse,
  ExecutiveRules,
  FeedbackDecision,
  MeetingRequest,
  Recommendation,
} from './types';

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function App() {
  const [activePage, setActivePage] = useState<PageId>('home');
  const [activePersona, setActivePersona] = useState<PersonaId>('executive_assistant');
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
      return api.recommendation(meetingRequest, rules, calendarContext);
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
  const currentPersona = personas[activePersona];

  useEffect(() => {
    setActorIdentity({
      actorId: currentPersona.id,
      email: currentPersona.email,
      name: currentPersona.name,
    });
  }, [currentPersona]);

  return (
    <main className="min-h-screen">
      <div className="flex min-h-screen">
        <aside
          className={`group/sidebar fixed inset-y-0 left-0 z-30 hidden border-r border-white/20 bg-[linear-gradient(180deg,#303947,#202735)] text-white shadow-[12px_0_36px_rgba(31,38,50,0.16)] transition-[width] duration-300 ease-out lg:block ${
            isNavPinned ? 'w-60' : 'w-16 hover:w-60'
          }`}
        >
          <div className={`flex h-full flex-col ${isNavPinned ? 'p-2.5' : 'px-2.5 py-2.5 group-hover/sidebar:p-2.5'}`}>
            <div className="flex min-h-12 items-center gap-3 border-b border-white/10 pb-2.5">
              <BrandLogo variant="mark" className="h-9 w-9 shrink-0" />
              <div className={`min-w-0 ${navExpanded ? 'block' : 'hidden group-hover/sidebar:block'}`}>
                <div className="font-bold leading-tight text-white">desk.ai</div>
                <div className="text-xs text-white/52">Ops command suite</div>
              </div>
            </div>

            <nav className="mt-3 space-y-1.5" aria-label="Primary pages">
              {pages.map((page) => {
                const Icon = page.icon;
                const isActive = activePage === page.id;
                return (
                  <button
                    key={page.id}
                    type="button"
                    aria-label={page.label}
                    onClick={() => setActivePage(page.id)}
                    className={`flex h-10 w-full items-center rounded-md border text-left text-sm transition-colors duration-200 ${
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
              className={`mt-auto flex h-10 w-full items-center rounded-md border border-white/[0.08] bg-white/[0.04] text-sm font-semibold text-white/72 transition-colors duration-200 hover:bg-white/[0.10] hover:text-white ${
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

        <div className={`min-w-0 flex-1 transition-[padding] duration-300 ease-out ${isNavPinned ? 'lg:pl-60' : 'lg:pl-16'}`}>
          <div className="sticky top-0 z-20 border-b border-white/25 bg-[linear-gradient(180deg,rgba(61,70,84,0.94),rgba(35,42,54,0.92))] px-4 py-1.5 text-white shadow-[0_8px_24px_rgba(31,38,50,0.12)] backdrop-blur-xl lg:px-6">
            <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto_1fr] items-center gap-x-3 gap-y-1.5">
              <div className="flex min-w-0 items-center gap-2">
                <BrandLogo variant="mark" className="h-7 w-7 shrink-0" />
                <span className="hidden text-xs font-semibold uppercase tracking-wide text-white/62 sm:inline">Executive Ops Workbench</span>
                <span className="hidden rounded-md border border-white/15 bg-white/10 px-2 py-1 text-xs font-semibold text-white/76 md:inline-flex">
                  {currentPersona.label}
                </span>
              </div>
              <div className="flex justify-center">
                <BrandLogo variant="wordmark" className="h-7" />
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

            {activePage === 'telemetry' ? <AiTechnicalDashboardPage /> : null}

            {activePage === 'account' ? (
              <AccountPage activePersona={activePersona} onPersonaChange={setActivePersona} />
            ) : null}
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
      <section className="relative overflow-hidden rounded-lg border border-white/70 bg-[linear-gradient(145deg,rgba(245,247,250,0.84),rgba(225,230,237,0.70))] shadow-[0_24px_62px_rgba(31,38,50,0.12)] backdrop-blur-xl">
        <div className="absolute inset-x-8 top-0 h-px bg-white/80" aria-hidden="true" />
        <div className="absolute right-0 top-0 h-56 w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.72),transparent_68%)]" aria-hidden="true" />
        <div className="relative grid gap-5 p-4 lg:grid-cols-[minmax(0,1fr)_420px] lg:p-5">
          <div className="min-w-0">
            <div className="inline-flex max-w-full items-center gap-2 rounded-md border border-line/80 bg-white/55 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-brandDark shadow-sm">
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
                  <div key={signal.label} className="rounded-lg border border-white/70 bg-white/[0.48] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.72),0_10px_24px_rgba(31,38,50,0.06)]">
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
                  <span key={mark} className="rounded-md border border-line/75 bg-white/[0.46] px-2.5 py-1 shadow-sm">
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
    <div className="min-w-0 rounded-lg border border-[#c8ced7] bg-[linear-gradient(180deg,#edf0f4,#d9dee6)] p-3 text-ink shadow-[0_18px_44px_rgba(31,38,50,0.12)]">
      <div className="flex min-w-0 items-center justify-between gap-2 border-b border-[#c2c8d2] pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-white/70 bg-white/58 text-brandDark shadow-sm">
            <Workflow size={17} aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold">Live decision canvas</div>
            <div className="text-xs text-steel">Intake, policy, calendar, response</div>
          </div>
        </div>
        <span className="hidden shrink-0 rounded-md border border-line bg-white/58 px-2 py-1 text-xs font-semibold text-brandDark shadow-sm sm:inline-flex">
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
                isComplete || isCurrent ? 'border-[#aeb6c2] bg-white/70' : 'border-[#c6ccd5] bg-white/40'
              }`}
            >
              <div className={`flex h-8 w-8 items-center justify-center rounded-md ${isComplete ? 'bg-brandDark text-white' : 'border border-line bg-white/60 text-brandDark'}`}>
                <Icon size={15} aria-hidden="true" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold">{step.label}</div>
                <div className="truncate text-xs text-steel">{step.detail}</div>
              </div>
              <div className={`h-2 w-2 rounded-full ${isComplete || isCurrent ? 'bg-brandDark' : 'bg-[#9aa3af]'}`} />
            </div>
          );
        })}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-md border border-[#c6ccd5] bg-white/42 p-2">
          <div className="font-semibold text-ink">SSO</div>
          <div className="mt-1 text-steel">ready</div>
        </div>
        <div className="rounded-md border border-[#c6ccd5] bg-white/42 p-2">
          <div className="font-semibold text-ink">SOC 2</div>
          <div className="mt-1 text-steel">aligned</div>
        </div>
        <div className="rounded-md border border-[#c6ccd5] bg-white/42 p-2">
          <div className="font-semibold text-ink">Logs</div>
          <div className="mt-1 text-steel">complete</div>
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

function AccountPage({
  activePersona,
  onPersonaChange,
}: {
  activePersona: PersonaId;
  onPersonaChange: (persona: PersonaId) => void;
}) {
  const persona = personas[activePersona];
  const [profile, setProfile] = useState(persona);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const signOutMutation = useMutation({
    mutationFn: api.signOut,
  });
  const isAdmin = activePersona === 'admin';

  useEffect(() => {
    setProfile(personas[activePersona]);
    setIsEditingProfile(false);
  }, [activePersona]);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
        <div className="flex flex-col justify-between gap-4 border-b border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.74),rgba(255,255,255,0.44))] px-4 py-4 md:flex-row md:items-center">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border border-line bg-white/70 text-brandDark shadow-sm">
              <UserCircle size={26} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold uppercase tracking-wide text-steel">{persona.eyebrow}</div>
              <h2 className="mt-1 truncate text-2xl font-bold text-ink">{profile.name}</h2>
              <p className="mt-1 text-sm text-steel">{profile.title}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Persona view"
              value={activePersona}
              onChange={(event) => onPersonaChange(event.target.value as PersonaId)}
              className="min-h-10 rounded-md border border-line bg-white/75 px-3 text-sm font-semibold text-brandDark shadow-sm"
            >
              <option value="executive_assistant">Executive Assistant</option>
              <option value="admin">Workspace Admin</option>
            </select>
            <button
              type="button"
              onClick={() => signOutMutation.mutate()}
              className="inline-flex min-h-10 items-center justify-center rounded-md border border-line bg-white/75 px-3 text-sm font-semibold text-brandDark shadow-sm hover:bg-brandSoft"
            >
              <LogOut className="mr-2" size={16} aria-hidden="true" />
              Sign out
            </button>
          </div>
        </div>
        <div className="grid gap-3 p-4 text-sm md:grid-cols-2">
          <InfoRow label="Email" value={profile.email} />
          <InfoRow label="Phone" value={profile.phone} />
          <InfoRow label="Timezone" value={profile.timezone} />
          <InfoRow label="Role" value={profile.role} />
          <InfoRow label="Access level" value={profile.accessLevel} />
          <InfoRow label="Last active" value={profile.lastActive} />
        </div>
        <div className="border-t border-line/80 px-4 py-3 text-sm text-steel">
          {signOutMutation.isPending
            ? 'Sign-out request sent to backend.'
            : signOutMutation.isError
              ? 'Backend sign-out endpoint is linked, but not implemented yet.'
              : 'Sign out is wired to the backend endpoint. Session handling will be completed with login/onboarding.'}
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
        <div className="flex items-center justify-between gap-3 border-b border-line/80 bg-white/50 px-4 py-4">
          <div className="flex items-center gap-2">
            <UserPen size={18} className="text-brandDark" aria-hidden="true" />
            <h2 className="text-base font-semibold text-ink">Profile details</h2>
          </div>
          <button
            type="button"
            onClick={() => setIsEditingProfile((current) => !current)}
            className="rounded-md border border-line bg-white/75 px-3 py-2 text-sm font-semibold text-brandDark shadow-sm hover:bg-brandSoft"
          >
            {isEditingProfile ? 'Done' : 'Change profile'}
          </button>
        </div>
        <div className="space-y-3 p-4 text-sm">
          <ProfileField label="Display name" value={profile.name} disabled={!isEditingProfile} onChange={(name) => setProfile((current) => ({ ...current, name }))} />
          <ProfileField label="Title" value={profile.title} disabled={!isEditingProfile} onChange={(title) => setProfile((current) => ({ ...current, title }))} />
          <ProfileField label="Email" value={profile.email} disabled={!isEditingProfile} onChange={(email) => setProfile((current) => ({ ...current, email }))} />
          <ProfileField label="Phone" value={profile.phone} disabled={!isEditingProfile} onChange={(phone) => setProfile((current) => ({ ...current, phone }))} />
        </div>
      </section>

      {isAdmin ? (
        <>
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

          <section className="xl:col-span-2 overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
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
        </>
      ) : null}

      <section className="xl:col-span-2 overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
        <div className="border-b border-line/80 bg-white/50 px-4 py-4">
          <h2 className="text-base font-semibold text-ink">
            {isAdmin ? 'Usage by workspace' : 'Scheduling workspace'}
          </h2>
        </div>
        <div className="grid gap-3 p-4 md:grid-cols-3">
          {isAdmin ? (
            <>
              <MetricCard label="Executive office" value="8.2k" detail="AI actions" />
              <MetricCard label="Customer escalations" value="6.1k" detail="AI actions" />
              <MetricCard label="Board operations" value="4.1k" detail="AI actions" />
            </>
          ) : (
            <>
              <MetricCard label="Pending requests" value="14" detail="need scheduling review" />
              <MetricCard label="Scheduled this week" value="27" detail="meetings coordinated" />
              <MetricCard label="Protected blocks kept" value="96%" detail="focus time preserved" />
            </>
          )}
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

function ProfileField({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-semibold uppercase tracking-wide text-steel">{label}</span>
      <input
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-line bg-white/70 px-3 py-2 text-sm text-ink shadow-inner disabled:bg-white/40 disabled:text-steel"
      />
    </label>
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

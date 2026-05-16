import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertCircle, ArrowRight, CheckCircle2, Loader2, Send, Sparkles } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { api } from './lib/api';
import type { DraftResponse, MeetingRequest, Recommendation } from './types';

const sampleRequest =
  'From Jordan at Atlas Finance: can Dana meet for 30 minutes next Tuesday afternoon to discuss renewal risk? Please include Priya from Legal if possible.';

function message(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function App() {
  const [rawText, setRawText] = useState(sampleRequest);
  const [parsed, setParsed] = useState<MeetingRequest>();
  const [recommendation, setRecommendation] = useState<Recommendation>();
  const [draft, setDraft] = useState<DraftResponse>();
  const [nextSteps, setNextSteps] = useState<string[]>([]);

  const healthQuery = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15000 });

  const runMutation = useMutation({
    mutationFn: async () => {
      if (!rawText.trim()) {
        throw new Error('Paste an incoming scheduling request first.');
      }
      return api.parseRequest(rawText);
    },
    onMutate: () => {
      setParsed(undefined);
      setRecommendation(undefined);
      setDraft(undefined);
      setNextSteps([]);
    },
    onSuccess: (response) => {
      setParsed(response.parsed_request);
      setRecommendation(response.recommendation);
      setDraft(response.draft_response);
      setNextSteps(response.next_steps);
    },
  });

  const isRunning = runMutation.isPending;
  const provider = healthQuery.data?.model_provider ?? 'unknown';
  const model = healthQuery.data?.model ?? 'unknown';

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#eef2f5,#dfe5eb)] text-ink">
      <section className="mx-auto flex min-h-screen max-w-6xl flex-col gap-5 px-4 py-6 md:px-6">
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/70 bg-white/70 px-4 py-3 shadow-sm backdrop-blur">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold uppercase text-steel">
              <Sparkles size={16} aria-hidden="true" />
              Native agent request router
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Incoming request to next step</h1>
          </div>
          <div className="rounded-md border border-line bg-white/80 px-3 py-2 text-sm text-steel">
            {provider}/{model} · Web Backend
          </div>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section className="rounded-lg border border-white/75 bg-white/72 p-4 shadow-sm backdrop-blur">
            <label htmlFor="incoming-request" className="text-sm font-semibold text-ink">
              Incoming request
            </label>
            <textarea
              id="incoming-request"
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              rows={12}
              className="mt-2 w-full resize-none rounded-md border border-line bg-white px-3 py-3 text-sm leading-6 text-ink shadow-inner outline-none focus:border-brand"
            />
            <button
              type="button"
              onClick={() => runMutation.mutate()}
              disabled={isRunning}
              className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-md bg-brand px-4 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRunning ? <Loader2 size={17} className="animate-spin" aria-hidden="true" /> : <Send size={17} aria-hidden="true" />}
              Run agent
            </button>
            {runMutation.error ? (
              <div role="alert" className="mt-3 flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <AlertCircle size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
                <div>
                  <div className="font-semibold">Model offline</div>
                  <div>{message(runMutation.error, 'Check with your admin before running this request.')}</div>
                </div>
              </div>
            ) : null}
          </section>

          <section className="space-y-4">
            <ResultBlock title="Parsed intent" empty={!parsed} emptyText="Run the agent to parse the request.">
              {parsed ? (
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <Field label="Title" value={parsed.intent.title} />
                  <Field label="Requester" value={parsed.intent.requester} />
                  <Field label="Priority" value={parsed.intent.priority} />
                  <Field label="Duration" value={`${parsed.intent.duration_minutes} minutes`} />
                  <Field label="Attendees" value={parsed.intent.attendees.join(', ') || 'None provided'} />
                  <Field label="Missing" value={parsed.intent.missing_fields.join(', ') || 'None'} />
                </dl>
              ) : null}
            </ResultBlock>

            <ResultBlock title="Next step" empty={!recommendation} emptyText="Recommendation will appear after parsing.">
              {recommendation ? (
                <div className="space-y-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md border border-line bg-white px-2 py-1 font-semibold text-brandDark">{recommendation.decision}</span>
                    <span className="text-steel">{Math.round(recommendation.confidence * 100)}% confidence</span>
                  </div>
                  <ul className="space-y-1">
                    {recommendation.rationale.map((item) => (
                      <li key={item} className="flex gap-2">
                        <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-700" aria-hidden="true" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="rounded-md border border-line bg-white/76 p-3">
                    <div className="text-xs font-semibold uppercase text-steel">Recommended next steps</div>
                    <ul className="mt-2 space-y-1">
                      {nextSteps.map((step) => (
                        <li key={step} className="flex gap-2">
                          <ArrowRight size={15} className="mt-0.5 shrink-0 text-brandDark" aria-hidden="true" />
                          <span>{step}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ) : null}
            </ResultBlock>

            <ResultBlock title="Response draft" empty={!draft} emptyText="Draft response will appear after the next step.">
              {draft ? (
                <div className="space-y-2 text-sm">
                  <div className="font-semibold text-ink">{draft.subject}</div>
                  <p className="rounded-md border border-line bg-white/80 p-3 leading-6">{draft.body}</p>
                </div>
              ) : null}
            </ResultBlock>
          </section>
        </div>
      </section>
    </main>
  );
}

function ResultBlock({
  title,
  empty,
  emptyText,
  children,
}: {
  title: string;
  empty: boolean;
  emptyText: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-white/75 bg-white/72 p-4 shadow-sm backdrop-blur">
      <div className="mb-3 flex items-center gap-2 text-base font-semibold text-ink">
        <ArrowRight size={17} className="text-brandDark" aria-hidden="true" />
        {title}
      </div>
      {empty ? <div className="rounded-md border border-dashed border-line px-3 py-5 text-sm text-steel">{emptyText}</div> : children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-white/76 px-3 py-2">
      <dt className="text-xs font-semibold uppercase text-steel">{label}</dt>
      <dd className="mt-1 break-words text-ink">{value}</dd>
    </div>
  );
}

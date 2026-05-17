import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  Loader2,
  Play,
  Save,
  Server,
  XCircle,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from './lib/api';
import type { EvalCase, EvalCaseResult, EvalRun } from './types';

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value));
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function summarizeFailures(run?: EvalRun) {
  if (!run?.results?.length) {
    return 'No completed run';
  }
  const counts = new Map<string, number>();
  for (const result of run.results) {
    for (const diff of result.diffs) {
      if (!diff.passed) {
        counts.set(diff.field, (counts.get(diff.field) ?? 0) + 1);
      }
    }
  }
  if (!counts.size) {
    return 'All tracked fields passed';
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([field, count]) => `${field} (${count})`)
    .join(', ');
}

function latestProvider(run?: EvalRun) {
  const result = run?.results?.find((item) => item.provider || item.model);
  if (!result) {
    return 'Not run yet';
  }
  return `${result.provider ?? 'unknown'} / ${result.model ?? 'unknown'}`;
}

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export function App() {
  const queryClient = useQueryClient();
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [draftCase, setDraftCase] = useState<EvalCase | null>(null);
  const [expectedJson, setExpectedJson] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);

  const casesQuery = useQuery({ queryKey: ['eval-cases'], queryFn: api.cases });
  const runsQuery = useQuery({ queryKey: ['eval-runs'], queryFn: api.runs, refetchInterval: 15000 });
  const latestRunId = currentRunId ?? runsQuery.data?.[0]?.id;
  const runQuery = useQuery({
    queryKey: ['eval-run', latestRunId],
    queryFn: () => api.run(latestRunId as string),
    enabled: Boolean(latestRunId),
    refetchInterval: 15000,
  });

  const cases = useMemo(() => casesQuery.data ?? [], [casesQuery.data]);
  const latestRun = runQuery.data;
  const selectedCase = useMemo(() => {
    return cases.find((item) => item.id === selectedCaseId) ?? cases[0] ?? null;
  }, [cases, selectedCaseId]);
  const selectedResult = useMemo(() => {
    if (selectedResultId && latestRun?.results) {
      return latestRun.results.find((item) => item.id === selectedResultId) ?? null;
    }
    if (selectedCase?.id && latestRun?.results) {
      return latestRun.results.find((item) => item.case_id === selectedCase.id) ?? null;
    }
    return latestRun?.results?.[0] ?? null;
  }, [latestRun, selectedCase?.id, selectedResultId]);

  useEffect(() => {
    if (!selectedCaseId && cases[0]) {
      setSelectedCaseId(cases[0].id);
    }
  }, [cases, selectedCaseId]);

  useEffect(() => {
    if (!selectedCase) {
      setDraftCase(null);
      setExpectedJson('');
      return;
    }
    setDraftCase(selectedCase);
    setExpectedJson(pretty(selectedCase.expected));
    setJsonError(null);
    setSelectedResultId(null);
  }, [selectedCase]);

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!draftCase) {
        throw new Error('Select a case before saving.');
      }
      const expected = JSON.parse(expectedJson) as EvalCase['expected'];
      return api.updateCase({ ...draftCase, expected });
    },
    onSuccess: async (updated) => {
      setJsonError(null);
      setSelectedCaseId(updated.id);
      await queryClient.invalidateQueries({ queryKey: ['eval-cases'] });
    },
    onError: (error) => {
      if (error instanceof SyntaxError) {
        setJsonError(error.message);
      }
    },
  });

  const runMutation = useMutation({
    mutationFn: api.runEvals,
    onSuccess: async (run) => {
      setCurrentRunId(run.id);
      await queryClient.invalidateQueries({ queryKey: ['eval-runs'] });
      queryClient.setQueryData(['eval-run', run.id], run);
      const firstFailure = run.results?.find((item) => !item.passed) ?? run.results?.[0];
      setSelectedResultId(firstFailure?.id ?? null);
    },
  });

  const activeCount = cases.filter((item) => item.active).length;
  const avgLatency = latestRun?.avg_latency_ms == null ? 'Not run' : `${Math.round(latestRun.avg_latency_ms)} ms`;

  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#eef2f5,#dfe5eb)] text-ink">
      <section className="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 px-4 py-6 md:px-6">
        <header className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/70 bg-white/75 px-4 py-3 shadow-sm backdrop-blur">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold uppercase text-steel">
              <BarChart3 size={16} aria-hidden="true" />
              Eval benchmark dashboard
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Meeting parser performance</h1>
          </div>
          <button
            type="button"
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || activeCount === 0}
            className="inline-flex min-h-11 items-center gap-2 rounded-md bg-brand px-4 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            {runMutation.isPending ? <Loader2 size={17} className="animate-spin" aria-hidden="true" /> : <Play size={17} aria-hidden="true" />}
            Run {activeCount} active cases
          </button>
        </header>

        <section className="grid gap-4 md:grid-cols-4">
          <MetricCard icon={<CheckCircle2 size={18} />} label="Pass rate" value={latestRun ? formatPercent(latestRun.pass_rate) : 'No run'} />
          <MetricCard icon={<Clock3 size={18} />} label="Average latency" value={avgLatency} />
          <MetricCard icon={<AlertCircle size={18} />} label="Failed fields" value={summarizeFailures(latestRun)} />
          <MetricCard icon={<Server size={18} />} label="Latest provider" value={latestProvider(latestRun)} />
        </section>

        {(casesQuery.error || runsQuery.error || runMutation.error || updateMutation.error || jsonError) && (
          <div role="alert" className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <AlertCircle size={17} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>{jsonError ?? errorMessage(casesQuery.error ?? runsQuery.error ?? runMutation.error ?? updateMutation.error)}</span>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <section className="overflow-hidden rounded-lg border border-white/75 bg-white/72 shadow-sm backdrop-blur">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="font-semibold text-ink">Benchmark cases</div>
              <div className="text-sm text-steel">{cases.length} total</div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse text-left text-sm">
                <thead className="bg-brandSoft text-xs uppercase text-steel">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Case</th>
                    <th className="px-4 py-3 font-semibold">Expected</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((caseItem) => {
                    const result = latestRun?.results?.find((item) => item.case_id === caseItem.id);
                    const selected = selectedCase?.id === caseItem.id;
                    return (
                      <tr
                        key={caseItem.id}
                        className={`cursor-pointer border-t border-line ${selected ? 'bg-white' : 'bg-white/45 hover:bg-white/70'}`}
                        onClick={() => setSelectedCaseId(caseItem.id)}
                      >
                        <td className="px-4 py-3 align-top">
                          <div className="font-semibold text-ink">{caseItem.name}</div>
                          <div className="mt-1 line-clamp-2 max-w-xl text-steel">{caseItem.prompt}</div>
                        </td>
                        <td className="px-4 py-3 align-top text-steel">
                          <div>{caseItem.expected.requester}</div>
                          <div>{caseItem.expected.duration_minutes} min · {caseItem.expected.priority}</div>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <StatusBadge result={result} />
                        </td>
                        <td className="px-4 py-3 align-top text-steel">
                          {result?.latency_ms == null ? 'Not run' : `${result.latency_ms} ms`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-lg border border-white/75 bg-white/72 p-4 shadow-sm backdrop-blur">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="font-semibold text-ink">Edit selected case</div>
                <button
                  type="button"
                  onClick={() => updateMutation.mutate()}
                  disabled={!draftCase || updateMutation.isPending}
                  className="inline-flex min-h-10 items-center gap-2 rounded-md bg-brand px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {updateMutation.isPending ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Save size={16} aria-hidden="true" />}
                  Save
                </button>
              </div>
              {draftCase ? (
                <div className="space-y-3">
                  <label className="block text-sm font-semibold text-ink">
                    Name
                    <input
                      value={draftCase.name}
                      onChange={(event) => setDraftCase({ ...draftCase, name: event.target.value })}
                      className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm font-normal outline-none focus:border-brand"
                    />
                  </label>
                  <label className="block text-sm font-semibold text-ink">
                    Request
                    <textarea
                      value={draftCase.prompt}
                      onChange={(event) => setDraftCase({ ...draftCase, prompt: event.target.value })}
                      rows={5}
                      className="mt-1 w-full resize-none rounded-md border border-line bg-white px-3 py-2 text-sm font-normal leading-6 outline-none focus:border-brand"
                    />
                  </label>
                  <label className="block text-sm font-semibold text-ink">
                    Expected JSON
                    <textarea
                      value={expectedJson}
                      onChange={(event) => setExpectedJson(event.target.value)}
                      rows={10}
                      spellCheck={false}
                      className="mt-1 w-full resize-y rounded-md border border-line bg-white px-3 py-2 font-mono text-xs font-normal leading-5 outline-none focus:border-brand"
                    />
                  </label>
                  <label className="flex items-center gap-2 text-sm font-semibold text-ink">
                    <input
                      type="checkbox"
                      checked={draftCase.active}
                      onChange={(event) => setDraftCase({ ...draftCase, active: event.target.checked })}
                    />
                    Active in benchmark runs
                  </label>
                </div>
              ) : (
                <EmptyState text="No cases loaded." />
              )}
            </section>

            <ResultPanel result={selectedResult} />
          </aside>
        </div>
      </section>
    </main>
  );
}

function MetricCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/75 bg-white/72 p-4 shadow-sm backdrop-blur">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-steel">
        {icon}
        {label}
      </div>
      <div className="mt-2 min-h-12 text-lg font-bold leading-6 text-ink">{value}</div>
    </div>
  );
}

function StatusBadge({ result }: { result?: EvalCaseResult }) {
  if (!result) {
    return <span className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold text-steel">Not run</span>;
  }
  if (result.passed) {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800">
        <CheckCircle2 size={14} aria-hidden="true" />
        Passed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-800">
      <XCircle size={14} aria-hidden="true" />
      {result.status.replace('_', ' ')}
    </span>
  );
}

function ResultPanel({ result }: { result: EvalCaseResult | null }) {
  if (!result) {
    return (
      <section className="rounded-lg border border-white/75 bg-white/72 p-4 shadow-sm backdrop-blur">
        <div className="mb-3 flex items-center gap-2 font-semibold text-ink">
          <Database size={17} aria-hidden="true" />
          Result detail
        </div>
        <EmptyState text="Run evals or select a case to inspect model output." />
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-white/75 bg-white/72 p-4 shadow-sm backdrop-blur">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="font-semibold text-ink">Result detail</div>
        <StatusBadge result={result} />
      </div>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <Detail label="Case" value={result.case_name} />
        <Detail label="Score" value={formatPercent(result.score)} />
        <Detail label="Latency" value={result.latency_ms == null ? 'Unknown' : `${result.latency_ms} ms`} />
        <Detail label="Provider" value={`${result.provider ?? 'unknown'} / ${result.model ?? 'unknown'}`} />
      </dl>
      {result.error ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{result.error}</div>
      ) : null}
      <div className="mt-4">
        <div className="mb-2 text-sm font-semibold text-ink">Field diffs</div>
        <div className="space-y-2">
          {result.diffs.map((diff) => (
            <div key={diff.field} className="rounded-md border border-line bg-white/78 p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-ink">{diff.field}</div>
                {diff.passed ? <CheckCircle2 size={16} className="text-emerald-700" /> : <XCircle size={16} className="text-rose-700" />}
              </div>
              {!diff.passed ? (
                <div className="mt-2 grid gap-2 text-xs text-steel">
                  <pre className="overflow-auto rounded bg-panel p-2">{pretty(diff.expected)}</pre>
                  <pre className="overflow-auto rounded bg-panel p-2">{pretty(diff.actual)}</pre>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-4 grid gap-3">
        <JsonBlock title="Normalized output" value={result.normalized_output} />
        <JsonBlock title="Expected JSON" value={result.expected} />
        <JsonBlock title="Raw model output" value={result.raw_output || 'No output'} />
      </div>
      <div className="mt-3 text-xs text-steel">Recorded {formatDate(result.created_at)}</div>
    </section>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-white/78 px-3 py-2">
      <dt className="text-xs font-semibold uppercase text-steel">{label}</dt>
      <dd className="mt-1 break-words text-ink">{value}</dd>
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="rounded-md border border-line bg-white/78">
      <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-ink">{title}</summary>
      <pre className="max-h-72 overflow-auto border-t border-line p-3 text-xs leading-5 text-steel">{typeof value === 'string' ? value : pretty(value)}</pre>
    </details>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-line px-3 py-5 text-sm text-steel">{text}</div>;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Request failed';
}

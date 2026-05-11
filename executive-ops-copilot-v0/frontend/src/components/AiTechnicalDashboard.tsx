import { Gauge } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { AiMetrics } from '../types';

function formatRate(value?: number) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function formatOperation(value: string) {
  return value.replace(/_/g, ' ');
}

function metricClass(severity: string) {
  if (severity === 'critical') {
    return 'border-danger/30 bg-white/70 text-danger';
  }
  if (severity === 'warning') {
    return 'border-[#d0a44a]/40 bg-white/70 text-[#805d18]';
  }
  return 'border-line bg-white/70 text-brandDark';
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

export function AiTechnicalDashboard({ metrics, error }: { metrics?: AiMetrics; error?: string }) {
  const empty = !metrics || metrics.total_events === 0;
  const operationRows = metrics?.operation_metrics ?? [];
  const toolRows = metrics?.tool_metrics ?? [];
  const insightRows = metrics?.insights ?? [];
  const failureRows = metrics?.recent_failures ?? [];

  return (
    <section className="overflow-hidden rounded-lg border border-white/75 bg-glass shadow-[0_20px_48px_rgba(31,38,50,0.11)] backdrop-blur-md">
      <div className="flex flex-col gap-3 border-b border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.76),rgba(255,255,255,0.48))] px-4 py-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <Gauge size={18} className="text-brandDark" aria-hidden="true" />
          <div>
            <h2 className="text-base font-semibold text-ink">AI technical performance</h2>
            <p className="mt-1 text-sm text-steel">
              Decoupled ADK telemetry for model health, tool-call reliability, latency, and eval-like failure insight.
            </p>
          </div>
        </div>
        <span className="rounded-md border border-line bg-white/70 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-brandDark shadow-sm">
          Telemetry framework
        </span>
      </div>

      {error ? <div className="border-b border-line bg-white/55 px-4 py-3 text-sm text-danger">{error}</div> : null}

      <div className="grid gap-3 p-4 md:grid-cols-5">
        <MetricCard label="AI events" value={String(metrics?.total_events ?? 0)} detail="tracked calls" />
        <MetricCard label="Success rate" value={formatRate(metrics?.success_rate)} detail="completed events" />
        <MetricCard label="ADK coverage" value={formatRate(metrics?.adk_coverage)} detail="model calls via ADK" />
        <MetricCard label="Tool coverage" value={formatRate(metrics?.tool_call_coverage)} detail="ADK tool traces" />
        <MetricCard label="P95 latency" value={`${metrics?.p95_latency_ms ?? 0}ms`} detail={`avg ${metrics?.avg_latency_ms ?? 0}ms`} />
      </div>

      <div className="grid gap-4 border-t border-line/80 p-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.8fr)]">
        <div className="min-w-0 space-y-4">
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel">Operation health</div>
            <div className="overflow-hidden rounded-md border border-line bg-white/58">
              {empty ? (
                <div className="px-3 py-4 text-sm text-steel">Run an intake, recommendation, or draft workflow to populate ADK telemetry.</div>
              ) : (
                operationRows.map((row) => (
                  <div key={row.operation} className="grid gap-2 border-b border-line/70 px-3 py-3 text-sm last:border-b-0 md:grid-cols-[1.2fr_0.8fr_0.8fr_0.8fr]">
                    <div className="min-w-0">
                      <div className="truncate font-semibold text-ink">{formatOperation(row.operation)}</div>
                      <div className="text-xs text-steel">{row.total} events</div>
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-steel">Success</div>
                      <div className="font-semibold text-ink">{formatRate(row.success_rate)}</div>
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-steel">ADK</div>
                      <div className="font-semibold text-ink">{formatRate(row.adk_coverage)}</div>
                    </div>
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wide text-steel">Tools</div>
                      <div className="font-semibold text-ink">{row.tool_calls_avg.toFixed(1)} avg</div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel">Tool-call reliability</div>
            <div className="overflow-hidden rounded-md border border-line bg-white/58">
              {toolRows.length ? (
                toolRows.map((tool) => (
                  <div key={tool.tool_name} className="grid gap-2 border-b border-line/70 px-3 py-3 text-sm last:border-b-0 md:grid-cols-[1.5fr_0.6fr_0.8fr_0.8fr]">
                    <div className="truncate font-semibold text-ink">{formatOperation(tool.tool_name)}</div>
                    <div className="text-steel">{tool.calls} calls</div>
                    <div className="font-semibold text-ink">{formatRate(tool.success_rate)}</div>
                    <div className="text-steel">{tool.failure_count} failed</div>
                  </div>
                ))
              ) : (
                <div className="px-3 py-4 text-sm text-steel">No tool traces in the current telemetry window.</div>
              )}
            </div>
          </div>
        </div>

        <div className="min-w-0 space-y-4">
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel">Insights</div>
            <div className="space-y-2">
              {insightRows.map((insight) => (
                <div key={`${insight.reason}-${insight.title}`} className={`rounded-md border px-3 py-2 text-sm shadow-sm ${metricClass(insight.severity)}`}>
                  <div className="font-semibold">{insight.title}</div>
                  <div className="mt-1 text-xs text-steel">{insight.detail}</div>
                  <div className="mt-2 text-xs font-semibold uppercase tracking-wide">{insight.reason}</div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel">Needs attention</div>
            <div className="space-y-2">
              {failureRows.length ? (
                failureRows.map((event) => (
                  <div key={event.id} className="rounded-md border border-line bg-white/58 px-3 py-2 text-sm shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-semibold text-ink">{formatOperation(event.operation)}</span>
                      <span className="rounded-md border border-line bg-white/70 px-2 py-1 text-xs font-semibold text-brandDark">{event.model_status}</span>
                    </div>
                    <div className="mt-1 text-xs text-steel">{event.runtime} / {event.latency_ms}ms / {event.error_code ?? 'review telemetry'}</div>
                  </div>
                ))
              ) : (
                <div className="rounded-md border border-line bg-white/58 px-3 py-4 text-sm text-steel">
                  No unavailable or invalid model events in the current telemetry window.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function AiTechnicalDashboardPage() {
  const metricsQuery = useQuery({ queryKey: ['ai-telemetry-dashboard'], queryFn: api.aiMetrics, refetchInterval: 20000 });

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-white/70 bg-white/55 p-4 shadow-[0_18px_44px_rgba(31,38,50,0.10)] backdrop-blur-md">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-line bg-white/80 text-brandDark shadow-sm">
            <Gauge size={18} aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-ink">AI Technical Dashboard</h2>
            <p className="mt-1 max-w-3xl text-sm text-steel">
              This view is decoupled from the scheduling workflow. It renders only metrics fetched from persisted AI telemetry events in SQLite.
            </p>
          </div>
        </div>
      </section>
      <AiTechnicalDashboard
        metrics={metricsQuery.data}
        error={metricsQuery.error ? 'DB-backed AI telemetry metrics are unavailable.' : undefined}
      />
    </div>
  );
}

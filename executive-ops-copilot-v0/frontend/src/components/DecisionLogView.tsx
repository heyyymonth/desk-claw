import type { DecisionLogEntry } from '../types';
import { EmptyState, Panel } from './ui';

export function DecisionLogView({ entries }: { entries: DecisionLogEntry[] }) {
  return (
    <Panel title="Decision History">
      {entries.length ? (
        <div className="space-y-3">
          {entries.map((entry, index) => (
            <article key={entry.id ?? `${entry.meeting_request.intent.title}-${index}`} className="rounded-md border border-line bg-white/55 p-3 text-sm shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-ink">{entry.meeting_request.intent.title}</h3>
                  <div className="mt-1 text-steel">
                    Requester: <strong className="text-ink">{entry.meeting_request.intent.requester}</strong>
                  </div>
                </div>
                <span className="rounded-md border border-line bg-white/75 px-2 py-1 text-xs font-semibold uppercase tracking-wide text-brandDark">
                  {entry.final_decision}
                </span>
              </div>
              <div className="mt-3 rounded-md bg-panel px-3 py-2 text-steel">
                desk.ai recommended <strong className="capitalize text-ink">{entry.recommendation.decision}</strong>
                {entry.recommendation.risk_level ? (
                  <>
                    {' '}
                    with <strong className="text-ink">{entry.recommendation.risk_level}</strong> risk.
                  </>
                ) : (
                  '.'
                )}
              </div>
              {entry.notes ? (
                <div className="mt-2 whitespace-pre-line text-steel">
                  <strong className="text-ink">EA note:</strong> {entry.notes}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState>Reviewed decisions will appear here in plain language after you accept, edit, reject, or mark a recommendation wrong.</EmptyState>
      )}
    </Panel>
  );
}

import type { DecisionLogEntry } from '../types';
import { EmptyState, Panel } from './ui';

export function DecisionLogView({ entries }: { entries: DecisionLogEntry[] }) {
  return (
    <Panel title="Decision Log View">
      {entries.length ? (
        <div className="space-y-3">
          {entries.map((entry, index) => (
            <article key={entry.id ?? `${entry.meeting_request.intent.title}-${index}`} className="rounded-md border border-line bg-panel p-3 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <h3 className="font-semibold">{entry.meeting_request.intent.title}</h3>
                <span className="capitalize text-steel">{entry.final_decision}</span>
              </div>
              <div className="mt-1 text-steel">
                {entry.recommendation.decision} recommendation for {entry.meeting_request.intent.requester}
              </div>
              {entry.notes ? <div className="mt-2">{entry.notes}</div> : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState>Accepted, edited, rejected, and wrong decisions will be logged here locally.</EmptyState>
      )}
    </Panel>
  );
}

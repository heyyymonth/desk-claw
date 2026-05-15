import { CalendarCheck } from 'lucide-react';
import type { ExecutiveRules, Recommendation } from '../types';
import { RiskLabel } from './RiskLabel';
import { EmptyState, InlineSpinner, LoadingNotice, Panel, PrimaryButton } from './ui';

export function RecommendationCard({
  recommendation,
  rules,
  onGenerate,
  disabled,
  isLoading,
}: {
  recommendation?: Recommendation;
  rules?: ExecutiveRules;
  onGenerate: () => void;
  disabled: boolean;
  isLoading: boolean;
}) {
  const highestRisk = recommendation?.risks.some((risk) => risk.level === 'high')
    ? 'high'
    : recommendation?.risks.some((risk) => risk.level === 'medium')
      ? 'medium'
      : 'low';

  return (
    <Panel
      title="Recommendation Card"
      aside={
        <PrimaryButton type="button" onClick={onGenerate} disabled={disabled || isLoading}>
          {isLoading ? <InlineSpinner className="mr-2" /> : <CalendarCheck className="mr-2" size={16} aria-hidden="true" />}
          {isLoading ? 'Generating recommendation...' : 'Generate Recommendation'}
        </PrimaryButton>
      }
    >
      {recommendation ? (
        <div className="space-y-4 text-sm">
          {isLoading ? <LoadingNotice>Recommendation generation is waiting on the model response.</LoadingNotice> : null}
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-2xl font-bold capitalize text-ink">{recommendation.decision}</div>
            <RiskLabel level={highestRisk} />
            <span className="rounded-md bg-panel px-2 py-1 font-semibold">
              {Math.round(recommendation.confidence * 100)}% confidence
            </span>
            <span className="text-steel">Model: {recommendation.model_status}</span>
          </div>
          <div>
            <div className="font-semibold">Rationale</div>
            <ul className="mt-1 list-disc pl-5">
              {recommendation.rationale.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <div className="font-semibold">Risks</div>
            {recommendation.risks.length ? (
              <ul className="mt-1 space-y-2">
                {recommendation.risks.map((risk) => (
                  <li key={`${risk.level}-${risk.message}`} className="flex items-start gap-2 rounded-md bg-panel px-3 py-2">
                    <RiskLabel level={risk.level} />
                    <span>{risk.message}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState>No risks returned by FastAPI.</EmptyState>
            )}
          </div>
          <div>
            <div className="font-semibold">Calendar impact</div>
            {recommendation.proposed_slots.length ? (
              <ul className="mt-1 space-y-2">
                {recommendation.proposed_slots.map((slot) => (
                  <li key={`${slot.start}-${slot.end}`} className="rounded-md bg-panel px-3 py-2">
                    {new Date(slot.start).toLocaleString()} to {new Date(slot.end).toLocaleString()} - {slot.reason}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState>No calendar slot change proposed. The likely action is clarify, decline, or defer.</EmptyState>
            )}
          </div>
          <div>
            <div className="font-semibold">Rules applied</div>
            <ul className="mt-1 list-disc pl-5">
              <li>
                Working hours {rules?.working_hours.start ?? 'unknown'}-{rules?.working_hours.end ?? 'unknown'} in{' '}
                {rules?.timezone ?? 'unknown timezone'}
              </li>
              {rules?.preferences.map((preference) => <li key={preference}>{preference}</li>)}
            </ul>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {isLoading ? <LoadingNotice>Recommendation generation is waiting on the model response.</LoadingNotice> : null}
          <EmptyState>
            {isLoading
              ? 'Recommendation details will appear here when the model response returns.'
              : 'Generate a recommendation after parsed intent, rules, and calendar context are visible.'}
          </EmptyState>
        </div>
      )}
    </Panel>
  );
}

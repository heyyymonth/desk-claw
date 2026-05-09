import { Check, Pencil, ThumbsDown, X } from 'lucide-react';
import type { FeedbackDecision } from '../types';
import { Panel, SecondaryButton } from './ui';

const options: Array<{ value: FeedbackDecision; label: string; icon: typeof Check }> = [
  { value: 'accepted', label: 'Accept', icon: Check },
  { value: 'edited', label: 'Edited', icon: Pencil },
  { value: 'rejected', label: 'Reject', icon: X },
  { value: 'wrong', label: 'Mark Wrong', icon: ThumbsDown },
];

export function DecisionFeedbackControls({
  onSubmit,
  disabled,
  isLogging,
}: {
  onSubmit: (decision: FeedbackDecision, notes: string) => void;
  disabled: boolean;
  isLogging: boolean;
}) {
  const submit = (decision: FeedbackDecision) => onSubmit(decision, decision === 'edited' ? 'Draft edited before use.' : '');

  return (
    <Panel title="Decision Feedback Controls">
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const Icon = option.icon;
          return (
            <SecondaryButton
              key={option.value}
              type="button"
              onClick={() => submit(option.value)}
              disabled={disabled || isLogging}
              aria-label={option.label}
            >
              <Icon className="mr-2" size={16} aria-hidden="true" />
              {option.label}
            </SecondaryButton>
          );
        })}
      </div>
      <p className="mt-3 text-sm text-steel">Feedback logs the decision only. V0 does not write back to a calendar or send email.</p>
    </Panel>
  );
}

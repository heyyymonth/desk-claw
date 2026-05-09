import { MailPlus } from 'lucide-react';
import type { DraftResponse } from '../types';
import { EmptyState, FieldLabel, Panel, PrimaryButton } from './ui';

export function DraftResponsePanel({
  draft,
  onDraftChange,
  onGenerate,
  disabled,
  isLoading,
}: {
  draft?: DraftResponse;
  onDraftChange: (draft: DraftResponse) => void;
  onGenerate: () => void;
  disabled: boolean;
  isLoading: boolean;
}) {
  return (
    <Panel
      title="Draft Response Panel"
      aside={
        <PrimaryButton type="button" onClick={onGenerate} disabled={disabled || isLoading}>
          <MailPlus className="mr-2" size={16} aria-hidden="true" />
          {isLoading ? 'Generating...' : 'Generate Draft'}
        </PrimaryButton>
      }
    >
      {draft ? (
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-[1fr_160px]">
            <div className="space-y-1">
              <FieldLabel>Subject</FieldLabel>
              <input
                aria-label="Draft subject"
                value={draft.subject}
                onChange={(event) => onDraftChange({ ...draft, subject: event.target.value })}
                className="w-full rounded-md border border-line px-3 py-2 text-sm"
              />
            </div>
            <div className="space-y-1">
              <FieldLabel>Tone</FieldLabel>
              <select
                aria-label="Draft tone"
                value={draft.tone}
                onChange={(event) => onDraftChange({ ...draft, tone: event.target.value as DraftResponse['tone'] })}
                className="w-full rounded-md border border-line px-3 py-2 text-sm"
              >
                <option value="concise">Concise</option>
                <option value="warm">Warm</option>
                <option value="firm">Firm</option>
              </select>
            </div>
          </div>
          <div className="space-y-1">
            <FieldLabel>Editable body</FieldLabel>
            <textarea
              aria-label="Draft body"
              value={draft.body}
              onChange={(event) => onDraftChange({ ...draft, body: event.target.value })}
              className="min-h-40 w-full resize-y rounded-md border border-line px-3 py-2 text-sm"
            />
          </div>
          <div className="text-sm text-steel">Model: {draft.model_status}. This draft is not sent automatically.</div>
        </div>
      ) : (
        <EmptyState>Draft response will appear here after the recommendation is generated.</EmptyState>
      )}
    </Panel>
  );
}

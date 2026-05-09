import { useState } from 'react';
import type { ExecutiveRules } from '../types';
import { fromDateTimeLocalValue, toDateTimeLocalValue } from '../lib/dateTime';
import { EmptyState, FieldLabel, Panel, SecondaryButton } from './ui';

export function ExecutiveRulesPanel({
  rules,
  onChange,
  error,
}: {
  rules?: ExecutiveRules;
  onChange: (rules: ExecutiveRules) => void;
  error?: string;
}) {
  const [confirmed, setConfirmed] = useState(false);

  if (!rules) {
    return (
      <Panel title="Executive Rules Panel">
        <EmptyState>{error ?? 'Default rules will load from FastAPI. You can still connect later if the backend is offline.'}</EmptyState>
      </Panel>
    );
  }

  const update = (patch: Partial<ExecutiveRules>) => onChange({ ...rules, ...patch });
  const updateProtectedBlock = (
    index: number,
    patch: Partial<ExecutiveRules['protected_blocks'][number]>,
  ) => {
    onChange({
      ...rules,
      protected_blocks: rules.protected_blocks.map((block, blockIndex) =>
        blockIndex === index ? { ...block, ...patch } : block,
      ),
    });
  };

  return (
    <Panel title="Executive Rules Panel">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1">
          <FieldLabel>Executive</FieldLabel>
          <input
            aria-label="Executive name"
            value={rules.executive_name}
            onChange={(event) => update({ executive_name: event.target.value })}
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <FieldLabel>Timezone</FieldLabel>
          <input
            aria-label="Timezone"
            value={rules.timezone}
            onChange={(event) => update({ timezone: event.target.value })}
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <FieldLabel>Working start</FieldLabel>
          <input
            aria-label="Working start"
            type="time"
            value={rules.working_hours.start}
            onChange={(event) => update({ working_hours: { ...rules.working_hours, start: event.target.value } })}
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <FieldLabel>Working end</FieldLabel>
          <input
            aria-label="Working end"
            type="time"
            value={rules.working_hours.end}
            onChange={(event) => update({ working_hours: { ...rules.working_hours, end: event.target.value } })}
            className="w-full rounded-md border border-line px-3 py-2 text-sm"
          />
        </div>
        <div className="md:col-span-2">
          <FieldLabel>Preferences</FieldLabel>
          <textarea
            aria-label="Executive preferences"
            value={rules.preferences.join('\n')}
            onChange={(event) =>
              update({
                preferences: event.target.value
                  .split('\n')
                  .map((preference) => preference.trim())
                  .filter(Boolean),
              })
            }
            className="mt-1 min-h-24 w-full resize-y rounded-md border border-line px-3 py-2 text-sm"
          />
        </div>
        <div className="md:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <FieldLabel>Protected blocks</FieldLabel>
            <SecondaryButton
              type="button"
              aria-label="Add protected block"
              onClick={() =>
                onChange({
                  ...rules,
                  protected_blocks: [
                    ...rules.protected_blocks,
                    {
                      label: 'Protected block',
                      start: new Date().toISOString(),
                      end: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
                    },
                  ],
                })
              }
              className="min-h-8 px-2 text-xs"
            >
              Add block
            </SecondaryButton>
          </div>
          {rules.protected_blocks.length ? (
            <div className="mt-2 space-y-3">
              {rules.protected_blocks.map((block, index) => (
                <div key={`${block.label}-${index}`} className="grid min-w-0 gap-2 rounded-md bg-panel p-3">
                  <input
                    aria-label={`Protected block ${index + 1} label`}
                    value={block.label}
                    onChange={(event) => updateProtectedBlock(index, { label: event.target.value })}
                    className="min-w-0 rounded-md border border-line px-3 py-2 text-sm"
                  />
                  <input
                    aria-label={`Protected block ${index + 1} start`}
                    type="datetime-local"
                    value={toDateTimeLocalValue(block.start)}
                    onChange={(event) => updateProtectedBlock(index, { start: fromDateTimeLocalValue(event.target.value) })}
                    className="min-w-0 rounded-md border border-line px-3 py-2 text-sm"
                  />
                  <input
                    aria-label={`Protected block ${index + 1} end`}
                    type="datetime-local"
                    value={toDateTimeLocalValue(block.end)}
                    onChange={(event) => updateProtectedBlock(index, { end: fromDateTimeLocalValue(event.target.value) })}
                    className="min-w-0 rounded-md border border-line px-3 py-2 text-sm"
                  />
                  <SecondaryButton
                    type="button"
                    aria-label={`Remove protected block ${index + 1}`}
                    onClick={() =>
                      onChange({
                        ...rules,
                        protected_blocks: rules.protected_blocks.filter((_block, blockIndex) => blockIndex !== index),
                      })
                    }
                    className="min-h-9 whitespace-nowrap"
                  >
                    Remove
                  </SecondaryButton>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>No protected blocks configured.</EmptyState>
          )}
        </div>
      </div>
      <div className="mt-4">
        <SecondaryButton type="button" aria-label="Confirm executive rules" onClick={() => setConfirmed(true)}>
          {confirmed ? 'Rules confirmed' : 'Confirm executive rules'}
        </SecondaryButton>
      </div>
    </Panel>
  );
}

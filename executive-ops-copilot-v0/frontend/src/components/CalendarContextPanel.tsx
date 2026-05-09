import type { CalendarContext, MeetingRequest } from '../types';
import { EmptyState, Panel, SecondaryButton } from './ui';

export function CalendarContextPanel({
  calendar,
  onChange,
  meetingRequest,
  error,
}: {
  calendar?: CalendarContext;
  onChange: (calendar: CalendarContext) => void;
  meetingRequest?: MeetingRequest;
  error?: string;
}) {
  const missing = [
    ...(calendar?.missing_context ?? []),
    ...(meetingRequest?.intent.missing_fields ?? []),
  ];

  return (
    <Panel title="Calendar Context Panel">
      <div className="space-y-3 text-sm">
        {error ? <EmptyState>{error}</EmptyState> : null}
        <div>
          <div className="font-semibold">AI and calendar assumptions</div>
          {calendar?.assumptions?.length ? (
            <ul className="mt-1 list-disc pl-5">
              {calendar.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
          ) : (
            <EmptyState>No calendar assumptions returned yet.</EmptyState>
          )}
        </div>
        <div>
          <div className="font-semibold">Missing context</div>
          {missing.length ? (
            <ul className="mt-1 list-disc pl-5 text-amberRisk">
              {missing.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <div className="text-greenRisk">No missing context currently reported.</div>
          )}
        </div>
        <div>
          <div className="flex items-center justify-between gap-3">
            <div className="font-semibold">Calendar impact preview</div>
            <SecondaryButton
              type="button"
              aria-label="Add busy block"
              onClick={() =>
                onChange({
                  ...(calendar ?? {}),
                  busy_blocks: [
                    ...(calendar?.busy_blocks ?? []),
                    {
                      title: 'Busy',
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
          {calendar?.busy_blocks?.length ? (
            <div className="mt-2 space-y-3">
              {calendar.busy_blocks.map((block, index) => (
                <div key={`${block.start}-${index}`} className="grid gap-2 rounded-md bg-panel p-3 md:grid-cols-[1fr_1fr_1fr_auto]">
                  <input
                    aria-label={`Busy block ${index + 1} title`}
                    value={block.title ?? ''}
                    onChange={(event) =>
                      onChange({
                        ...calendar,
                        busy_blocks: calendar.busy_blocks?.map((busyBlock, blockIndex) =>
                          blockIndex === index ? { ...busyBlock, title: event.target.value } : busyBlock,
                        ),
                      })
                    }
                    className="rounded-md border border-line px-3 py-2 text-sm"
                  />
                  <input
                    aria-label={`Busy block ${index + 1} start`}
                    value={block.start}
                    onChange={(event) =>
                      onChange({
                        ...calendar,
                        busy_blocks: calendar.busy_blocks?.map((busyBlock, blockIndex) =>
                          blockIndex === index ? { ...busyBlock, start: event.target.value } : busyBlock,
                        ),
                      })
                    }
                    className="rounded-md border border-line px-3 py-2 text-sm"
                  />
                  <input
                    aria-label={`Busy block ${index + 1} end`}
                    value={block.end}
                    onChange={(event) =>
                      onChange({
                        ...calendar,
                        busy_blocks: calendar.busy_blocks?.map((busyBlock, blockIndex) =>
                          blockIndex === index ? { ...busyBlock, end: event.target.value } : busyBlock,
                        ),
                      })
                    }
                    className="rounded-md border border-line px-3 py-2 text-sm"
                  />
                  <SecondaryButton
                    type="button"
                    aria-label={`Remove busy block ${index + 1}`}
                    onClick={() =>
                      onChange({
                        ...calendar,
                        busy_blocks: calendar.busy_blocks?.filter((_block, blockIndex) => blockIndex !== index),
                      })
                    }
                    className="min-h-9"
                  >
                    Remove
                  </SecondaryButton>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState>Mock calendar availability will appear here when FastAPI is available.</EmptyState>
          )}
        </div>
        <SecondaryButton type="button" aria-label="Confirm mock calendar">
          Confirm mock calendar
        </SecondaryButton>
      </div>
    </Panel>
  );
}

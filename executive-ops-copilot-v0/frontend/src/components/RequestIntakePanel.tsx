import { ClipboardList } from 'lucide-react';
import type { MeetingRequest } from '../types';
import { EmptyState, ErrorState, FieldLabel, Panel, PrimaryButton } from './ui';

export function RequestIntakePanel({
  rawText,
  onRawTextChange,
  onParse,
  parsedRequest,
  isParsing,
  error,
  validationError,
}: {
  rawText: string;
  onRawTextChange: (value: string) => void;
  onParse: () => void;
  parsedRequest?: MeetingRequest;
  isParsing: boolean;
  error?: string;
  validationError?: string;
}) {
  const intent = parsedRequest?.intent;

  return (
    <Panel title="Request Intake Panel">
      <div className="space-y-3">
        <FieldLabel>Meeting request</FieldLabel>
        <textarea
          aria-label="Meeting request"
          value={rawText}
          onChange={(event) => onRawTextChange(event.target.value)}
          className="min-h-36 w-full resize-y rounded-md border border-line px-3 py-2 text-sm"
          placeholder="Paste the requester email, Slack message, or scheduling note."
        />
        {validationError ? <ErrorState message={validationError} /> : null}
        {error ? <ErrorState message={error} /> : null}
        <PrimaryButton type="button" onClick={onParse} disabled={isParsing}>
          <ClipboardList className="mr-2" size={16} aria-hidden="true" />
          {isParsing ? 'Parsing...' : 'Parse Request'}
        </PrimaryButton>
        {intent ? (
          <div className="grid gap-3 rounded-md border border-line bg-panel p-3 text-sm md:grid-cols-2">
            <div>
              <div className="font-semibold">Title</div>
              <div>{intent.title}</div>
            </div>
            <div>
              <div className="font-semibold">Requester</div>
              <div>{intent.requester}</div>
            </div>
            <div>
              <div className="font-semibold">Duration</div>
              <div>{intent.duration_minutes} minutes</div>
            </div>
            <div>
              <div className="font-semibold">Priority</div>
              <div className="capitalize">{intent.priority}</div>
            </div>
            <div className="md:col-span-2">
              <div className="font-semibold">Attendees</div>
              {intent.attendees.length ? (
                <div>{intent.attendees.join(', ')}</div>
              ) : (
                <div className="text-amberRisk">No attendees identified.</div>
              )}
            </div>
            <div className="md:col-span-2">
              <div className="font-semibold">Preferred windows</div>
              {intent.preferred_windows?.length ? (
                <ul className="mt-1 space-y-1">
                  {intent.preferred_windows.map((window) => (
                    <li key={`${window.start}-${window.end}`}>
                      {new Date(window.start).toLocaleString()} to {new Date(window.end).toLocaleString()}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-amberRisk">No preferred window identified.</div>
              )}
            </div>
            <div className="md:col-span-2">
              <div className="font-semibold">Constraints</div>
              {intent.constraints.length ? (
                <ul className="mt-1 list-disc pl-5">
                  {intent.constraints.map((constraint) => (
                    <li key={constraint}>{constraint}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-steel">No explicit constraints.</div>
              )}
            </div>
            <div className="md:col-span-2">
              <div className="font-semibold">AI assumed or found missing</div>
              {intent.missing_fields.length ? (
                <ul className="mt-1 list-disc pl-5 text-amberRisk">
                  {intent.missing_fields.map((field) => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
              ) : (
                <div className="text-greenRisk">No missing fields reported.</div>
              )}
            </div>
          </div>
        ) : (
          <EmptyState>Parsed intent will appear here before any recommendation is generated.</EmptyState>
        )}
      </div>
    </Panel>
  );
}

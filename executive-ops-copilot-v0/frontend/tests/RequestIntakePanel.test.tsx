import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { RequestIntakePanel } from '../src/components/RequestIntakePanel';
import { meetingRequest } from './fixtures';

describe('RequestIntakePanel', () => {
  it('shows validation feedback before parsing an empty request', async () => {
    const user = userEvent.setup();
    const onParse = vi.fn();

    render(
      <RequestIntakePanel
        rawText=""
        onRawTextChange={vi.fn()}
        onParse={onParse}
        isParsing={false}
        validationError="Paste a meeting request before parsing."
      />,
    );

    await user.click(screen.getByRole('button', { name: /parse request/i }));

    expect(onParse).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert')).toHaveTextContent('Paste a meeting request before parsing.');
  });

  it('renders parsed intent and missing fields', () => {
    render(
      <RequestIntakePanel
        rawText={meetingRequest.raw_text}
        onRawTextChange={vi.fn()}
        onParse={vi.fn()}
        parsedRequest={meetingRequest}
        isParsing={false}
      />,
    );

    expect(screen.getByText('Partner sync')).toBeInTheDocument();
    expect(screen.getByText('Jordan Lee')).toBeInTheDocument();
    expect(screen.getByText('Requester timezone')).toBeInTheDocument();
  });

  it('shows the request parsing loading state in the active panel', () => {
    render(
      <RequestIntakePanel
        rawText={meetingRequest.raw_text}
        onRawTextChange={vi.fn()}
        onParse={vi.fn()}
        isParsing={true}
      />,
    );

    expect(screen.getByRole('button', { name: /parsing request/i })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Request parsing is waiting on the model response.');
  });
});

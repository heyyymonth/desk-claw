import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { DraftResponsePanel } from '../src/components/DraftResponsePanel';
import type { DraftResponse } from '../src/types';
import { draft } from './fixtures';

describe('DraftResponsePanel', () => {
  it('allows draft response editing', async () => {
    const user = userEvent.setup();
    const onDraftChange = vi.fn();

    function Harness() {
      const [value, setValue] = useState<DraftResponse>(draft);
      return (
        <DraftResponsePanel
          draft={value}
          onDraftChange={(nextDraft) => {
            setValue(nextDraft);
            onDraftChange(nextDraft);
          }}
          onGenerate={vi.fn()}
          disabled={false}
          isLoading={false}
        />
      );
    }

    render(<Harness />);

    await user.clear(screen.getByLabelText('Draft body'));
    await user.type(screen.getByLabelText('Draft body'), 'Updated response');

    expect(onDraftChange).toHaveBeenLastCalledWith(expect.objectContaining({ body: 'Updated response' }));
  });

  it('shows the draft loading state in the active panel', () => {
    render(
      <DraftResponsePanel
        onDraftChange={vi.fn()}
        onGenerate={vi.fn()}
        disabled={false}
        isLoading={true}
      />,
    );

    expect(screen.getByRole('button', { name: /generating draft/i })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Draft generation is waiting on the model response.');
  });
});

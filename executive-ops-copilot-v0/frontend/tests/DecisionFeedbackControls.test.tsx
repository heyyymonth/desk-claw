import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DecisionFeedbackControls } from '../src/components/DecisionFeedbackControls';

describe('DecisionFeedbackControls', () => {
  it('submits selected feedback', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<DecisionFeedbackControls onSubmit={onSubmit} disabled={false} isLogging={false} />);

    await user.click(screen.getByRole('button', { name: 'Mark Wrong' }));

    expect(onSubmit).toHaveBeenCalledWith('wrong', '');
  });

  it('disables actions when no decision can be logged', () => {
    render(<DecisionFeedbackControls onSubmit={vi.fn()} disabled={true} isLogging={false} />);

    expect(screen.getByRole('button', { name: 'Accept' })).toBeDisabled();
  });

  it('shows the decision logging loading state in the active panel', () => {
    render(<DecisionFeedbackControls onSubmit={vi.fn()} disabled={false} isLogging={true} />);

    expect(screen.getByRole('button', { name: 'Accept' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Saving the decision feedback to the audit log.');
  });
});

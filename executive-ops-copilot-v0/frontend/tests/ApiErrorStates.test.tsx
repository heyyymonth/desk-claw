import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RequestIntakePanel } from '../src/components/RequestIntakePanel';

describe('API error states', () => {
  it('shows clear FastAPI error feedback', () => {
    render(
      <RequestIntakePanel
        rawText="Please schedule this."
        onRawTextChange={vi.fn()}
        onParse={vi.fn()}
        isParsing={false}
        error="FastAPI request failed with 503"
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('FastAPI request failed with 503');
  });
});

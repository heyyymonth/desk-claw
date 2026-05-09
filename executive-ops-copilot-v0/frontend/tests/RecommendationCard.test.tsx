import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RecommendationCard } from '../src/components/RecommendationCard';
import { recommendation, rules } from './fixtures';

describe('RecommendationCard', () => {
  it('renders recommendation details, rules applied, and calendar impact', () => {
    render(
      <RecommendationCard
        recommendation={recommendation}
        rules={rules}
        onGenerate={vi.fn()}
        disabled={false}
        isLoading={false}
      />,
    );

    expect(screen.getByText('schedule')).toBeInTheDocument();
    expect(screen.getByText('Requested window fits working hours.')).toBeInTheDocument();
    expect(screen.getByText(/Open calendar window with enough buffer/)).toBeInTheDocument();
    expect(screen.getByText(/Prefer customer meetings before 3 PM/)).toBeInTheDocument();
  });
});

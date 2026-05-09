import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RiskLabel } from '../src/components/RiskLabel';

describe('RiskLabel', () => {
  it('renders risk level text clearly', () => {
    render(<RiskLabel level="high" />);

    expect(screen.getByText('high risk')).toBeInTheDocument();
  });
});

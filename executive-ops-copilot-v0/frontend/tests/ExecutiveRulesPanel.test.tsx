import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ExecutiveRulesPanel } from '../src/components/ExecutiveRulesPanel';
import type { ExecutiveRules } from '../src/types';
import { rules } from './fixtures';

describe('ExecutiveRulesPanel', () => {
  it('allows executive preferences to be edited locally before recommendation', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    function Harness() {
      const [value, setValue] = useState<ExecutiveRules>(rules);
      return (
        <ExecutiveRulesPanel
          rules={value}
          onChange={(nextRules) => {
            setValue(nextRules);
            onChange(nextRules);
          }}
        />
      );
    }

    render(<Harness />);

    fireEvent.change(screen.getByLabelText('Executive preferences'), { target: { value: 'Avoid Mondays' } });

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ preferences: ['Avoid Mondays'] }));
  });

  it('adds protected blocks without calling backend write endpoints', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(<ExecutiveRulesPanel rules={rules} onChange={onChange} />);

    await user.click(screen.getByRole('button', { name: 'Add protected block' }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        protected_blocks: expect.arrayContaining([
          expect.objectContaining({ label: 'Protected block' }),
        ]),
      }),
    );
  });
});

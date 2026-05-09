import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { CalendarContextPanel } from '../src/components/CalendarContextPanel';
import type { CalendarContext } from '../src/types';
import { meetingRequest } from './fixtures';

const calendar: CalendarContext = {
  assumptions: ['Using mock calendar context.'],
  missing_context: ['Calendar source is seeded.'],
  busy_blocks: [
    {
      title: 'Focus block',
      start: '2026-05-12T15:00:00-07:00',
      end: '2026-05-12T16:00:00-07:00',
    },
  ],
};

describe('CalendarContextPanel', () => {
  it('shows assumptions and missing context explicitly', () => {
    render(<CalendarContextPanel calendar={calendar} onChange={vi.fn()} meetingRequest={meetingRequest} />);

    expect(screen.getByText('Using mock calendar context.')).toBeInTheDocument();
    expect(screen.getByText('Calendar source is seeded.')).toBeInTheDocument();
    expect(screen.getByText('Requester timezone')).toBeInTheDocument();
  });

  it('allows busy blocks to be edited locally', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    function Harness() {
      const [value, setValue] = useState<CalendarContext>(calendar);
      return (
        <CalendarContextPanel
          calendar={value}
          onChange={(nextCalendar) => {
            setValue(nextCalendar);
            onChange(nextCalendar);
          }}
          meetingRequest={meetingRequest}
        />
      );
    }

    render(<Harness />);

    await user.clear(screen.getByLabelText('Busy block 1 title'));
    await user.type(screen.getByLabelText('Busy block 1 title'), 'Board prep');

    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        busy_blocks: [expect.objectContaining({ title: 'Board prep' })],
      }),
    );
  });
});

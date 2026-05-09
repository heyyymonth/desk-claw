import { CalendarDays } from 'lucide-react';
import type { CalendarContext, ExecutiveRules, MeetingRequest, Recommendation } from '../types';
import { EmptyState, Panel } from './ui';

type CalendarEvent = {
  title: string;
  start: Date;
  end: Date;
  kind: 'booked' | 'protected' | 'suggested';
};

const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

export function WorkWeekCalendar({
  calendar,
  rules,
  recommendation,
  meetingRequest,
}: {
  calendar?: CalendarContext;
  rules: ExecutiveRules;
  recommendation?: Recommendation;
  meetingRequest?: MeetingRequest;
}) {
  const weekStart = startOfWorkWeek(anchorDate(calendar, rules, recommendation, meetingRequest));
  const days = Array.from({ length: 5 }, (_item, index) => addDays(weekStart, index));
  const hours = workHours(rules);
  const events = calendarEvents(calendar, rules, recommendation).filter((event) =>
    days.some((day) => isSameDay(day, event.start)),
  );

  return (
    <Panel
      title="Work Week Calendar"
      aside={
        <div className="flex items-center gap-2 text-sm text-steel">
          <CalendarDays size={16} aria-hidden="true" />
          <span>{formatWeekRange(days)}</span>
        </div>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-steel">
          A visual view of booked time, protected focus blocks, and any suggested slot after a recommendation is generated.
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          <Legend label="Booked" className="border-[#c7cbd3] bg-[#e4e7eb]" />
          <Legend label="Protected" className="border-[#b7bcc5] bg-[#d6dae1]" />
          <Legend label="Suggested" className="border-[#8f98a8] bg-[#c7ced8]" />
        </div>
        <div className="overflow-x-auto rounded-lg border border-line bg-white/55">
          <div className="grid min-w-[720px] grid-cols-[72px_repeat(5,minmax(0,1fr))]">
            <div className="border-b border-line bg-white/60 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-steel">
              Time
            </div>
            {days.map((day, index) => (
              <div key={day.toISOString()} className="border-b border-l border-line bg-white/60 px-3 py-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-steel">{dayNames[index]}</div>
                <div className="text-sm font-semibold text-ink">{day.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div>
              </div>
            ))}
            {hours.map((hour) => (
              <HourRow key={hour} hour={hour} days={days} events={events} />
            ))}
          </div>
        </div>
        {events.length ? (
          <div className="grid gap-2 md:grid-cols-2">
            {events.map((event) => (
              <div key={`${event.kind}-${event.title}-${event.start.toISOString()}`} className="rounded-md border border-line bg-white/55 px-3 py-2 text-sm">
                <div className="font-semibold text-ink">{event.title}</div>
                <div className="text-steel">
                  {event.start.toLocaleString(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })} -{' '}
                  {event.end.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState>Calendar blocks will appear here after rules and calendar context load.</EmptyState>
        )}
      </div>
    </Panel>
  );
}

function HourRow({ hour, days, events }: { hour: number; days: Date[]; events: CalendarEvent[] }) {
  return (
    <>
      <div className="border-b border-line px-3 py-3 text-xs font-semibold text-steel">{formatHour(hour)}</div>
      {days.map((day) => {
        const matching = events.filter((event) => isSameDay(day, event.start) && event.start.getHours() <= hour && event.end.getHours() >= hour);
        return (
          <div key={`${day.toISOString()}-${hour}`} className="min-h-14 border-b border-l border-line bg-white/35 p-1">
            <div className="space-y-1">
              {matching.map((event) => (
                <div
                  key={`${event.title}-${event.start.toISOString()}`}
                  className={`rounded-md border px-2 py-1 text-xs font-semibold ${eventClass(event.kind)}`}
                >
                  <div className="truncate">{event.title}</div>
                  <div className="font-normal opacity-80">
                    {event.start.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </>
  );
}

function Legend({ label, className }: { label: string; className: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-md border border-line bg-white/55 px-2 py-1 text-steel">
      <span className={`h-2.5 w-2.5 rounded-sm border ${className}`} />
      {label}
    </span>
  );
}

function eventClass(kind: CalendarEvent['kind']) {
  if (kind === 'suggested') {
    return 'border-[#8f98a8] bg-[#c7ced8] text-[#1f2937]';
  }
  if (kind === 'protected') {
    return 'border-[#b7bcc5] bg-[#d6dae1] text-[#27303d]';
  }
  return 'border-[#c7cbd3] bg-[#e4e7eb] text-[#27303d]';
}

function calendarEvents(calendar: CalendarContext | undefined, rules: ExecutiveRules, recommendation?: Recommendation): CalendarEvent[] {
  return [
    ...(calendar?.busy_blocks ?? []).map((block) => ({
      title: block.title ?? 'Booked',
      start: new Date(block.start),
      end: new Date(block.end),
      kind: 'booked' as const,
    })),
    ...rules.protected_blocks.map((block) => ({
      title: block.label,
      start: new Date(block.start),
      end: new Date(block.end),
      kind: 'protected' as const,
    })),
    ...(recommendation?.proposed_slots ?? []).map((slot) => ({
      title: 'Suggested slot',
      start: new Date(slot.start),
      end: new Date(slot.end),
      kind: 'suggested' as const,
    })),
  ].filter((event) => !Number.isNaN(event.start.getTime()) && !Number.isNaN(event.end.getTime()));
}

function anchorDate(
  calendar: CalendarContext | undefined,
  rules: ExecutiveRules,
  recommendation: Recommendation | undefined,
  meetingRequest: MeetingRequest | undefined,
) {
  const candidates = [
    recommendation?.proposed_slots[0]?.start,
    meetingRequest?.intent.preferred_windows?.[0]?.start,
    calendar?.busy_blocks?.[0]?.start,
    rules.protected_blocks[0]?.start,
  ].filter(Boolean) as string[];
  return candidates.length ? new Date(candidates[0]) : new Date();
}

function workHours(rules: ExecutiveRules) {
  const start = Number.parseInt(rules.working_hours.start.split(':')[0] ?? '9', 10);
  const end = Number.parseInt(rules.working_hours.end.split(':')[0] ?? '17', 10);
  const first = Number.isNaN(start) ? 9 : start;
  const last = Number.isNaN(end) ? 17 : end;
  return Array.from({ length: Math.max(1, last - first) }, (_item, index) => first + index);
}

function startOfWorkWeek(date: Date) {
  const next = new Date(date);
  const day = next.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  next.setDate(next.getDate() + offset);
  next.setHours(0, 0, 0, 0);
  return next;
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function isSameDay(left: Date, right: Date) {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth() && left.getDate() === right.getDate();
}

function formatHour(hour: number) {
  return new Date(2026, 0, 1, hour).toLocaleTimeString(undefined, { hour: 'numeric' });
}

function formatWeekRange(days: Date[]) {
  const first = days[0];
  const last = days[days.length - 1];
  return `${first.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${last.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })}`;
}

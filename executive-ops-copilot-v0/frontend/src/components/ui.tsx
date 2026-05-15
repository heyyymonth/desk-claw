import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

export function Panel({
  title,
  children,
  aside,
}: {
  title: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-white/68 bg-[rgba(247,248,250,0.70)] shadow-[0_18px_42px_rgba(31,38,50,0.10)] backdrop-blur-md">
      <div className="flex min-h-14 items-center justify-between gap-3 border-b border-line/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.62),rgba(241,244,248,0.42))] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.76)]">
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {aside}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-dashed border-line bg-white/45 px-3 py-4 text-sm text-steel">{children}</div>;
}

export function InlineSpinner({ className = '' }: { className?: string }) {
  return <Loader2 className={`shrink-0 animate-spin ${className}`} size={16} aria-hidden="true" />;
}

export function LoadingNotice({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 rounded-md border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.78),rgba(238,240,244,0.72))] px-3 py-2 text-sm font-semibold text-brandDark shadow-[inset_0_1px_0_rgba(255,255,255,0.72),0_8px_20px_rgba(31,38,50,0.06)]"
    >
      <InlineSpinner className="text-brandDark" />
      <span>{children}</span>
    </div>
  );
}

export function FieldLabel({ children }: { children: ReactNode }) {
  return <label className="text-xs font-semibold uppercase tracking-wide text-steel">{children}</label>;
}

export function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex min-h-10 items-center justify-center rounded-md border border-white/10 bg-[linear-gradient(180deg,#2f3745,#171d28)] px-4 text-sm font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_12px_26px_rgba(32,39,52,0.20)] hover:bg-brand disabled:cursor-not-allowed disabled:border-transparent disabled:bg-none disabled:bg-slate-400 ${props.className ?? ''}`}
    />
  );
}

export function SecondaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex min-h-10 items-center justify-center rounded-md border border-line bg-white/75 px-3 text-sm font-semibold text-brandDark shadow-[inset_0_1px_0_rgba(255,255,255,0.72),0_8px_18px_rgba(31,38,50,0.06)] hover:bg-brandSoft disabled:cursor-not-allowed disabled:text-slate-400 ${props.className ?? ''}`}
    />
  );
}

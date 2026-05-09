import type { ReactNode } from 'react';

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
    <section className="rounded-lg border border-white/70 bg-glass shadow-[0_18px_44px_rgba(31,38,50,0.10)] backdrop-blur-md">
      <div className="flex min-h-14 items-center justify-between gap-3 border-b border-line/80 bg-white/45 px-4 py-3">
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

export function FieldLabel({ children }: { children: ReactNode }) {
  return <label className="text-xs font-semibold uppercase tracking-wide text-steel">{children}</label>;
}

export function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex min-h-10 items-center justify-center rounded-md bg-brandDark px-4 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(32,39,52,0.16)] hover:bg-brand disabled:cursor-not-allowed disabled:bg-slate-400 ${props.className ?? ''}`}
    />
  );
}

export function SecondaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex min-h-10 items-center justify-center rounded-md border border-line bg-white/70 px-3 text-sm font-semibold text-brandDark shadow-sm hover:bg-brandSoft disabled:cursor-not-allowed disabled:text-slate-400 ${props.className ?? ''}`}
    />
  );
}

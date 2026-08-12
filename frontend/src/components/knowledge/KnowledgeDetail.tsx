import type { ReactNode } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export function KnowledgeBackLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link to={to} className="mb-6 inline-flex min-h-11 items-center gap-2 text-sm text-content-secondary transition hover:text-content-primary"><ArrowLeft size={18} />{children}</Link>;
}

export function KnowledgeHero({ eyebrow, title, description, media, badges }: {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  media?: ReactNode;
  badges?: ReactNode;
}) {
  return <header className="relative overflow-hidden rounded-3xl border border-line bg-surface-raised p-5 shadow-sm sm:p-8">
    <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-surface-base/40" />
    <div className="relative grid items-center gap-6 md:grid-cols-[minmax(0,1fr)_15rem]">
      <div><p className="text-xs font-bold uppercase tracking-[0.2em] text-primary">{eyebrow}</p><h1 className="mt-2 font-serif text-3xl font-bold leading-tight text-content-primary sm:text-5xl">{title}</h1>{description ? <div className="mt-4 max-w-3xl text-base leading-7 text-content-secondary">{description}</div> : null}{badges ? <div className="mt-5 flex flex-wrap gap-2">{badges}</div> : null}</div>
      {media ? <div className="mx-auto w-full max-w-60">{media}</div> : null}
    </div>
  </header>;
}

export function KnowledgeFacts({ children }: { children: ReactNode }) {
  return <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{children}</dl>;
}

export function KnowledgeFact({ label, value }: { label: ReactNode; value: ReactNode }) {
  return <div className="rounded-xl border border-line bg-surface-raised p-4"><dt className="text-xs font-semibold uppercase tracking-wide text-content-muted">{label}</dt><dd className="mt-1 text-base font-semibold text-content-primary">{value}</dd></div>;
}

export function KnowledgeBadge({ children, tone = 'neutral' }: {
  children: ReactNode;
  tone?: 'neutral' | 'primary' | 'danger' | 'warning';
}) {
  const tones = {
    neutral: 'border-line bg-surface text-content-secondary',
    primary: 'border-primary/30 bg-primary/10 text-primary',
    danger: 'border-danger/30 bg-danger/10 text-danger',
    warning: 'border-warning/30 bg-warning/10 text-warning',
  };
  return <span className={`inline-flex min-h-7 items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

export function KnowledgeSection({ id, title, icon, children, className = '' }: {
  id?: string;
  title: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return <section id={id} className={`scroll-mt-24 rounded-2xl border border-line bg-surface-raised p-5 shadow-sm sm:p-6 ${className}`}><h2 className="mb-4 flex items-center gap-2 font-serif text-xl font-bold text-primary sm:text-2xl">{icon}{title}</h2>{children}</section>;
}

export function KnowledgeEmpty({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-content-muted">{children}</p>;
}

import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} />;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-[var(--radius)] border border-dashed border-border-strong px-6 py-12 text-center", className)}>
      {icon ? <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted text-muted-foreground [&>svg]:h-5 [&>svg]:w-5">{icon}</div> : null}
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-[13px] text-muted-foreground text-balance">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow ? <div className="mb-1 text-[12px] font-medium uppercase tracking-wide text-subtle">{eyebrow}</div> : null}
        <h1 className="text-[22px] font-semibold leading-tight tracking-tight">{title}</h1>
        {description ? <p className="mt-1 text-[13.5px] text-muted-foreground max-w-2xl">{description}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function SectionTitle({ children, className, right }: { children: React.ReactNode; className?: string; right?: React.ReactNode }) {
  return (
    <div className={cn("mb-3 flex items-center justify-between", className)}>
      <h2 className="text-[13px] font-semibold uppercase tracking-wide text-subtle">{children}</h2>
      {right}
    </div>
  );
}

export function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-border-strong bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{children}</kbd>;
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="card-surface p-4">
      <div className="text-[12px] font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 text-[22px] font-semibold tracking-tight tabular-nums">{value}</div>
      {hint ? <div className="mt-0.5 text-[12px] text-subtle">{hint}</div> : null}
    </div>
  );
}

export function ProgressRing({ value, size = 36, stroke = 3, className }: { value: number; size?: number; stroke?: number; className?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <svg width={size} height={size} className={cn("shrink-0 -rotate-90", className)} aria-label={`${pct}% complete`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--border)" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke="var(--primary)"
        strokeWidth={stroke}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c - (pct / 100) * c}
        className="transition-[stroke-dashoffset] duration-500"
      />
    </svg>
  );
}

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Archive, Database, Download, FolderOpen, HardDrive, History, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn, formatBytes, formatNumber, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { SectionTitle, Skeleton, Stat } from "@/components/ui/misc";
import { ConfirmDialog } from "@/components/dialogs";

interface ProjectUse {
  slug: string;
  title: string;
  total: number;
  exemplars: number;
  exports: number;
  figures: number;
  history: number;
  other: number;
  exports_count: number;
}
interface ProfileUse {
  slug: string;
  name: string;
  total: number;
  sources: number;
  history: number;
  other: number;
}
interface Overview {
  data_dir: string;
  total: number;
  projects_total: number;
  profiles_total: number;
  raw_sources: number;
  exports_total: number;
  history_total: number;
  disk_free: number | null;
  other: { database: number; templates: number; kinds: number; branding: number };
  projects: ProjectUse[];
  profiles: ProfileUse[];
  counts: { llm_calls: number; llm_calls_old: number; jobs: number; jobs_finished: number; sessions: number; sessions_expired: number };
  oldest_llm_call: string | null;
  checked_at: string;
}
interface CleanupReport {
  report: Record<string, { removed?: number; freed?: number }>;
  freed: number;
}

const ACTIONS: Array<{ key: string; label: string; hint: (o: Overview) => string; icon: React.ComponentType<{ className?: string }>; needsDays?: boolean; needsKeep?: boolean; risky?: boolean }> = [
  {
    key: "exports",
    label: "Old exports",
    icon: Archive,
    needsKeep: true,
    hint: (o) => `${formatBytes(o.exports_total)} of PDFs, DOCX and LaTeX archives. Keeps the newest few per project.`,
  },
  {
    key: "raw_sources",
    label: "Raw paper sources",
    icon: FolderOpen,
    risky: true,
    hint: (o) => `${formatBytes(o.raw_sources)} of LaTeX source trees and original PDFs. Extracted text, figures and summaries are kept; re-extraction would need the file again.`,
  },
  {
    key: "history",
    label: "Compact version history",
    icon: History,
    hint: (o) => `${formatBytes(o.history_total)} across project and profile histories. Runs git gc; nothing is lost.`,
  },
  {
    key: "jobs",
    label: "Finished job records",
    icon: Database,
    needsDays: true,
    hint: (o) => `${formatNumber(o.counts.jobs_finished)} finished of ${formatNumber(o.counts.jobs)} job rows. Running jobs are never touched.`,
  },
  {
    key: "llm_calls",
    label: "Old model-call logs",
    icon: Database,
    needsDays: true,
    risky: true,
    hint: (o) => `${formatNumber(o.counts.llm_calls)} logged calls${o.oldest_llm_call ? `, oldest ${timeAgo(o.oldest_llm_call)}` : ""}. The Usage page loses that history.`,
  },
  {
    key: "sessions",
    label: "Expired sign-in sessions",
    icon: Database,
    hint: (o) => `${formatNumber(o.counts.sessions_expired)} expired of ${formatNumber(o.counts.sessions)}. Also done automatically at every restart.`,
  },
  {
    key: "vacuum",
    label: "Compact the database",
    icon: HardDrive,
    hint: (o) => `Database is ${formatBytes(o.other.database)} including its write-ahead log. Reclaims space after deletions.`,
  },
];

function Bar({ parts, total }: { parts: Array<{ label: string; value: number; className: string }>; total: number }) {
  if (!total) return <div className="h-2 w-full rounded-full bg-muted" />;
  return (
    <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted" role="img" aria-label={parts.map((p) => `${p.label} ${formatBytes(p.value)}`).join(", ")}>
      {parts
        .filter((p) => p.value > 0)
        .map((p) => (
          <span key={p.label} className={cn("h-full", p.className)} style={{ width: `${(p.value / total) * 100}%` }} title={`${p.label}: ${formatBytes(p.value)}`} />
        ))}
    </div>
  );
}

export function StoragePage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["admin-storage"], queryFn: () => api.get<Overview>("/api/admin/storage"), staleTime: 30_000 });
  const [selected, setSelected] = useState<Set<string>>(new Set(["exports", "history", "jobs", "sessions", "vacuum"]));
  const [keep, setKeep] = useState(3);
  const [days, setDays] = useState(90);
  const [confirm, setConfirm] = useState(false);
  const run = useMutation({
    mutationFn: () => api.post<CleanupReport>("/api/admin/storage/cleanup", { actions: [...selected], keep_exports: keep, older_than_days: days }),
    onSuccess: (r) => {
      setConfirm(false);
      void qc.invalidateQueries({ queryKey: ["admin-storage"] });
      void qc.invalidateQueries({ queryKey: ["usage"] });
      const removed = Object.values(r.report).reduce((n, x) => n + (x.removed ?? 0), 0);
      toast.success(`Cleanup done: ${formatBytes(r.freed)} freed${removed ? `, ${removed} record${removed === 1 ? "" : "s"} removed` : ""}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading || !q.data) return <Skeleton className="h-96" />;
  const o = q.data;
  const maxProject = Math.max(1, ...o.projects.map((p) => p.total));
  const toggle = (k: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  const risky = [...selected].some((k) => ACTIONS.find((a) => a.key === k)?.risky);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Data volume" value={formatBytes(o.total)} hint={o.data_dir} />
        <Stat label="Projects" value={formatBytes(o.projects_total)} hint={`${o.projects.length} project${o.projects.length === 1 ? "" : "s"}`} />
        <Stat label="Author profiles" value={formatBytes(o.profiles_total)} hint={`${o.profiles.length} profile${o.profiles.length === 1 ? "" : "s"}`} />
        <Stat label="Free on disk" value={formatBytes(o.disk_free)} hint={`Database ${formatBytes(o.other.database)} · checked ${timeAgo(o.checked_at)}`} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Back up</CardTitle>
          <CardDescription>
            One zip of the whole data volume: a consistent database snapshot plus every project, profile, template and kind file. Restore by unzipping it into an empty volume.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <a href="/api/admin/storage/backup?include_exports=true&include_raw=false" download>
            <Button variant="secondary">
              <Download className="h-4 w-4" /> Download backup
            </Button>
          </a>
          <a href="/api/admin/storage/backup?include_exports=true&include_raw=true" download className="text-[13px] text-muted-foreground underline-offset-2 hover:underline">
            Include raw paper sources ({formatBytes(o.raw_sources)} more)
          </a>
          <span className="text-[12.5px] text-subtle">Version history is left out; every file is included at its latest state.</span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Clean up</CardTitle>
          <CardDescription>
            Nothing here touches drafts, patterns, references or figures. Pick what to remove, then run it. The same actions can be scripted against the API for a cron job.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-2 md:grid-cols-2">
            {ACTIONS.map((a) => (
              <label key={a.key} className={cn("flex cursor-pointer items-start gap-3 rounded-[var(--radius-sm)] border px-3 py-2.5 transition-colors", selected.has(a.key) ? "border-primary/40 bg-primary-soft/30" : "border-border hover:bg-muted/50")}>
                <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--primary)]" checked={selected.has(a.key)} onChange={() => toggle(a.key)} />
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5 text-[13.5px] font-medium">
                    <a.icon className="h-3.5 w-3.5 text-muted-foreground" /> {a.label}
                    {a.risky ? <span className="rounded-full bg-warning-soft px-1.5 text-[10.5px] font-medium uppercase tracking-wide text-warning">irreversible</span> : null}
                  </span>
                  <span className="block text-[12.5px] text-muted-foreground">{a.hint(o)}</span>
                </span>
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-4">
            <Field label="Exports to keep per project" className="w-40">
              <Input type="number" min={0} max={50} value={keep} onChange={(e) => setKeep(Math.max(0, Number(e.target.value) || 0))} />
            </Field>
            <Field label="Remove records older than (days)" className="w-56">
              <Input type="number" min={0} max={3650} value={days} onChange={(e) => setDays(Math.max(0, Number(e.target.value) || 0))} />
            </Field>
            <Button onClick={() => setConfirm(true)} disabled={!selected.size} className="ml-auto">
              <Trash2 className="h-4 w-4" /> Run cleanup
            </Button>
          </div>
        </CardContent>
      </Card>

      <div>
        <SectionTitle>Projects by size</SectionTitle>
        <Card className="divide-y divide-border">
          {o.projects.length === 0 ? <p className="p-4 text-[13px] text-muted-foreground">No projects yet.</p> : null}
          {o.projects.map((p) => (
            <div key={p.slug} className="grid gap-2 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_120px]">
              <div className="min-w-0">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-[14px] font-medium">{p.title}</span>
                  <span className="shrink-0 text-[13px] tabular-nums text-muted-foreground">{formatBytes(p.total)}</span>
                </div>
                <div className="mt-1.5" style={{ width: `${Math.max(8, (p.total / maxProject) * 100)}%` }}>
                  <Bar
                    total={p.total}
                    parts={[
                      { label: "Example papers", value: p.exemplars, className: "bg-primary" },
                      { label: "Exports", value: p.exports, className: "bg-warning" },
                      { label: "Figures", value: p.figures, className: "bg-success" },
                      { label: "History", value: p.history, className: "bg-border-strong" },
                      { label: "Other", value: p.other, className: "bg-muted-foreground/40" },
                    ]}
                  />
                </div>
              </div>
              <div className="text-[11.5px] text-subtle sm:text-right">
                <span className="text-primary">■</span> example papers {formatBytes(p.exemplars)} · <span className="text-warning">■</span> {p.exports_count} export{p.exports_count === 1 ? "" : "s"} {formatBytes(p.exports)}
              </div>
            </div>
          ))}
        </Card>
      </div>

      {o.profiles.length ? (
        <div>
          <SectionTitle>Author profiles by size</SectionTitle>
          <Card className="divide-y divide-border">
            {o.profiles.map((p) => (
              <div key={p.slug} className="flex items-center justify-between gap-3 px-4 py-2.5 text-[13.5px]">
                <span className="truncate font-medium">{p.name}</span>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  sources {formatBytes(p.sources)} · history {formatBytes(p.history)} · <span className="text-foreground">{formatBytes(p.total)}</span>
                </span>
              </div>
            ))}
          </Card>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Run cleanup?"
        description={
          risky
            ? "Some selected actions cannot be undone: raw sources cannot be re-extracted without the original file, and deleted call logs vanish from the Usage page."
            : "Selected actions only remove data that can be regenerated. Drafts, patterns, references and figures are never touched."
        }
        confirmLabel="Run cleanup"
        onConfirm={() => run.mutate()}
        busy={run.isPending}
      />
    </div>
  );
}

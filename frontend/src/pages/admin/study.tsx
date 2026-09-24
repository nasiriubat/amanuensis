import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ClipboardCopy, Download, FileText, FlaskConical, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { formatNumber, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { EmptyState, SectionTitle, Skeleton, Stat } from "@/components/ui/misc";
import { ConfirmDialog } from "@/components/dialogs";
import { RichMarkdown } from "@/components/rich-markdown";

interface StudyProject {
  slug: string;
  title: string;
  kind: string;
  entry: string;
  owner: string | null;
  created_at: string;
  events: number;
  event_kinds: Record<string, number>;
  active_minutes: number;
  minutes_by_step: Record<string, number>;
  first_event: string | null;
  last_event: string | null;
  tokens_by_purpose: Record<string, { calls: number; tokens: number }>;
  tokens_total: number;
  sections: Record<string, number>;
  exports: number;
  references: number;
  cite_requests: number;
  verdicts: string[];
}

interface StudyState {
  enabled: boolean;
  since: string | null;
  events: number;
  projects: StudyProject[];
}

interface KitDoc {
  name: string;
  title: string;
  content: string;
}

const STEP_LABEL: Record<string, string> = {
  home: "Project page",
  spec: "Describe",
  design: "Research design",
  sources: "Sources",
  playbook: "Playbook",
  interview: "Interview",
  outline: "Outline",
  studio: "Studio",
  references: "References",
  figures: "Figures",
  review: "Review",
  export: "Export",
  other: "Elsewhere",
};

function StepBar({ minutes }: { minutes: Record<string, number> }) {
  const total = Object.values(minutes).reduce((a, b) => a + b, 0);
  if (!total) return <span className="text-[12px] text-subtle">No timed activity yet</span>;
  const entries = Object.entries(minutes).sort((a, b) => b[1] - a[1]);
  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
        {entries.map(([k, v], i) => (
          <div key={k} title={`${STEP_LABEL[k] ?? k}: ${v} min`} className={i % 2 ? "bg-primary/50" : "bg-primary"} style={{ width: `${(v / total) * 100}%` }} />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px] text-muted-foreground">
        {entries.slice(0, 5).map(([k, v]) => (
          <span key={k}>
            {STEP_LABEL[k] ?? k} <span className="tabular-nums text-foreground">{v}</span> min
          </span>
        ))}
      </div>
    </div>
  );
}

function ProjectRow({ p }: { p: StudyProject }) {
  const sections = Object.entries(p.sections);
  const total = sections.reduce((a, [, n]) => a + n, 0);
  const own = (p.sections.edited ?? 0) + (p.sections.mine ?? 0);
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[14px] font-semibold">{p.title}</h3>
            <Badge variant="outline">{p.kind.replace(/-/g, " ")}</Badge>
            <Badge>{p.entry === "idea" ? "from an idea" : p.entry === "draft" ? "from a draft" : "from a build"}</Badge>
          </div>
          <div className="text-[12.5px] text-muted-foreground">
            {p.owner ?? "unknown owner"} · created {timeAgo(p.created_at)}
            {p.last_event ? ` · last active ${timeAgo(p.last_event)}` : ""}
          </div>
        </div>
        <div className="grid grid-cols-3 gap-x-5 text-right text-[12px] text-muted-foreground sm:grid-cols-6">
          <div>
            <div className="text-[15px] font-semibold tabular-nums text-foreground">{p.active_minutes}</div>
            active min
          </div>
          <div>
            <div className="text-[15px] font-semibold tabular-nums text-foreground">{formatNumber(p.tokens_total)}</div>
            tokens
          </div>
          <div>
            <div className="text-[15px] font-semibold tabular-nums text-foreground">
              {own}/{total}
            </div>
            sections theirs
          </div>
          <div>
            <div className="text-[15px] font-semibold tabular-nums text-foreground">{p.references}</div>
            references
          </div>
          <div>
            <div className="text-[15px] font-semibold tabular-nums text-foreground">{p.exports}</div>
            exports
          </div>
          <div>
            <div className="text-[15px] font-semibold tabular-nums text-foreground">{p.events}</div>
            events
          </div>
        </div>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_260px]">
        <StepBar minutes={p.minutes_by_step} />
        <div className="text-[12px] text-muted-foreground">
          {p.verdicts.length ? (
            <div>
              Reviewer: <span className="text-foreground">{p.verdicts.join(" → ")}</span>
            </div>
          ) : (
            <div>Not reviewed yet</div>
          )}
          {Object.keys(p.event_kinds).length ? (
            <div className="mt-0.5">
              {Object.entries(p.event_kinds)
                .filter(([k]) => k !== "page")
                .map(([k, n]) => `${n} ${k.replace(/_/g, " ")}`)
                .join(", ") || "only page views"}
            </div>
          ) : null}
          {p.cite_requests ? <div className="mt-0.5">{p.cite_requests} claims still need a source</div> : null}
        </div>
      </div>
    </Card>
  );
}

export function StudyPage() {
  const qc = useQueryClient();
  const study = useQuery({ queryKey: ["admin-study"], queryFn: () => api.get<StudyState>("/api/admin/study"), refetchInterval: 60_000 });
  const kit = useQuery({ queryKey: ["admin-study-kit"], queryFn: () => api.get<KitDoc[]>("/api/admin/study/kit") });
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const [confirmErase, setConfirmErase] = useState(false);
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.put<{ enabled: boolean }>("/api/admin/study", { enabled }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["admin-study"] });
      void qc.invalidateQueries({ queryKey: ["site"] });
      toast.success(r.enabled ? "Recording usage events. Tell participants; the consent text covers it." : "Recording stopped. Existing events are kept.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const guide = useMutation({
    mutationFn: () => api.post<{ slug: string; created: boolean }>("/api/admin/study/guide-page"),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["admin-pages"] });
      toast.success(r.created ? `Draft page created at /p/${r.slug}. Edit and publish it under Pages.` : `The guide page already exists at /p/${r.slug}.`);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const erase = useMutation({
    mutationFn: () => api.delete("/api/admin/study/events"),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-study"] });
      setConfirmErase(false);
      toast.success("All usage events erased");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!study.data) return <Skeleton className="h-64" />;
  const s = study.data;
  const participants = new Set(s.projects.filter((p) => p.events > 0).map((p) => p.owner)).size;
  const active = s.projects.filter((p) => p.events > 0);

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>User study</CardTitle>
          <CardDescription>
            Opt-in recording of which pages people open and which actions they take, with timestamps and token counts. Never the text they write. Switch it on for the study weeks, hand participants the guide and consent text below, and export the data when the study ends.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-border px-3 py-2.5">
            <span>
              <span className="block text-[13px] font-medium">Record usage events</span>
              <span className="block text-[12px] text-muted-foreground">{s.enabled ? `On since ${s.since ? timeAgo(s.since) : "now"}. ${s.events} events so far.` : "Off. Nothing is sent by the browser."}</span>
            </span>
            <Switch checked={s.enabled} onCheckedChange={(v) => toggle.mutate(v)} />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Participants with activity" value={participants} />
            <Stat label="Projects with activity" value={active.length} />
            <Stat label="Events recorded" value={formatNumber(s.events)} />
          </div>
          <div className="flex flex-wrap gap-2">
            <a href="/api/admin/study/events.csv" className="inline-flex">
              <Button variant="secondary" type="button">
                <Download className="h-4 w-4" /> Events (CSV)
              </Button>
            </a>
            <a href="/api/admin/study/summary.json" className="inline-flex">
              <Button variant="secondary" type="button">
                <Download className="h-4 w-4" /> Per-project summary (JSON)
              </Button>
            </a>
            <Button variant="secondary" type="button" onClick={() => guide.mutate()} loading={guide.isPending}>
              <FileText className="h-4 w-4" /> Create the participant guide page
            </Button>
            <Button variant="ghost" type="button" onClick={() => setConfirmErase(true)} disabled={!s.events} className="ml-auto text-destructive">
              <Trash2 className="h-4 w-4" /> Erase events
            </Button>
          </div>
        </CardContent>
      </Card>

      <div>
        <SectionTitle>Projects</SectionTitle>
        {s.projects.length === 0 ? (
          <EmptyState icon={<FlaskConical />} title="No projects yet" description="Rows appear as participants create projects. Timing needs recording to be on." />
        ) : (
          <div className="flex flex-col gap-3">
            {[...s.projects].sort((a, b) => b.events - a.events || b.tokens_total - a.tokens_total).map((p) => <ProjectRow key={p.slug} p={p} />)}
          </div>
        )}
        <p className="mt-2 text-[12px] text-muted-foreground">Active minutes count gaps of up to 30 minutes between two events and attribute them to the page the person was on. An open tab overnight does not count.</p>
      </div>

      <div>
        <SectionTitle>Study kit</SectionTitle>
        <p className="mb-3 -mt-1 text-[13px] text-muted-foreground">Ready to adapt: fill in the study lead, retention period and your university's wording. Copy into your own documents or publish the guide as a page.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {(kit.data ?? []).map((d) => (
            <Card key={d.name} className="flex flex-col gap-2 p-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-[14px] font-semibold">{d.title}</h3>
                <div className="flex gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      void navigator.clipboard.writeText(d.content);
                      toast.success("Copied as Markdown");
                    }}
                  >
                    <ClipboardCopy className="h-3.5 w-3.5" /> Copy
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setOpenDoc(openDoc === d.name ? null : d.name)}>
                    {openDoc === d.name ? "Hide" : "Read"}
                  </Button>
                </div>
              </div>
              <p className="text-[12.5px] text-muted-foreground">
                {d.content
                  .split("\n")
                  .slice(1)
                  .find((l) => l.trim() && !l.startsWith("#"))
                  ?.slice(0, 160)}
              </p>
              {openDoc === d.name ? (
                <div className="mt-2 max-h-[420px] overflow-y-auto rounded-[var(--radius-sm)] border border-border bg-muted/30 p-4">
                  <RichMarkdown source={d.content} />
                </div>
              ) : null}
            </Card>
          ))}
        </div>
      </div>

      <ConfirmDialog
        open={confirmErase}
        onOpenChange={setConfirmErase}
        title="Erase every usage event?"
        description="Use this when a participant withdraws or after the study is analysed. Papers, tokens and accounts are untouched."
        confirmLabel="Erase"
        onConfirm={() => erase.mutate()}
        busy={erase.isPending}
      />
    </div>
  );
}

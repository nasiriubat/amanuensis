import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertCircle, CheckCircle2, ExternalLink, FileText, Loader2, Plus, Trash2, Upload, X } from "lucide-react";
import { api } from "@/lib/api";
import type { JobInfo, Paper, PaperDetail } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Markdown } from "@/components/markdown";
import { ConfirmDialog } from "@/components/dialogs";

const JOB_LABEL: Record<string, string> = {
  ingest_arxiv: "Fetching from arXiv",
  ingest_pdf: "Extracting PDF",
  learn_playbook: "Learning playbook",
  learn_profile: "Learning voice",
};

export function JobProgress({ jobs, onDismiss }: { jobs: JobInfo[]; onDismiss: (id: string) => void }) {
  if (jobs.length === 0) return null;
  return (
    <div className="mb-4 flex flex-col gap-2">
      {jobs.map((j) => {
        const running = j.status === "queued" || j.status === "running";
        return (
          <div
            key={j.id}
            className={cn(
              "card-surface flex items-center gap-3 px-4 py-2.5 text-[13px]",
              j.status === "failed" && "border-destructive/40 bg-destructive-soft/40",
              j.status === "done" && "border-success/30",
            )}
          >
            {running ? (
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
            ) : j.status === "done" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{JOB_LABEL[j.type] ?? j.type}</span>
                <span className="truncate text-muted-foreground">{j.error ?? j.message}</span>
              </div>
              {running ? (
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${Math.max(j.progress, 3)}%` }} />
                </div>
              ) : null}
            </div>
            {!running ? (
              <button onClick={() => onDismiss(j.id)} className="rounded p-1 text-subtle hover:bg-muted hover:text-foreground" aria-label="Dismiss">
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function AddPapers({
  arxivUrl,
  uploadUrl,
  onJob,
  disabled,
}: {
  arxivUrl: string;
  uploadUrl: string;
  onJob: (job: JobInfo) => void;
  disabled?: boolean;
}) {
  const [ref, setRef] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const addArxiv = useMutation({
    mutationFn: (r: string) => api.post<JobInfo>(arxivUrl, { ref: r }),
    onSuccess: (job) => {
      onJob(job);
      setRef("");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const upload = useMutation({
    mutationFn: (f: File) => api.upload<JobInfo>(uploadUrl, f),
    onSuccess: (job) => onJob(job),
    onError: (e: Error) => toast.error(e.message),
  });

  const submitRefs = () => {
    const refs = ref
      .split(/[\s,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    refs.forEach((r) => addArxiv.mutate(r));
  };

  return (
    <Card className="mb-4 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitRefs();
          }}
          className="flex flex-1 items-center gap-2"
        >
          <Input
            value={ref}
            onChange={(e) => setRef(e.target.value)}
            placeholder="arXiv id or URL, e.g. 2405.15793 or https://arxiv.org/abs/2405.15793"
            disabled={disabled}
            className="font-mono text-[12.5px]"
          />
          <Button type="submit" disabled={!ref.trim() || disabled} loading={addArxiv.isPending}>
            <Plus className="h-4 w-4" /> Add
          </Button>
        </form>
        <div className="flex items-center gap-2 text-[12px] text-subtle">
          <span className="hidden sm:inline">or</span>
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            multiple
            className="hidden"
            onChange={(e) => {
              Array.from(e.target.files ?? []).forEach((f) => upload.mutate(f));
              e.target.value = "";
            }}
          />
          <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={disabled} loading={upload.isPending}>
            <Upload className="h-4 w-4" /> Upload PDF
          </Button>
        </div>
      </div>
      <p className="mt-2 text-[12px] text-muted-foreground">
        arXiv papers come with their LaTeX source, which gives exact sections, captions and references. Several ids can be pasted at once.
      </p>
    </Card>
  );
}

function PaperCard({ p, onOpen, onDelete }: { p: Paper; onOpen: () => void; onDelete: () => void }) {
  const authors = p.authors?.length ? (p.authors.length > 3 ? `${p.authors.slice(0, 3).join(", ")} et al.` : p.authors.join(", ")) : null;
  return (
    <Card interactive={p.status === "ready"} onClick={p.status === "ready" ? onOpen : undefined} className="flex items-start gap-3 p-4">
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <FileText className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <h3 className="text-[14px] font-semibold leading-snug">{p.title}</h3>
          {p.status === "pending" ? <Badge variant="warning">Processing</Badge> : null}
          {p.status === "failed" ? <Badge variant="destructive">Failed</Badge> : null}
        </div>
        <div className="mt-0.5 text-[12.5px] text-muted-foreground">
          {authors}
          {authors && p.year ? " · " : ""}
          {p.year ?? ""}
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11.5px]">
          {p.source ? <Badge variant="outline">{p.source === "arxiv-latex" ? "arXiv LaTeX" : p.source === "arxiv-pdf" ? "arXiv PDF" : "PDF"}</Badge> : null}
          {p.word_count ? <span className="text-subtle">{formatNumber(p.word_count)} words</span> : null}
          {p.figures?.length ? <span className="text-subtle">{p.figures.length} figures/tables</span> : null}
          {p.error ? <span className="text-destructive">{p.error}</span> : null}
        </div>
      </div>
      <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
        {p.url ? (
          <a href={p.url} target="_blank" rel="noreferrer" className="rounded p-1.5 text-subtle hover:bg-muted hover:text-foreground" aria-label="Open on arXiv">
            <ExternalLink className="h-4 w-4" />
          </a>
        ) : null}
        <button onClick={onDelete} className="rounded p-1.5 text-subtle hover:bg-destructive-soft hover:text-destructive" aria-label="Remove">
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </Card>
  );
}

function PaperDialog({ url, onClose }: { url: string | null; onClose: () => void }) {
  const q = useQuery({ queryKey: ["paper", url], queryFn: () => api.get<PaperDetail>(url!), enabled: !!url });
  const [tab, setTab] = useState<"text" | "summary">("text");
  const d = q.data;
  return (
    <Dialog open={!!url} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={d?.meta.title ?? "Paper"} description={d ? `${d.meta.word_count ?? 0} words · extracted with ${d.meta.extraction}` : undefined} className="max-w-3xl">
        {d ? (
          <>
            <div className="mb-3 flex items-center gap-1">
              <Button size="sm" variant={tab === "text" ? "secondary" : "ghost"} onClick={() => setTab("text")}>
                Extracted text
              </Button>
              <Button size="sm" variant={tab === "summary" ? "secondary" : "ghost"} onClick={() => setTab("summary")} disabled={!d.summary}>
                Learned summary
              </Button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto rounded-[var(--radius-sm)] border border-border bg-muted/30 p-4">
              {tab === "text" ? (
                <Markdown source={d.markdown.slice(0, 60_000)} />
              ) : (
                <pre className="whitespace-pre-wrap font-mono text-[12px] leading-relaxed">{JSON.stringify(JSON.parse(d.summary ?? "{}"), null, 2)}</pre>
              )}
            </div>
          </>
        ) : (
          <Skeleton className="h-64" />
        )}
      </DialogContent>
    </Dialog>
  );
}

export function PaperList({ listUrl, itemUrl, emptyTitle, emptyText }: { listUrl: string; itemUrl: (id: string) => string; emptyTitle: string; emptyText: string }) {
  const papers = useQuery({ queryKey: ["papers", listUrl], queryFn: () => api.get<Paper[]>(listUrl), refetchInterval: (q) => (q.state.data?.some((p) => p.status === "pending") ? 2000 : false) });
  const [open, setOpen] = useState<string | null>(null);
  const [del, setDel] = useState<Paper | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(itemUrl(id)),
    onSuccess: () => {
      setDel(null);
      void papers.refetch();
      toast.success("Removed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (papers.isLoading) return <Skeleton className="h-24" />;
  const list = papers.data ?? [];
  return (
    <>
      {list.length === 0 ? (
        <EmptyState icon={<FileText />} title={emptyTitle} description={emptyText} className="py-10" />
      ) : (
        <div className="flex flex-col gap-2.5">
          {list.map((p) => (
            <PaperCard key={p.id} p={p} onOpen={() => setOpen(itemUrl(p.id))} onDelete={() => setDel(p)} />
          ))}
        </div>
      )}
      <PaperDialog url={open} onClose={() => setOpen(null)} />
      <ConfirmDialog
        open={!!del}
        onOpenChange={(o) => !o && setDel(null)}
        title="Remove this paper?"
        description={del ? `"${del.title}" and its extracted text will be deleted. Anything already learned from it stays.` : ""}
        confirmLabel="Remove"
        onConfirm={() => del && remove.mutate(del.id)}
        busy={remove.isPending}
      />
    </>
  );
}

export const BUDGETS = [
  { value: 15_000, label: "Small", hint: "~4k tokens per paper. Good for a first look and cheap experiments." },
  { value: 40_000, label: "Standard", hint: "~10k tokens per paper. Enough to see every section in some depth." },
  { value: 90_000, label: "Full", hint: "~22k tokens per paper. Nearly the whole paper for most conference papers." },
];

import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  BookMarked,
  ChevronLeft,
  Download,
  FileText,
  Image,
  ListTree,
  Lock,
  MessageSquareText,
  MoreHorizontal,
  Quote,
  Settings2,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { KindSummary, Profile, Project } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader, ProgressRing, SectionTitle, Skeleton } from "@/components/ui/misc";
import { MarkdownEditor } from "@/components/markdown-editor";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/dialogs";
import { projectProgress } from "./library";

const NONE = "__none__";

interface StageDef {
  key: string;
  to?: (slug: string) => string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  phase: number;
  describe: (p: Project) => string;
  status: (p: Project) => "done" | "ready" | "locked" | "soon";
}

const STAGES: StageDef[] = [
  {
    key: "sources",
    title: "Sources",
    icon: BookMarked,
    phase: 2,
    to: (slug) => `/projects/${slug}/sources`,
    describe: (p) => (p.counts.exemplars ? `${p.counts.exemplars} exemplar papers ingested.` : "Add 5 to 10 papers to learn from. arXiv links or PDFs."),
    status: (p) => (p.counts.exemplars ? "done" : "ready"),
  },
  {
    key: "playbook",
    title: "Playbook",
    icon: Sparkles,
    phase: 2,
    to: (slug) => `/projects/${slug}/playbook`,
    describe: (p) => (p.counts.playbook_files ? `${p.counts.playbook_files} of 5 playbook files learned.` : "How these papers frame contribution, structure sections and present evidence."),
    status: (p) => (p.counts.playbook_files ? "done" : p.counts.exemplars ? "ready" : "locked"),
  },
  {
    key: "interview",
    title: "Interview",
    icon: MessageSquareText,
    phase: 3,
    describe: () => "Structured rounds that turn what you built into a framed contribution.",
    status: () => "soon",
  },
  {
    key: "outline",
    title: "Outline",
    icon: ListTree,
    phase: 3,
    describe: () => "One line per paragraph. You approve it before any prose is written.",
    status: () => "soon",
  },
  {
    key: "references",
    title: "References",
    icon: Quote,
    phase: 5,
    describe: (p) => (p.counts.references ? `${p.counts.references} verified references.` : "Search Semantic Scholar, OpenAlex and arXiv. Every key is verified."),
    status: () => "soon",
  },
  {
    key: "figures",
    title: "Figures",
    icon: Image,
    phase: 6,
    describe: () => "Architecture and flow diagrams from Mermaid. Results only from your data.",
    status: () => "soon",
  },
  {
    key: "export",
    title: "Export",
    icon: Download,
    phase: 6,
    describe: () => "LNCS, ACM or your own template. PDF, LaTeX zip and DOCX.",
    status: () => "soon",
  },
];

function StageCard({ def, p }: { def: StageDef; p: Project }) {
  const status = def.status(p);
  const Icon = def.icon;
  const navigate = useNavigate();
  const href = def.to?.(p.slug);
  return (
    <Card interactive={!!href} onClick={href ? () => navigate(href) : undefined} className="relative flex gap-3.5 p-4">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-[14px] font-semibold">{def.title}</h3>
          {status === "done" ? (
            <Badge variant="success">Done</Badge>
          ) : status === "ready" ? (
            <Badge variant="primary">Next</Badge>
          ) : status === "locked" ? (
            <Badge variant="outline">Needs sources</Badge>
          ) : status === "soon" ? (
            <Badge variant="outline" className="gap-1">
              <Lock className="h-3 w-3" /> Phase {def.phase}
            </Badge>
          ) : null}
        </div>
        <p className="mt-0.5 text-[12.5px] leading-snug text-muted-foreground">{def.describe(p)}</p>
      </div>
    </Card>
  );
}

function ProjectSettingsDialog({ p, open, onOpenChange }: { p: Project; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const kinds = useQuery({ queryKey: ["kinds"], queryFn: () => api.get<KindSummary[]>("/api/kinds"), enabled: open });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<Profile[]>("/api/profiles"), enabled: open });
  const [title, setTitle] = useState(p.title);
  const [kind, setKind] = useState(p.kind);
  const [profileId, setProfileId] = useState(p.profile_id ?? NONE);
  const [venue, setVenue] = useState(p.venue ?? "");

  const save = useMutation({
    mutationFn: () =>
      api.patch<Project>(`/api/projects/${p.slug}`, {
        title: title.trim(),
        kind,
        profile_id: profileId === NONE ? null : profileId,
        clear_profile: profileId === NONE,
        venue,
      }),
    onSuccess: (np) => {
      qc.setQueryData(["project", p.slug], np);
      void qc.invalidateQueries({ queryKey: ["projects"] });
      onOpenChange(false);
      toast.success("Project updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Project settings">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <Field label="Title">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </Field>
          <Field label="Paper kind" hint="Changing the kind re-seeds unanswered interview rounds. Written sections are never touched.">
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(kinds.data ?? []).map((k) => (
                  <SelectItem key={k.slug} value={k.slug}>
                    {k.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Author profile">
              <Select value={profileId} onValueChange={setProfileId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>None</SelectItem>
                  {(profiles.data ?? []).map((pr) => (
                    <SelectItem key={pr.id} value={pr.id}>
                      {pr.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Target venue">
              <Input value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="Optional" />
            </Field>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending}>
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ProjectHomePage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const project = useQuery({ queryKey: ["project", slug], queryFn: () => api.get<Project>(`/api/projects/${slug}`) });
  const spec = useQuery({
    queryKey: ["project", slug, "file", "system-spec"],
    queryFn: () => api.get<{ content: string }>(`/api/projects/${slug}/files/system-spec`),
  });
  const [settings, setSettings] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const saveSpec = async (content: string) => {
    await api.put(`/api/projects/${slug}/files/system-spec`, { content });
    await qc.invalidateQueries({ queryKey: ["project", slug] });
  };

  const del = useMutation({
    mutationFn: () => api.delete(`/api/projects/${slug}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project deleted");
      navigate("/");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (project.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (!project.data) {
    return <p className="text-muted-foreground">Project not found.</p>;
  }
  const p = project.data;

  return (
    <div className="animate-in">
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-[12.5px] font-medium text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-3.5 w-3.5" /> Library
      </Link>
      <PageHeader
        eyebrow={
          <span className="flex items-center gap-2">
            <Badge variant="primary">{p.kind_name}</Badge>
            {p.venue ? <Badge variant="outline">{p.venue}</Badge> : null}
            {p.profile_name ? <Badge variant="outline">Voice: {p.profile_name}</Badge> : null}
          </span>
        }
        title={p.title}
        description={`Created ${new Date(p.created_at).toLocaleDateString()} · ${p.owner_name}`}
        actions={
          <>
            <div className="mr-2 flex items-center gap-2 text-[12.5px] text-muted-foreground">
              <ProgressRing value={projectProgress(p)} size={28} />
              {projectProgress(p)}%
            </div>
            <Button variant="secondary" onClick={() => setSettings(true)}>
              <Settings2 className="h-4 w-4" /> Settings
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="icon" aria-label="More">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setSettings(true)}>
                  <Settings2 /> Project settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem destructive onSelect={() => setConfirmDelete(true)}>
                  <Trash2 /> Delete project
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      <SectionTitle>Start here</SectionTitle>
      <Card className="mb-8 p-5">
        <div className="mb-4 flex items-start gap-3.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
            <FileText className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-[14.5px] font-semibold">What you built</h3>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">
              Paste the system description here. A specification generated with Claude Code works well: what it does, how it works, who it is for.
              The interview reads this first and only asks what is missing.
            </p>
          </div>
        </div>
        {spec.data ? (
          <MarkdownEditor
            value={spec.data.content}
            onSave={saveSpec}
            placeholder={"# System name\n\n## Purpose\n\n## Users\n\n## Architecture\n\n## What it does\n\n## Evaluation so far"}
            emptyHint="Switch to Edit and paste your system specification."
            minHeight={360}
          />
        ) : (
          <Skeleton className="h-[360px]" />
        )}
      </Card>

      <SectionTitle>Pipeline</SectionTitle>
      <div className="grid gap-3 sm:grid-cols-2">
        {STAGES.map((s) => (
          <StageCard key={s.key} def={s} p={p} />
        ))}
      </div>

      <ProjectSettingsDialog key={p.updated_at} p={p} open={settings} onOpenChange={setSettings} />
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this project?"
        description={`"${p.title}" and all its files, drafts and history will be removed. This cannot be undone.`}
        onConfirm={() => del.mutate()}
        busy={del.isPending}
      />
    </div>
  );
}

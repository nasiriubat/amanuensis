import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronLeft, MoreHorizontal, Sparkles, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { JobInfo, Profile } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { useJobs } from "@/lib/jobs";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader, SectionTitle, Skeleton } from "@/components/ui/misc";
import { Switch } from "@/components/ui/switch";
import { MarkdownEditor } from "@/components/markdown-editor";
import { ConfirmDialog } from "@/components/dialogs";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AddPapers, JobProgress, PaperList } from "@/components/papers";
import { BudgetPicker } from "@/pages/playbook";

export function ProfilePage() {
  const { slug = "" } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const profile = useQuery({ queryKey: ["profile", slug], queryFn: () => api.get<Profile>(`/api/profiles/${slug}`) });
  const style = useQuery({ queryKey: ["profile", slug, "style"], queryFn: () => api.get<{ content: string }>(`/api/profiles/${slug}/style`) });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [budget, setBudget] = useState(15_000);
  const { jobs, active, watch, dismiss } = useJobs({ profile_id: profile.data?.id }, (j) => {
    if (j.type === "learn_profile" && j.status === "done") void qc.invalidateQueries({ queryKey: ["profile", slug] });
  });

  const canEdit = !!profile.data && (user?.role === "admin" || profile.data.owner_id === user?.id);

  const toggleShare = useMutation({
    mutationFn: (shareable: boolean) => api.patch<Profile>(`/api/profiles/${slug}`, { shareable }),
    onSuccess: (p) => {
      qc.setQueryData(["profile", slug], p);
      void qc.invalidateQueries({ queryKey: ["profiles"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const del = useMutation({
    mutationFn: () => api.delete(`/api/profiles/${slug}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["profiles"] });
      toast.success("Profile deleted");
      navigate("/profiles");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const learn = useMutation({
    mutationFn: () => api.post<JobInfo>(`/api/profiles/${slug}/learn`, { max_chars_per_paper: budget }),
    onSuccess: (job) => watch(job),
    onError: (e: Error) => toast.error(e.message),
  });

  const saveStyle = async (content: string) => {
    await api.put(`/api/profiles/${slug}/style`, { content });
    await qc.invalidateQueries({ queryKey: ["profile", slug] });
  };

  if (profile.isLoading) return <Skeleton className="h-64" />;
  if (!profile.data) return <p className="text-muted-foreground">Profile not found.</p>;
  const p = profile.data;
  const base = `/api/profiles/${slug}/sources`;

  return (
    <div className="animate-in">
      <Link to="/profiles" className="mb-4 inline-flex items-center gap-1 text-[12.5px] font-medium text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-3.5 w-3.5" /> Author profiles
      </Link>
      <PageHeader
        eyebrow={
          <span className="flex items-center gap-2">
            {p.status === "ready" ? <Badge variant="success">Ready</Badge> : p.status === "learning" ? <Badge variant="warning">Learning</Badge> : <Badge>Empty</Badge>}
            {p.shareable ? <Badge variant="outline">Shared</Badge> : null}
          </span>
        }
        title={p.name}
        description={p.description || `Author profile by ${p.owner_name}`}
        actions={
          canEdit ? (
            <>
              <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
                Share with workspace
                <Switch checked={p.shareable} onCheckedChange={(v) => toggleShare.mutate(v)} />
              </label>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="secondary" size="icon" aria-label="More">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem destructive onSelect={() => setConfirmDelete(true)}>
                    <Trash2 /> Delete profile
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : null
        }
      />

      <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
        <div>
          <SectionTitle>Source papers</SectionTitle>
          {canEdit ? <AddPapers arxivUrl={`${base}/arxiv`} uploadUrl={`${base}/upload`} onJob={watch} /> : null}
          <JobProgress jobs={jobs} onDismiss={dismiss} />
          <PaperList
            listUrl={base}
            itemUrl={(id) => `${base}/${id}`}
            emptyTitle="No papers yet"
            emptyText="Add papers this person wrote. Five to ten give a stable picture of their voice."
          />
          {canEdit ? (
            <Card className="mt-4 p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                  <Sparkles className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="text-[14px] font-semibold">Learn the voice</h3>
                  <p className="mt-0.5 text-[12.5px] text-muted-foreground">
                    Reads a sample of each paper (introduction, one body section, conclusion) plus deterministic statistics, then writes the profile.
                  </p>
                  <div className="mt-3">
                    <BudgetPicker value={budget} onChange={setBudget} disabled={active} />
                  </div>
                  <Button className="mt-3" onClick={() => learn.mutate()} loading={learn.isPending} disabled={active || p.source_count === 0}>
                    <Sparkles className="h-4 w-4" /> {p.status === "ready" ? "Relearn voice" : "Learn voice"}
                  </Button>
                </div>
              </div>
            </Card>
          ) : null}
        </div>
        <div>
          <SectionTitle>Voice</SectionTitle>
          {style.data ? (
            <MarkdownEditor
              value={style.data.content}
              onSave={saveStyle}
              readOnly={!canEdit}
              minHeight={520}
              placeholder={"# Voice\n\n## Sentences\n\n## Openers and transitions\n\n## Hedging\n\n## Things this author never does"}
              emptyHint="Once papers are added and the voice is learned, the profile appears here. You can also write it by hand."
            />
          ) : (
            <Skeleton className="h-[520px]" />
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this profile?"
        description={`"${p.name}" and its learned voice will be removed. Projects using it keep their drafts but lose the voice reference.`}
        onConfirm={() => del.mutate()}
        busy={del.isPending}
      />
    </div>
  );
}

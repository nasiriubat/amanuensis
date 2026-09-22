import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Feather, FileText, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { Profile, Project } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, PageHeader, ProgressRing, SectionTitle, Skeleton } from "@/components/ui/misc";
import { NewProfileDialog, NewProjectDialog } from "@/components/dialogs";
import { useAuth } from "@/lib/auth";

const STAGES = ["setup", "sources", "playbook", "interview", "outline", "drafting", "review", "export"];

export function projectProgress(p: Project): number {
  let score = 0;
  if (p.counts.has_spec) score += 1;
  if (p.counts.exemplars > 0) score += 1;
  if (p.counts.playbook_files > 0) score += 1;
  if (p.counts.sections > 0) score += 2;
  if (p.counts.references > 0) score += 1;
  const idx = Math.max(STAGES.indexOf(p.stage), 0);
  return Math.min(100, Math.round(((score + idx) / (6 + STAGES.length - 1)) * 100));
}

export function ProjectCard({ p }: { p: Project }) {
  const navigate = useNavigate();
  return (
    <Card interactive onClick={() => navigate(`/projects/${p.slug}`)} className="group flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
            <Badge variant="primary">{p.kind_name}</Badge>
            {p.venue ? <Badge variant="outline">{p.venue}</Badge> : null}
          </div>
          <h3 className="text-[15px] font-semibold leading-snug">{p.title}</h3>
        </div>
        <ProgressRing value={projectProgress(p)} />
      </div>
      <div className="mt-4 flex items-center gap-4 text-[12.5px] text-muted-foreground">
        <span>{p.counts.exemplars} exemplar{p.counts.exemplars === 1 ? "" : "s"}</span>
        <span>{p.counts.sections} section{p.counts.sections === 1 ? "" : "s"}</span>
        <span>{p.counts.references} ref{p.counts.references === 1 ? "" : "s"}</span>
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-[12px] text-subtle">
        <span>
          {p.profile_name ? `Voice: ${p.profile_name}` : "No author profile"} · updated {timeAgo(p.updated_at)}
        </span>
        <ArrowRight className="h-4 w-4 opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
    </Card>
  );
}

export function ProfileCard({ p }: { p: Profile }) {
  const navigate = useNavigate();
  const status =
    p.status === "ready" ? <Badge variant="success">Ready</Badge> : p.status === "learning" ? <Badge variant="warning">Learning</Badge> : <Badge>Empty</Badge>;
  return (
    <Card interactive onClick={() => navigate(`/profiles/${p.slug}`)} className="flex items-center gap-4 p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
        <Feather className="h-4.5 w-4.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="truncate text-[14.5px] font-semibold">{p.name}</h3>
          {status}
          {p.shareable ? <Badge variant="outline">Shared</Badge> : null}
        </div>
        <p className="mt-0.5 truncate text-[12.5px] text-muted-foreground">
          {p.source_count} source paper{p.source_count === 1 ? "" : "s"} · by {p.owner_name}
        </p>
      </div>
    </Card>
  );
}

export function LibraryPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.get<Project[]>("/api/projects") });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<Profile[]>("/api/profiles") });
  const [newProject, setNewProject] = useState(false);
  const [newProfile, setNewProfile] = useState(false);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  return (
    <div className="animate-in">
      <PageHeader
        title={`${greeting}, ${user?.display_name?.split(" ")[0] ?? ""}`}
        description="Pick up a paper where you left it, or start a new one."
        actions={
          <>
            <Button variant="secondary" onClick={() => setNewProfile(true)}>
              <Feather className="h-4 w-4" /> New profile
            </Button>
            <Button onClick={() => setNewProject(true)}>
              <Plus className="h-4 w-4" /> New project
            </Button>
          </>
        }
      />

      <SectionTitle>Projects</SectionTitle>
      {projects.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[168px]" />
          ))}
        </div>
      ) : projects.data && projects.data.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.map((p) => (
            <ProjectCard key={p.id} p={p} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<FileText />}
          title="No projects yet"
          description="A project is one paper. Add the papers you want to learn from, describe what you built, and the interview takes it from there."
          action={
            <Button onClick={() => setNewProject(true)}>
              <Plus className="h-4 w-4" /> Create your first project
            </Button>
          }
        />
      )}

      <div className="mt-10">
        <SectionTitle
          right={
            <Link to="/profiles" className="text-[12.5px] font-medium text-primary hover:underline">
              See all
            </Link>
          }
        >
          Author profiles
        </SectionTitle>
        {profiles.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-[72px]" />
            ))}
          </div>
        ) : profiles.data && profiles.data.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {profiles.data.slice(0, 6).map((p) => (
              <ProfileCard key={p.id} p={p} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Feather />}
            title="No author profiles"
            description="Upload someone's papers, yours or a colleague's, and the tool learns how they write. Projects then draft in that voice."
            action={
              <Button variant="secondary" onClick={() => setNewProfile(true)}>
                <Plus className="h-4 w-4" /> New profile
              </Button>
            }
            className="py-8"
          />
        )}
      </div>

      <NewProjectDialog open={newProject} onOpenChange={setNewProject} onCreated={(p) => navigate(`/projects/${p.slug}`)} />
      <NewProfileDialog open={newProfile} onOpenChange={setNewProfile} onCreated={(p) => navigate(`/profiles/${p.slug}`)} />
    </div>
  );
}

export function ProfilesPage() {
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<Profile[]>("/api/profiles") });
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  return (
    <div className="animate-in">
      <PageHeader
        title="Author profiles"
        description="Each profile captures one person's tone and habits. Use your own, or learn from a colleague whose papers get accepted."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New profile
          </Button>
        }
      />
      {profiles.data && profiles.data.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {profiles.data.map((p) => (
            <ProfileCard key={p.id} p={p} />
          ))}
        </div>
      ) : profiles.isLoading ? (
        <Skeleton className="h-[72px]" />
      ) : (
        <EmptyState icon={<Feather />} title="No author profiles" description="Create one to start learning a voice." />
      )}
      <NewProfileDialog open={open} onOpenChange={setOpen} onCreated={(p) => navigate(`/profiles/${p.slug}`)} />
    </div>
  );
}

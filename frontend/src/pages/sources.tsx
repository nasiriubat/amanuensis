import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { useJobs } from "@/lib/jobs";
import { Button } from "@/components/ui/button";
import { PageHeader, SectionTitle, Skeleton } from "@/components/ui/misc";
import { AddPapers, JobProgress, PaperList } from "@/components/papers";
import { NextStepBar } from "@/components/flow";
import { LiteratureScan } from "@/components/literature-scan";

export function SourcesPage() {
  const { slug = "" } = useParams();
  const navigate = useNavigate();
  const project = useQuery({ queryKey: ["project", slug], queryFn: () => api.get<Project>(`/api/projects/${slug}`) });
  const { jobs, watch, dismiss } = useJobs({ project_id: project.data?.id });

  if (project.isLoading) return <Skeleton className="h-64" />;
  if (!project.data) return <p className="text-muted-foreground">Project not found.</p>;
  const p = project.data;
  const base = `/api/projects/${slug}/exemplars`;

  return (
    <div className="animate-in">
      <Link to={`/projects/${slug}`} className="mb-4 inline-flex items-center gap-1 text-[12.5px] font-medium text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-3.5 w-3.5" /> {p.title}
      </Link>
      <PageHeader
        title="Sources"
        description="Exemplar papers the playbook is learned from. Five to ten papers of the kind you are writing, ideally from the venue you target. Any exemplar can also be cited with one click."
        actions={
          <Button variant="secondary" onClick={() => navigate(`/projects/${slug}/playbook`)} disabled={!p.counts.exemplars}>
            <Sparkles className="h-4 w-4" /> Go to playbook
          </Button>
        }
      />
      <div className="mb-6">
        <LiteratureScan slug={slug} projectId={p.id} />
      </div>
      <SectionTitle>Add papers you already know</SectionTitle>
      <AddPapers arxivUrl={`${base}/arxiv`} uploadUrl={`${base}/upload`} onJob={watch} />
      <JobProgress jobs={jobs.filter((j) => j.type !== "scan")} onDismiss={dismiss} />
      <SectionTitle>Exemplars</SectionTitle>
      <PaperList
        listUrl={base}
        itemUrl={(id) => `${base}/${id}`}
        citeUrl={(id) => `${base}/${id}/cite`}
        emptyTitle="No exemplars yet"
        emptyText="Let the scan suggest papers, paste arXiv ids of papers you admire in this genre, or upload PDFs. The tool reads them and learns how they are built."
      />
      <NextStepBar p={p} current="sources" />
    </div>
  );
}

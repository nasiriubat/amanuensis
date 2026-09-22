import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, FileText } from "lucide-react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { PageHeader, Skeleton } from "@/components/ui/misc";
import { MarkdownEditor } from "@/components/markdown-editor";
import { NextStepBar } from "@/components/flow";

export function SpecPage() {
  const { slug = "" } = useParams();
  const qc = useQueryClient();
  const project = useQuery({ queryKey: ["project", slug], queryFn: () => api.get<Project>(`/api/projects/${slug}`) });
  const spec = useQuery({ queryKey: ["project", slug, "file", "system-spec"], queryFn: () => api.get<{ content: string }>(`/api/projects/${slug}/files/system-spec`) });

  const save = async (content: string) => {
    await api.put(`/api/projects/${slug}/files/system-spec`, { content });
    await qc.invalidateQueries({ queryKey: ["project", slug] });
  };

  if (project.isLoading) return <Skeleton className="h-64" />;
  if (!project.data) return <p className="text-muted-foreground">Project not found.</p>;
  const p = project.data;

  return (
    <div className="animate-in">
      <Link to={`/projects/${slug}`} className="mb-4 inline-flex items-center gap-1 text-[12.5px] font-medium text-muted-foreground hover:text-foreground">
        <ChevronLeft className="h-3.5 w-3.5" /> {p.title}
      </Link>
      <PageHeader
        title="What you built"
        description="The system specification. The interview reads it to skip what you already said, and the draft may only state what is in here, in your answers, or in the facts."
      />
      <Card className="p-5">
        <div className="mb-4 flex items-start gap-3.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
            <FileText className="h-4 w-4" />
          </span>
          <div className="text-[12.5px] text-muted-foreground">
            A specification generated with Claude Code or similar works well: purpose, users, architecture, what it does, what has been evaluated so far.
            Numbers and names you write here become facts the paper can use, so be exact.
          </div>
        </div>
        {spec.data ? (
          <MarkdownEditor
            value={spec.data.content}
            onSave={save}
            placeholder={"# System name\n\n## Purpose\n\n## Users\n\n## Architecture\n\n## What it does\n\n## Evaluation so far"}
            emptyHint="Switch to Edit and paste your system specification."
            minHeight={460}
          />
        ) : (
          <Skeleton className="h-[460px]" />
        )}
      </Card>
      <NextStepBar p={p} current="spec" />
    </div>
  );
}

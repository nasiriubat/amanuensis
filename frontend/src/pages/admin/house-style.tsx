import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SectionTitle, Skeleton } from "@/components/ui/misc";
import { MarkdownEditor } from "@/components/markdown-editor";

export function HouseStylePage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["house-style"], queryFn: () => api.get<{ content: string }>("/api/house-style") });
  const save = async (content: string) => {
    await api.put("/api/house-style", { content });
    await qc.invalidateQueries({ queryKey: ["house-style"] });
  };
  return (
    <div>
      <SectionTitle>House style</SectionTitle>
      <p className="mb-4 -mt-1 max-w-2xl text-[13px] text-muted-foreground">
        Injected into every drafting and critique prompt after the author profile. The profile decides tone, this file decides hygiene:
        banned phrases, sentence length, punctuation. The prose lint in the editor reads the same rules.
      </p>
      {q.data ? <MarkdownEditor value={q.data.content} onSave={save} minHeight={560} /> : <Skeleton className="h-[560px]" />}
    </div>
  );
}

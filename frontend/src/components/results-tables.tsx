import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Table2, Trash2, Upload } from "lucide-react";
import { api } from "@/lib/api";
import type { ResultTable } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, SectionTitle, Skeleton } from "@/components/ui/misc";
import { ConfirmDialog } from "@/components/dialogs";

/**
 * Experiment results as CSV or XLSX. Each file becomes a table the Studio can insert, and the
 * numbers in it become facts the draft may state. Mounted on the Figures page.
 */
export function ResultsTables({ slug }: { slug: string }) {
  const qc = useQueryClient();
  const tables = useQuery({ queryKey: ["results", slug], queryFn: () => api.get<ResultTable[]>(`/api/projects/${slug}/results`) });
  const [open, setOpen] = useState<string | null>(null);
  const [del, setDel] = useState<ResultTable | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const preview = useQuery({
    queryKey: ["results-preview", slug, open],
    queryFn: () => api.get<{ columns: string[]; rows: string[][]; total: number }>(`/api/projects/${slug}/results/${open}/preview`),
    enabled: !!open,
  });
  const upload = useMutation({
    mutationFn: (f: File) => api.upload<ResultTable>(`/api/projects/${slug}/results/upload`, f),
    onSuccess: (t) => {
      void qc.invalidateQueries({ queryKey: ["results", slug] });
      setOpen(t.name);
      toast.success(`${t.title}: ${t.rows} rows, ${t.columns.length} columns. Give it a caption.`);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const caption = useMutation({
    mutationFn: ({ name, caption }: { name: string; caption: string }) => api.patch<ResultTable>(`/api/projects/${slug}/results/${name}`, { caption }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["results", slug] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: (name: string) => api.delete(`/api/projects/${slug}/results/${name}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["results", slug] });
      setDel(null);
      setOpen(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const list = tables.data ?? [];

  return (
    <div className="mt-10">
      <SectionTitle
        right={
          <>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.tsv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              multiple
              className="hidden"
              onChange={(e) => {
                Array.from(e.target.files ?? []).forEach((f) => upload.mutate(f));
                e.target.value = "";
              }}
            />
            <Button size="sm" variant="secondary" onClick={() => fileRef.current?.click()} loading={upload.isPending}>
              <Upload className="h-3.5 w-3.5" /> Upload CSV or XLSX
            </Button>
          </>
        }
      >
        Results tables
      </SectionTitle>
      <p className="mb-3 -mt-1 text-[13px] text-muted-foreground">
        Your measurements as a spreadsheet: one header row, one row per observation, first sheet only. The numbers become facts the draft may state, and the Studio inserts any table with its caption from the Figure menu. Nothing is computed beyond what the cells say.
      </p>
      {tables.isLoading ? (
        <Skeleton className="h-24" />
      ) : list.length === 0 ? (
        <EmptyState icon={<Table2 />} title="No results yet" description="Upload a CSV or XLSX when you have measurements. Until then, results in the draft stay as [NEEDS] placeholders." className="py-8" />
      ) : (
        <div className="flex flex-col gap-2.5">
          {list.map((t) => {
            const isOpen = open === t.name;
            return (
              <Card key={t.name} className="p-4">
                <div className="flex flex-wrap items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <Table2 className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <button onClick={() => setOpen(isOpen ? null : t.name)} className="text-left">
                      <div className="text-[14px] font-semibold leading-snug">{t.caption || t.title}</div>
                      <div className="mt-0.5 text-[12.5px] text-muted-foreground">
                        {t.rows} rows · {t.columns.join(", ")} · from {t.source_file} · insert as <span className="font-mono">{`{#tbl:${t.name}}`}</span>
                      </div>
                    </button>
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-[11.5px] text-subtle">
                      {t.summary.map((s) => (
                        <span key={s.column}>
                          {s.column}: {s.kind === "number" ? `${s.min} to ${s.max}, mean ${s.mean}` : `${s.distinct} values`}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button onClick={() => setDel(t)} className="rounded p-1.5 text-subtle hover:bg-destructive-soft hover:text-destructive" aria-label="Remove">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                {isOpen ? (
                  <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3">
                    <label className="flex flex-col gap-1 text-[12.5px] font-medium">
                      Caption, as it will appear under the table
                      <Input
                        defaultValue={t.caption}
                        placeholder="e.g. Time to first fix per condition, seconds"
                        onBlur={(e) => e.target.value.trim() !== t.caption && caption.mutate({ name: t.name, caption: e.target.value })}
                      />
                    </label>
                    {preview.data ? (
                      <div className="overflow-x-auto rounded-[var(--radius-sm)] border border-border">
                        <table className="w-full text-[12.5px]">
                          <thead className="bg-muted/50 text-left text-[11.5px] text-subtle">
                            <tr>
                              {preview.data.columns.map((c) => (
                                <th key={c} className="px-3 py-1.5 font-medium">
                                  {c}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {preview.data.rows.slice(0, 8).map((r, i) => (
                              <tr key={i} className="border-t border-border">
                                {r.map((c, j) => (
                                  <td key={j} className="px-3 py-1 tabular-nums">
                                    {c}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {preview.data.total > 8 ? <div className="px-3 py-1.5 text-[11.5px] text-subtle">and {preview.data.total - 8} more rows</div> : null}
                      </div>
                    ) : (
                      <Skeleton className="h-24" />
                    )}
                  </div>
                ) : null}
              </Card>
            );
          })}
        </div>
      )}
      <ConfirmDialog
        open={!!del}
        onOpenChange={(o) => !o && setDel(null)}
        title={`Remove “${del?.caption || del?.title}”?`}
        description="Tables already inserted in sections stay as text. Facts extracted from it stay until you run the outline again."
        confirmLabel="Remove"
        onConfirm={() => del && remove.mutate(del.name)}
        busy={remove.isPending}
      />
    </div>
  );
}

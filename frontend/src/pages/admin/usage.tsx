import { useQuery } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { UsageRow, UsageSummary } from "@/lib/types";
import { formatNumber, timeAgo } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { EmptyState, SectionTitle, Skeleton, Stat } from "@/components/ui/misc";

function RowsTable({ title, rows }: { title: string; rows: UsageRow[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wide text-subtle">{title}</div>
      {rows.length === 0 ? (
        <div className="px-4 py-6 text-center text-[13px] text-subtle">No calls yet</div>
      ) : (
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11.5px] text-subtle">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-2 py-2 text-right font-medium">Calls</th>
              <th className="px-2 py-2 text-right font-medium">In</th>
              <th className="px-2 py-2 text-right font-medium">Out</th>
              <th className="px-4 py-2 text-right font-medium">Cached</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-t border-border">
                <td className="px-4 py-2">
                  <span className="font-medium">{r.label}</span>
                  {r.errors ? <span className="ml-2 text-[11.5px] text-destructive">{r.errors} failed</span> : null}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">{r.calls}</td>
                <td className="px-2 py-2 text-right tabular-nums">{formatNumber(r.input_tokens)}</td>
                <td className="px-2 py-2 text-right tabular-nums">{formatNumber(r.output_tokens)}</td>
                <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">{formatNumber(r.cached_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export function UsagePage() {
  const q = useQuery({ queryKey: ["usage"], queryFn: () => api.get<UsageSummary>("/api/usage/summary"), refetchInterval: 30_000 });
  if (q.isLoading || !q.data) return <Skeleton className="h-64" />;
  const u = q.data;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <SectionTitle>Totals</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-3">
          <Stat label="LLM calls" value={u.total_calls} />
          <Stat label="Input tokens" value={formatNumber(u.total_input_tokens)} />
          <Stat label="Output tokens" value={formatNumber(u.total_output_tokens)} />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <RowsTable title="By provider" rows={u.by_provider} />
        <RowsTable title="By purpose" rows={u.by_purpose} />
      </div>
      <RowsTable title="By project" rows={u.by_project} />
      <div>
        <SectionTitle>Recent calls</SectionTitle>
        {u.recent.length === 0 ? (
          <EmptyState title="No calls yet" description="Test a purpose on the Models tab and it appears here." className="py-8" />
        ) : (
          <Card className="divide-y divide-border">
            {u.recent.map((c) => (
              <div key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-[12.5px]">
                {c.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : <AlertCircle className="h-3.5 w-3.5 text-destructive" />}
                <span className="font-mono font-medium">{c.purpose}</span>
                <span className="text-muted-foreground">
                  {c.provider} · <span className="font-mono">{c.model}</span>
                </span>
                <span className="ml-auto tabular-nums text-muted-foreground">
                  {c.input_tokens} in · {c.output_tokens} out · {c.duration_ms} ms
                </span>
                <span className="text-subtle">{timeAgo(c.created_at)}</span>
                {c.error ? <span className="basis-full truncate text-destructive">{c.error}</span> : null}
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}

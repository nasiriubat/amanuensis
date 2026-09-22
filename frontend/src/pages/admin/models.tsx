import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, FlaskConical, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { LlmTestResult, Provider, PurposeAssignment } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SectionTitle, Skeleton } from "@/components/ui/misc";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";

const NONE = "__none__";

function PurposeCard({ a, providers }: { a: PurposeAssignment; providers: Provider[] }) {
  const qc = useQueryClient();
  const [providerId, setProviderId] = useState(a.provider_id ?? NONE);
  const [model, setModel] = useState(a.model ?? "");
  const [filter, setFilter] = useState("");
  const [test, setTest] = useState<LlmTestResult | null>(null);

  const provider = providers.find((p) => p.id === providerId);
  const models = useMemo(() => {
    const list = provider?.models ?? [];
    const f = filter.trim().toLowerCase();
    return f ? list.filter((m) => m.id.toLowerCase().includes(f) || (m.name ?? "").toLowerCase().includes(f)) : list;
  }, [provider, filter]);

  const dirty = (a.provider_id ?? NONE) !== providerId || (a.model ?? "") !== model;

  const save = useMutation({
    mutationFn: () =>
      api.put<PurposeAssignment>(`/api/purposes/${a.purpose}`, {
        provider_id: providerId === NONE ? null : providerId,
        model: providerId === NONE ? null : model.trim() || null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["purposes"] });
      toast.success(`${a.purpose} updated`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const runTest = useMutation({
    mutationFn: () => api.post<LlmTestResult>("/api/llm/test", { purpose: a.purpose }),
    onSuccess: (r) => setTest(r),
    onError: (e: Error) => {
      setTest(null);
      toast.error(e.message);
    },
  });

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-mono text-[14px] font-semibold">{a.purpose}</h3>
            {a.provider_name && a.model ? (
              <Badge variant="success" className="gap-1">
                <CheckCircle2 className="h-3 w-3" /> {a.provider_name}
              </Badge>
            ) : (
              <Badge variant="warning">Unassigned</Badge>
            )}
          </div>
          <p className="mt-1 max-w-xl text-[12.5px] text-muted-foreground">{a.description}</p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => runTest.mutate()} loading={runTest.isPending} disabled={!a.provider_id || !a.model || dirty}>
          <FlaskConical className="h-3.5 w-3.5" /> Test
        </Button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[200px_1fr_auto]">
        <Select
          value={providerId}
          onValueChange={(v) => {
            setProviderId(v);
            setModel("");
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="Provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Unassigned</SelectItem>
            {providers
              .filter((p) => p.enabled)
              .map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>

        {provider && provider.models.length > 0 ? (
          <Select value={model || undefined} onValueChange={setModel}>
            <SelectTrigger disabled={!provider}>
              <SelectValue placeholder="Choose a model" />
            </SelectTrigger>
            <SelectContent>
              <div className="sticky top-0 z-10 border-b border-border bg-card p-1.5">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle" />
                  <Input
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    onKeyDown={(e) => e.stopPropagation()}
                    placeholder="Filter models"
                    className="h-8 pl-7 text-[12.5px]"
                  />
                </div>
              </div>
              <SelectGroup>
                <SelectLabel>
                  {models.length} of {provider.models.length}
                </SelectLabel>
                {models.slice(0, 300).map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    <span className="font-mono text-[12.5px]">{m.id}</span>
                    {m.context_window ? <span className="ml-2 text-[11px] text-subtle">{Math.round(m.context_window / 1000)}k</span> : null}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        ) : (
          <Input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={!provider}
            placeholder={provider ? "Model id (list unavailable, type it)" : "Pick a provider first"}
            className="font-mono text-[12.5px]"
          />
        )}

        <Button onClick={() => save.mutate()} disabled={!dirty || (providerId !== NONE && !model.trim())} loading={save.isPending}>
          Save
        </Button>
      </div>

      {test ? (
        <div className="mt-4 rounded-[var(--radius-sm)] border border-success/30 bg-success-soft/60 p-3 text-[12.5px]">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground">
            <span className="font-medium text-foreground">{test.model}</span>
            <span>{test.duration_ms} ms</span>
            <span>
              {test.input_tokens} in · {test.output_tokens} out
            </span>
          </div>
          <p className="mt-1.5 italic text-foreground">“{test.text}”</p>
        </div>
      ) : null}
    </Card>
  );
}

export function ModelsPage() {
  const purposes = useQuery({ queryKey: ["purposes"], queryFn: () => api.get<PurposeAssignment[]>("/api/purposes") });
  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api.get<Provider[]>("/api/providers") });

  return (
    <div>
      <SectionTitle>Model per purpose</SectionTitle>
      <p className="mb-4 -mt-1 text-[13px] text-muted-foreground">
        Each purpose gets the model that suits it. Projects and individual sections can override these defaults later.
      </p>
      {purposes.isLoading || providers.isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {(purposes.data ?? []).map((a) => (
            <PurposeCard key={`${a.purpose}-${a.provider_id}-${a.model}`} a={a} providers={providers.data ?? []} />
          ))}
        </div>
      )}
    </div>
  );
}

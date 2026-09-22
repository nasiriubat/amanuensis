import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertCircle, KeyRound, MoreHorizontal, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Adapter, Provider, ProviderPreset } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, SectionTitle, Skeleton } from "@/components/ui/misc";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/dialogs";

const CUSTOM = "__custom__";

function ProviderDialog({ open, onOpenChange, existing }: { open: boolean; onOpenChange: (o: boolean) => void; existing?: Provider }) {
  const qc = useQueryClient();
  const presets = useQuery({ queryKey: ["provider-presets"], queryFn: () => api.get<ProviderPreset[]>("/api/providers/presets"), enabled: open && !existing });
  const [preset, setPreset] = useState(CUSTOM);
  const [name, setName] = useState(existing?.name ?? "");
  const [adapter, setAdapter] = useState<Adapter>(existing?.adapter ?? "openai_compat");
  const [baseUrl, setBaseUrl] = useState(existing?.base_url ?? "");
  const [apiKey, setApiKey] = useState("");

  const applyPreset = (value: string) => {
    setPreset(value);
    const p = presets.data?.find((x) => x.name === value);
    if (p) {
      setName(p.name);
      setAdapter(p.adapter);
      setBaseUrl(p.base_url ?? "");
    }
  };

  const save = useMutation({
    mutationFn: () =>
      existing
        ? api.patch<Provider>(`/api/providers/${existing.id}`, {
            name: name.trim(),
            base_url: baseUrl.trim(),
            ...(apiKey ? { api_key: apiKey } : {}),
          })
        : api.post<Provider>("/api/providers", { name: name.trim(), adapter, base_url: baseUrl.trim() || null, api_key: apiKey || null }),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["providers"] });
      onOpenChange(false);
      if (p.models_error) toast.warning(`Saved, but fetching models failed: ${p.models_error}`);
      else toast.success(`${p.name} saved. ${p.models.length} models available.`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={existing ? `Edit ${existing.name}` : "Add provider"}
        description="Keys are encrypted at rest and never sent to the browser. Models are fetched when you save."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
          className="flex flex-col gap-4"
        >
          {!existing ? (
            <Field label="Preset">
              <Select value={preset} onValueChange={applyPreset}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={CUSTOM}>Custom endpoint</SelectItem>
                  {(presets.data ?? []).map((p) => (
                    <SelectItem key={p.name} value={p.name}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          ) : null}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name">
              <Input value={name} onChange={(e) => setName(e.target.value)} required />
            </Field>
            <Field label="Protocol">
              <Select value={adapter} onValueChange={(v) => setAdapter(v as Adapter)} disabled={!!existing}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai_compat">OpenAI-compatible</SelectItem>
                  <SelectItem value="anthropic">Anthropic</SelectItem>
                </SelectContent>
              </Select>
            </Field>
          </div>
          <Field label="Base URL" hint="Leave empty for the provider's default.">
            <Input
              type="url"
              name="provider-base-url"
              autoComplete="off"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.example.com/v1"
              className="font-mono text-[12.5px]"
            />
          </Field>
          <Field label={existing?.has_key ? `API key (currently ····${existing.key_hint})` : "API key"} hint={existing ? "Leave empty to keep the current key." : undefined}>
            {/* new-password is the only autocomplete value Chromium honours for password inputs. */}
            <Input
              type="password"
              name="provider-api-key"
              autoComplete="new-password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="font-mono text-[12.5px]"
            />
          </Field>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={save.isPending} disabled={!name.trim()}>
              {existing ? "Save" : "Add provider"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ProviderRow({ p }: { p: Provider }) {
  const qc = useQueryClient();
  const [edit, setEdit] = useState(false);
  const [confirm, setConfirm] = useState(false);

  const refresh = useMutation({
    mutationFn: () => api.post<Provider>(`/api/providers/${p.id}/refresh-models`),
    onSuccess: (np) => {
      void qc.invalidateQueries({ queryKey: ["providers"] });
      if (np.models_error) toast.error(np.models_error);
      else toast.success(`${np.models.length} models`);
    },
  });
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.patch<Provider>(`/api/providers/${p.id}`, { enabled }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["providers"] }),
  });
  const del = useMutation({
    mutationFn: () => api.delete(`/api/providers/${p.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["providers"] });
      void qc.invalidateQueries({ queryKey: ["purposes"] });
      toast.success("Provider removed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Card className="flex flex-wrap items-center gap-4 p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted font-mono text-[13px] font-semibold text-muted-foreground">
        {p.name.slice(0, 2).toUpperCase()}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-[14.5px] font-semibold">{p.name}</h3>
          <Badge variant="outline">{p.adapter === "anthropic" ? "Anthropic" : "OpenAI-compatible"}</Badge>
          {p.has_key ? (
            <Badge variant="success" className="gap-1">
              <KeyRound className="h-3 w-3" /> ····{p.key_hint}
            </Badge>
          ) : (
            <Badge variant="warning">No key</Badge>
          )}
          {!p.enabled ? <Badge>Disabled</Badge> : null}
        </div>
        <div className="mt-0.5 truncate font-mono text-[12px] text-muted-foreground">{p.base_url ?? "default endpoint"}</div>
        <div className="mt-1 text-[12px] text-subtle">
          {p.models_error ? (
            <span className="inline-flex items-center gap-1 text-destructive">
              <AlertCircle className="h-3 w-3" /> {p.models_error}
            </span>
          ) : (
            <>
              {p.models.length} models · fetched {timeAgo(p.models_fetched_at)}
            </>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Switch checked={p.enabled} onCheckedChange={(v) => toggle.mutate(v)} aria-label="Enabled" />
        <Button variant="secondary" size="sm" onClick={() => refresh.mutate()} loading={refresh.isPending}>
          <RefreshCw className="h-3.5 w-3.5" /> Models
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="More">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setEdit(true)}>
              <KeyRound /> Edit key and URL
            </DropdownMenuItem>
            <DropdownMenuItem destructive onSelect={() => setConfirm(true)}>
              <Trash2 /> Remove
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {edit ? <ProviderDialog open onOpenChange={setEdit} existing={p} /> : null}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Remove ${p.name}?`}
        description="Purposes assigned to this provider become unassigned until you pick another."
        confirmLabel="Remove"
        onConfirm={() => del.mutate()}
        busy={del.isPending}
      />
    </Card>
  );
}

export function ProvidersPage() {
  const providers = useQuery({ queryKey: ["providers"], queryFn: () => api.get<Provider[]>("/api/providers") });
  const [add, setAdd] = useState(false);
  return (
    <div>
      <SectionTitle
        right={
          <Button size="sm" onClick={() => setAdd(true)}>
            <Plus className="h-3.5 w-3.5" /> Add provider
          </Button>
        }
      >
        LLM providers
      </SectionTitle>
      {providers.isLoading ? (
        <Skeleton className="h-20" />
      ) : providers.data && providers.data.length > 0 ? (
        <div className="flex flex-col gap-3">
          {providers.data.map((p) => (
            <ProviderRow key={p.id} p={p} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<KeyRound />}
          title="No providers yet"
          description="Add OpenAI, OpenRouter, Anthropic or any OpenAI-compatible endpoint. Then assign models to purposes on the Models tab."
          action={
            <Button onClick={() => setAdd(true)}>
              <Plus className="h-4 w-4" /> Add provider
            </Button>
          }
        />
      )}
      {add ? <ProviderDialog open onOpenChange={setAdd} /> : null}
    </div>
  );
}

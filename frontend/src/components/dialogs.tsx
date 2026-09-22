import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { KindSummary, Profile, Project } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

const NONE = "__none__";

export function NewProjectDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated: (p: Project) => void }) {
  const qc = useQueryClient();
  const kinds = useQuery({ queryKey: ["kinds"], queryFn: () => api.get<KindSummary[]>("/api/kinds"), enabled: open });
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<Profile[]>("/api/profiles"), enabled: open });
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState("tool-paper");
  const [profileId, setProfileId] = useState(NONE);
  const [venue, setVenue] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api.post<Project>("/api/projects", {
        title: title.trim(),
        kind,
        profile_id: profileId === NONE ? null : profileId,
        venue: venue.trim() || null,
      }),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["projects"] });
      onOpenChange(false);
      setTitle("");
      setVenue("");
      onCreated(p);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const selectedKind = kinds.data?.find((k) => k.slug === kind);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="New project" description="One project is one paper. You can change everything later.">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <Field label="Working title">
            <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Tender Scout: matching public tenders to SMEs" required />
          </Field>
          <Field label="Paper kind" hint={selectedKind?.summary}>
            <Select value={kind} onValueChange={setKind}>
              <SelectTrigger>
                <SelectValue placeholder="Choose a kind" />
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
            <Field label="Author profile" hint="Whose voice the drafts follow.">
              <Select value={profileId} onValueChange={setProfileId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>None yet</SelectItem>
                  {(profiles.data ?? []).map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Target venue" hint="Optional. Can be suggested later.">
              <Input value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="e.g. ICSE 2027 Demo" />
            </Field>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={!title.trim()}>
              Create project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function NewProfileDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (o: boolean) => void; onCreated?: (p: Profile) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [shareable, setShareable] = useState(false);

  const create = useMutation({
    mutationFn: () => api.post<Profile>("/api/profiles", { name: name.trim(), description: description.trim() || null, shareable }),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["profiles"] });
      onOpenChange(false);
      setName("");
      setDescription("");
      onCreated?.(p);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="New author profile" description="A profile learns one person's voice from their papers and can be reused across projects.">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <Field label="Name">
            <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Nasir" required />
          </Field>
          <Field label="Notes" hint="Optional. Who this is, what they write about.">
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} className="min-h-[72px]" />
          </Field>
          <label className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-border px-3 py-2.5">
            <span>
              <span className="block text-[13px] font-medium">Share with the workspace</span>
              <span className="block text-[12px] text-muted-foreground">Other members can use this profile in their projects.</span>
            </span>
            <Switch checked={shareable} onCheckedChange={setShareable} />
          </label>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={create.isPending} disabled={!name.trim()}>
              Create profile
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Delete",
  onConfirm,
  busy,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  busy?: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description={description} className="max-w-md">
        <DialogFooter className="mt-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

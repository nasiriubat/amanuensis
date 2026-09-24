import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, MoreHorizontal, Plus, ShieldCheck, Trash2, UserRound, UserX } from "lucide-react";
import { api } from "@/lib/api";
import type { Role, User } from "@/lib/types";
import { initials, timeAgo } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { SectionTitle, Skeleton } from "@/components/ui/misc";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { ConfirmDialog } from "@/components/dialogs";

function randomPassword(): string {
  const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const arr = new Uint32Array(14);
  crypto.getRandomValues(arr);
  return Array.from(arr, (n) => chars[n % chars.length]).join("");
}

function NewUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("user");
  const [password, setPassword] = useState(randomPassword);
  const [created, setCreated] = useState<{ email: string; password: string; emailed: boolean; error: string | null } | null>(null);
  const mail = useQuery({ queryKey: ["admin-mail"], queryFn: () => api.get<{ enabled: boolean; host: string; from_addr: string }>("/api/admin/mail"), enabled: open });
  const mailReady = !!(mail.data?.enabled && mail.data.host && mail.data.from_addr);
  const [sendEmail, setSendEmail] = useState(true);

  const create = useMutation({
    mutationFn: () =>
      api.post<User & { emailed: boolean; email_error: string | null }>("/api/users", {
        email: email.trim(),
        display_name: name.trim(),
        role,
        password,
        send_email: mailReady && sendEmail,
      }),
    onSuccess: (u) => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      setCreated({ email: u.email, password, emailed: u.emailed, error: u.email_error });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const close = () => {
    onOpenChange(false);
    setTimeout(() => {
      setCreated(null);
      setEmail("");
      setName("");
      setRole("user");
      setPassword(randomPassword());
    }, 200);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(o) : close())}>
      <DialogContent
        title={created ? (created.emailed ? "Invitation sent" : "Account created") : "Invite a member"}
        description={
          created
            ? created.emailed
              ? `${created.email} received the sign-in details by email. Keep a copy in case it lands in spam.`
              : "Share these once. The password is not shown again."
            : "They must change the temporary password on first sign-in."
        }
      >
        {created ? (
          <div className="flex flex-col gap-3">
            {created.error ? <p className="rounded-[var(--radius-sm)] bg-warning-soft/50 px-3 py-2 text-[12.5px] text-warning">The account exists, but the email did not go out: {created.error} Share the details below instead.</p> : null}
            <div className="rounded-[var(--radius-sm)] border border-border bg-muted/50 p-3 font-mono text-[13px]">
              <div>
                <span className="text-subtle">email </span>
                {created.email}
              </div>
              <div>
                <span className="text-subtle">password </span>
                {created.password}
              </div>
            </div>
            <DialogFooter className="mt-2">
              <Button
                variant="secondary"
                onClick={() => {
                  void navigator.clipboard.writeText(`${created.email}\n${created.password}`);
                  toast.success("Copied");
                }}
              >
                Copy
              </Button>
              <Button onClick={close}>Done</Button>
            </DialogFooter>
          </div>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
            className="flex flex-col gap-4"
          >
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name">
                <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} required />
              </Field>
              <Field label="Role">
                <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">Member</SelectItem>
                    <SelectItem value="admin">Administrator</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>
            <Field label="Email">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Field>
            <Field label="Temporary password" hint="Generated for you. Edit if you prefer.">
              <Input value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} className="font-mono text-[12.5px]" required />
            </Field>
            {mailReady ? (
              <label className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-border px-3 py-2.5">
                <span>
                  <span className="block text-[13px] font-medium">Email the invitation</span>
                  <span className="block text-[12px] text-muted-foreground">Sign-in link and temporary password go to {email.trim() || "their address"}.</span>
                </span>
                <Switch checked={sendEmail} onCheckedChange={setSendEmail} />
              </label>
            ) : (
              <p className="text-[12px] text-muted-foreground">Email is not set up, so you will share the password yourself. An SMTP server can be added under Settings → Site.</p>
            )}
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" loading={create.isPending} disabled={!email.trim() || !name.trim() || password.length < 8}>
                {mailReady && sendEmail ? "Create and send" : "Create account"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

function UserRow({ u }: { u: User }) {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [resetPw, setResetPw] = useState<string | null>(null);
  const isMe = me?.id === u.id;

  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch<User>(`/api/users/${u.id}`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["users"] }),
    onError: (e: Error) => toast.error(e.message),
  });
  const del = useMutation({
    mutationFn: () => api.delete(`/api/users/${u.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("User deleted");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const mail = useQuery({ queryKey: ["admin-mail"], queryFn: () => api.get<{ enabled: boolean; host: string; from_addr: string }>("/api/admin/mail") });
  const mailReady = !!(mail.data?.enabled && mail.data.host && mail.data.from_addr);
  const doReset = () => {
    const pw = randomPassword();
    patch.mutate(
      { password: pw, send_email: mailReady },
      {
        onSuccess: (r) => {
          const res = r as User & { emailed?: boolean; email_error?: string | null };
          if (res.emailed) toast.success(`New temporary password emailed to ${u.email}`);
          else {
            if (res.email_error) toast.error(`Email failed: ${res.email_error}`);
            setResetPw(pw);
          }
        },
      },
    );
  };

  return (
    <Card className="flex items-center gap-4 p-4">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary">
        {initials(u.display_name)}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[14px] font-semibold">{u.display_name}</span>
          {u.role === "admin" ? (
            <Badge variant="primary" className="gap-1">
              <ShieldCheck className="h-3 w-3" /> Admin
            </Badge>
          ) : null}
          {!u.is_active ? <Badge variant="destructive">Deactivated</Badge> : null}
          {u.must_change_password ? <Badge variant="warning">Temporary password</Badge> : null}
          {isMe ? <Badge variant="outline">You</Badge> : null}
        </div>
        <div className="text-[12.5px] text-muted-foreground">
          {u.email} · joined {timeAgo(u.created_at)}
        </div>
        {resetPw ? (
          <div className="mt-2 inline-flex items-center gap-2 rounded-md border border-border bg-muted/50 px-2 py-1 font-mono text-[12.5px]">
            new password: {resetPw}
            <Button size="sm" variant="ghost" onClick={() => setResetPw(null)}>
              Hide
            </Button>
          </div>
        ) : null}
      </div>
      {!isMe ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" aria-label="More">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => patch.mutate({ role: u.role === "admin" ? "user" : "admin" })}>
              <ShieldCheck /> {u.role === "admin" ? "Make member" : "Make administrator"}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={doReset}>
              <KeyRound /> Reset password
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => patch.mutate({ is_active: !u.is_active })}>
              {u.is_active ? <UserX /> : <UserRound />} {u.is_active ? "Deactivate" : "Reactivate"}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => setConfirmDelete(true)}>
              <Trash2 /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete ${u.display_name}?`}
        description="Their projects and author profiles are deleted with them. Deactivate instead if you want to keep the work."
        onConfirm={() => del.mutate()}
        busy={del.isPending}
      />
    </Card>
  );
}

export function UsersPage() {
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/api/users") });
  const [add, setAdd] = useState(false);
  return (
    <div>
      <SectionTitle
        right={
          <Button size="sm" onClick={() => setAdd(true)}>
            <Plus className="h-3.5 w-3.5" /> Invite member
          </Button>
        }
      >
        Members
      </SectionTitle>
      {users.isLoading ? (
        <Skeleton className="h-20" />
      ) : (
        <div className="flex flex-col gap-3">
          {(users.data ?? []).map((u) => (
            <UserRow key={u.id} u={u} />
          ))}
        </div>
      )}
      <NewUserDialog open={add} onOpenChange={setAdd} />
    </div>
  );
}

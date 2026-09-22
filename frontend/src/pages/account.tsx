import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, Moon, Sun, Laptop } from "lucide-react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

export function AccountPage() {
  const { user, refresh } = useAuth();
  const { theme, setTheme } = useTheme();
  const [name, setName] = useState(user?.display_name ?? "");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");

  const saveName = useMutation({
    mutationFn: () => api.patch<User>("/api/auth/me", { display_name: name.trim() }),
    onSuccess: async () => {
      await refresh();
      toast.success("Name updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const changePw = useMutation({
    mutationFn: () => api.post<User>("/api/auth/change-password", { current_password: current, new_password: next }),
    onSuccess: async () => {
      await refresh();
      setCurrent("");
      setNext("");
      setAgain("");
      toast.success("Password changed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const mismatch = again.length > 0 && next !== again;

  return (
    <div className="animate-in max-w-2xl">
      <PageHeader title="Account" description="Your name, password and appearance." />

      {user?.must_change_password ? (
        <div className="mb-6 flex items-start gap-3 rounded-[var(--radius)] border border-warning/40 bg-warning-soft p-4">
          <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <div className="text-[13px] leading-snug">
            <div className="font-semibold">Set a password of your own</div>
            <div className="text-muted-foreground">You are signed in with a temporary password. Change it below before doing anything else.</div>
          </div>
        </div>
      ) : null}

      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>{user?.email}</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                saveName.mutate();
              }}
              className="flex items-end gap-3"
            >
              <Field label="Display name" className="flex-1">
                <Input value={name} onChange={(e) => setName(e.target.value)} required />
              </Field>
              <Button type="submit" variant="secondary" loading={saveName.isPending} disabled={name.trim() === user?.display_name}>
                Save
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Password</CardTitle>
            <CardDescription>At least 8 characters. Sessions on other devices stay signed in.</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!mismatch) changePw.mutate();
              }}
              className="flex flex-col gap-4"
            >
              <Field label="Current password">
                <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="New password">
                  <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} required />
                </Field>
                <Field label="Repeat new password" error={mismatch ? "Passwords do not match" : null}>
                  <Input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required />
                </Field>
              </div>
              <div>
                <Button type="submit" loading={changePw.isPending} disabled={mismatch || next.length < 8 || !current}>
                  Change password
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>Stored in this browser only.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2">
              {(
                [
                  ["light", "Light", Sun],
                  ["dark", "Dark", Moon],
                  ["system", "System", Laptop],
                ] as const
              ).map(([key, label, Icon]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setTheme(key)}
                  className={cn(
                    "flex flex-col items-center gap-2 rounded-[var(--radius-sm)] border p-3 text-[13px] font-medium transition-colors hover:bg-muted",
                    theme === key ? "border-primary bg-primary-soft text-primary" : "border-border",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

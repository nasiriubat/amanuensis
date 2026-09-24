import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { SiteLogo, useDocumentMeta } from "@/lib/site";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const site = useDocumentMeta("Sign in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  const sendReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/forgot", { email });
      setForgotSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the email");
    } finally {
      setBusy(false);
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email, password);
      navigate(u.must_change_password ? "/account" : "/library", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-[380px] animate-in">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-4">
            <SiteLogo className="h-12 w-12" iconClassName="h-6 w-6" />
          </span>
          <h1 className="text-[22px] font-semibold tracking-tight">{site.name}</h1>
          <p className="mt-1 text-[13.5px] text-muted-foreground">{site.tagline || "Sign in to your workspace"}</p>
        </div>
        {forgot ? (
          <form onSubmit={sendReset} className="card-surface p-6 shadow-[0_8px_32px_-12px_rgba(16,24,40,0.12)]">
            {forgotSent ? (
              <div className="flex flex-col gap-3 text-[13.5px]">
                <p>If an account exists for that address, a link is on its way. It works for one hour.</p>
                <p className="text-muted-foreground">Nothing arrived? Check spam, or ask an administrator to reset it for you.</p>
                <Button type="button" variant="secondary" onClick={() => setForgot(false)} className="mt-1 w-full">
                  Back to sign in
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <p className="text-[13.5px] text-muted-foreground">Enter your email and we send a link to choose a new password.</p>
                <Field label="Email" error={error}>
                  <Input type="email" autoComplete="username" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} required />
                </Field>
                <Button type="submit" size="lg" loading={busy} className="mt-1 w-full">
                  Send the link
                </Button>
                <button type="button" onClick={() => setForgot(false)} className="text-[12.5px] text-muted-foreground hover:text-foreground">
                  Back to sign in
                </button>
              </div>
            )}
          </form>
        ) : (
          <form onSubmit={submit} className="card-surface p-6 shadow-[0_8px_32px_-12px_rgba(16,24,40,0.12)]">
            <div className="flex flex-col gap-4">
              <Field label="Email">
                <Input type="email" autoComplete="username" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} required />
              </Field>
              <Field label="Password" error={error}>
                <Input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </Field>
              <Button type="submit" size="lg" loading={busy} className="mt-1 w-full">
                Sign in
              </Button>
              {site.password_reset ? (
                <button type="button" onClick={() => setForgot(true)} className="text-center text-[12.5px] text-muted-foreground hover:text-foreground">
                  Forgot your password?
                </button>
              ) : null}
            </div>
          </form>
        )}
        <p className="mt-6 text-center text-[12px] text-subtle">Accounts are created by an administrator.</p>
      </div>
    </div>
  );
}

import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { SiteLogo, useDocumentMeta } from "@/lib/site";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";

/** Landing page of the link in a "Forgot password" email. */
export function ResetPasswordPage() {
  const site = useDocumentMeta("Choose a new password");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pw !== pw2) {
      setError("The two passwords differ");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/auth/reset", { token, new_password: pw });
      toast.success("Password changed. Sign in with it now.");
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the password");
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
          <p className="mt-1 text-[13.5px] text-muted-foreground">Choose a new password</p>
        </div>
        {token ? (
          <form onSubmit={submit} className="card-surface p-6 shadow-[0_8px_32px_-12px_rgba(16,24,40,0.12)]">
            <div className="flex flex-col gap-4">
              <Field label="New password" hint="At least 8 characters.">
                <Input type="password" autoComplete="new-password" autoFocus minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} required />
              </Field>
              <Field label="Repeat it" error={error}>
                <Input type="password" autoComplete="new-password" minLength={8} value={pw2} onChange={(e) => setPw2(e.target.value)} required />
              </Field>
              <Button type="submit" size="lg" loading={busy} className="mt-1 w-full" disabled={pw.length < 8}>
                Change password
              </Button>
            </div>
          </form>
        ) : (
          <div className="card-surface p-6 text-center text-[13.5px] text-muted-foreground">
            This link is incomplete. Open the one from the email, or ask for a new one from the sign-in page.
          </div>
        )}
        <p className="mt-6 text-center text-[12px] text-subtle">
          <Link to="/login" className="text-primary hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

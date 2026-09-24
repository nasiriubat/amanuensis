import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ExternalLink, Eye, EyeOff, FileText, Plus, Trash2, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { SiteLogo, type LandingContent } from "@/lib/site";
import { cn, timeAgo } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { EmptyState, SectionTitle, Skeleton } from "@/components/ui/misc";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { MarkdownEditor } from "@/components/markdown-editor";
import { ConfirmDialog } from "@/components/dialogs";

interface SiteAdmin {
  name: string;
  tagline: string;
  footer: string;
  seo: { title: string; description: string; keywords: string; og_image: string; index: boolean };
  homepage: string;
  logo: string | null;
  landing: LandingContent;
}

const lines = (s: string) =>
  s
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
const principlesFromText = (s: string) =>
  lines(s).map((l) => {
    const [title, ...rest] = l.split("|");
    return { title: title.trim(), text: rest.join("|").trim() };
  });
const principlesToText = (p: LandingContent["principles"]) => p.map((x) => `${x.title} | ${x.text}`).join("\n");

interface PageRow {
  id: string;
  slug: string;
  title: string;
  published: boolean;
  show_in_nav: boolean;
  nav_order: number;
  updated_at: string;
  content?: string;
}

// ------------------------------------------------------------------ Site settings

export function SitePage() {
  const qc = useQueryClient();
  const site = useQuery({ queryKey: ["admin-site"], queryFn: () => api.get<SiteAdmin>("/api/admin/site") });
  const pages = useQuery({ queryKey: ["admin-pages"], queryFn: () => api.get<PageRow[]>("/api/admin/pages") });
  const [form, setForm] = useState<SiteAdmin | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (site.data && !form) setForm(site.data);
  }, [site.data, form]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["admin-site"] });
    void qc.invalidateQueries({ queryKey: ["site"] });
  };
  const save = useMutation({
    mutationFn: () => api.put<SiteAdmin>("/api/admin/site", form),
    onSuccess: (s) => {
      setForm(s);
      invalidate();
      toast.success("Site settings saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const upload = useMutation({
    mutationFn: (f: File) => api.upload<{ logo_url: string }>("/api/admin/site/logo", f),
    onSuccess: () => {
      invalidate();
      setForm(null);
      toast.success("Logo updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const removeLogo = useMutation({
    mutationFn: () => api.delete("/api/admin/site/logo"),
    onSuccess: () => {
      invalidate();
      setForm(null);
    },
  });

  if (!form) return <Skeleton className="h-96" />;
  const dirty = JSON.stringify(form) !== JSON.stringify(site.data);
  const set = (patch: Partial<SiteAdmin>) => setForm({ ...form, ...patch });
  const setSeo = (patch: Partial<SiteAdmin["seo"]>) => setForm({ ...form, seo: { ...form.seo, ...patch } });
  const setLanding = (patch: Partial<LandingContent>) => setForm({ ...form, landing: { ...form.landing, ...patch } });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
      className="flex flex-col gap-5"
    >
      <Card>
        <CardHeader>
          <CardTitle>Identity</CardTitle>
          <CardDescription>Name and logo appear in the sidebar, the sign-in page, public pages and the browser tab.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-4">
            <SiteLogo className="h-14 w-14" iconClassName="h-7 w-7" />
            <div className="flex flex-col gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/svg+xml,image/webp"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) upload.mutate(f);
                  e.target.value = "";
                }}
              />
              <div className="flex gap-2">
                <Button type="button" variant="secondary" size="sm" onClick={() => fileRef.current?.click()} loading={upload.isPending}>
                  <Upload className="h-3.5 w-3.5" /> Upload logo
                </Button>
                {form.logo ? (
                  <Button type="button" variant="ghost" size="sm" onClick={() => removeLogo.mutate()}>
                    <Trash2 className="h-3.5 w-3.5" /> Remove
                  </Button>
                ) : null}
              </div>
              <span className="text-[12px] text-muted-foreground">PNG, JPEG, SVG or WebP up to 2 MB. Square works best.</span>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Site name">
              <Input value={form.name} onChange={(e) => set({ name: e.target.value })} required />
            </Field>
            <Field label="Tagline" hint="Shown under the name on the sign-in page and in the browser title.">
              <Input value={form.tagline} onChange={(e) => set({ tagline: e.target.value })} />
            </Field>
          </div>
          <Field label="Footer text" hint="Public pages only. Leave empty to show the site name.">
            <Input value={form.footer} onChange={(e) => set({ footer: e.target.value })} />
          </Field>
          <Field label="Homepage for visitors" hint="What someone who is not signed in sees at the root address.">
            <Select value={form.homepage} onValueChange={(v) => set({ homepage: v })}>
              <SelectTrigger className="sm:w-80">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="landing">The landing page (below)</SelectItem>
                <SelectItem value="login">The sign-in page</SelectItem>
                {(pages.data ?? [])
                  .filter((p) => p.published)
                  .map((p) => (
                    <SelectItem key={p.id} value={p.slug}>
                      Page: {p.title}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Landing page</CardTitle>
          <CardDescription>
            The public front page at <a href="/landing" target="_blank" rel="noreferrer" className="text-primary underline-offset-2 hover:underline">/landing</a>. The eleven steps and the five entry points come from the product itself and stay in sync; the words here are yours.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Eyebrow" hint="Small line above the headline.">
              <Input value={form.landing.eyebrow} onChange={(e) => setLanding({ eyebrow: e.target.value })} maxLength={120} />
            </Field>
            <Field label="Headline">
              <Input value={form.landing.headline} onChange={(e) => setLanding({ headline: e.target.value })} maxLength={120} required />
            </Field>
          </div>
          <Field label="Subheadline">
            <Textarea value={form.landing.subheadline} onChange={(e) => setLanding({ subheadline: e.target.value })} maxLength={600} className="min-h-[72px]" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Primary button" hint="Leads to sign-in.">
              <Input value={form.landing.cta_primary} onChange={(e) => setLanding({ cta_primary: e.target.value })} maxLength={40} required />
            </Field>
            <Field label="Secondary button" hint="Scrolls to the steps. Leave empty to hide.">
              <Input value={form.landing.cta_secondary} onChange={(e) => setLanding({ cta_secondary: e.target.value })} maxLength={40} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="What a chat window gets wrong" hint="One point per line, up to eight.">
              <Textarea value={form.landing.why_chat.join("\n")} onChange={(e) => setLanding({ why_chat: lines(e.target.value).slice(0, 8) })} className="min-h-[140px]" />
            </Field>
            <Field label={`What ${form.name} does instead`} hint="One point per line, up to eight.">
              <Textarea value={form.landing.why_us.join("\n")} onChange={(e) => setLanding({ why_us: lines(e.target.value).slice(0, 8) })} className="min-h-[140px]" />
            </Field>
          </div>
          <Field label="Principles" hint="One per line as “Title | explanation”, up to eight.">
            <Textarea value={principlesToText(form.landing.principles)} onChange={(e) => setLanding({ principles: principlesFromText(e.target.value).slice(0, 8) })} className="min-h-[150px] font-mono text-[12.5px]" />
          </Field>
          <Field label="Closing line" hint="Under the tagline at the bottom of the page.">
            <Input value={form.landing.closing} onChange={(e) => setLanding({ closing: e.target.value })} maxLength={300} />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Search engines</CardTitle>
          <CardDescription>
            Rendered into the page head on the server, so link previews and crawlers see them without running scripts. A sitemap is served at /sitemap.xml. The workspace itself is never indexed.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-border px-3 py-2.5">
            <span>
              <span className="block text-[13px] font-medium">Allow indexing of public pages</span>
              <span className="block text-[12px] text-muted-foreground">Off writes a robots.txt that blocks everything.</span>
            </span>
            <Switch checked={form.seo.index} onCheckedChange={(v) => setSeo({ index: v })} />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Meta title" hint="Defaults to the site name.">
              <Input value={form.seo.title} onChange={(e) => setSeo({ title: e.target.value })} />
            </Field>
            <Field label="Keywords" hint="Comma separated.">
              <Input value={form.seo.keywords} onChange={(e) => setSeo({ keywords: e.target.value })} />
            </Field>
          </div>
          <Field label="Meta description">
            <Textarea value={form.seo.description} onChange={(e) => setSeo({ description: e.target.value })} className="min-h-[72px]" />
          </Field>
          <Field label="Social preview image URL" hint="Used as og:image when links are shared.">
            <Input value={form.seo.og_image} onChange={(e) => setSeo({ og_image: e.target.value })} className="font-mono text-[12.5px]" />
          </Field>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={save.isPending} disabled={!dirty}>
          Save settings
        </Button>
        {dirty ? <span className="text-[12.5px] text-warning">Unsaved changes</span> : null}
      </div>
    </form>
  );
}

export function SiteTab() {
  return (
    <div className="flex flex-col gap-5">
      <SitePage />
      <MailCard />
    </div>
  );
}

// ------------------------------------------------------------------ Email

interface MailAdmin {
  enabled: boolean;
  host: string;
  port: number;
  security: "starttls" | "ssl" | "none";
  username: string;
  from_addr: string;
  from_name: string;
  has_password: boolean;
  password_hint: string | null;
}

function MailCard() {
  const qc = useQueryClient();
  const mail = useQuery({ queryKey: ["admin-mail"], queryFn: () => api.get<MailAdmin>("/api/admin/mail") });
  const [form, setForm] = useState<MailAdmin | null>(null);
  const [password, setPassword] = useState("");
  useEffect(() => {
    if (mail.data && !form) setForm(mail.data);
  }, [mail.data, form]);
  const save = useMutation({
    mutationFn: () => api.put<MailAdmin>("/api/admin/mail", { ...form, password: password || null }),
    onSuccess: (m) => {
      setForm(m);
      setPassword("");
      void qc.invalidateQueries({ queryKey: ["admin-mail"] });
      void qc.invalidateQueries({ queryKey: ["site"] });
      toast.success(m.enabled ? "Email settings saved. Send a test to be sure." : "Email switched off");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const test = useMutation({
    mutationFn: () => api.post<{ sent_to: string }>("/api/admin/mail/test"),
    onSuccess: (r) => toast.success(`Test message sent to ${r.sent_to}`),
    onError: (e: Error) => toast.error(e.message),
  });
  if (!form) return <Skeleton className="h-64" />;
  const set = (patch: Partial<MailAdmin>) => setForm({ ...form, ...patch });
  const dirty = JSON.stringify(form) !== JSON.stringify(mail.data) || password !== "";
  const ready = form.enabled && form.host.trim() && form.from_addr.trim();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <Card>
        <CardHeader>
          <CardTitle>Email</CardTitle>
          <CardDescription>
            With an SMTP server, invitations carry the sign-in details and members can reset a forgotten password themselves. Without one, you share temporary passwords by hand. The password is stored encrypted.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <label className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-border px-3 py-2.5">
            <span>
              <span className="block text-[13px] font-medium">Send email</span>
              <span className="block text-[12px] text-muted-foreground">Off keeps every setting but sends nothing.</span>
            </span>
            <Switch checked={form.enabled} onCheckedChange={(v) => set({ enabled: v })} />
          </label>
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_120px_160px]">
            <Field label="SMTP host">
              <Input value={form.host} onChange={(e) => set({ host: e.target.value })} placeholder="smtp.example.org" className="font-mono text-[12.5px]" />
            </Field>
            <Field label="Port">
              <Input type="number" min={1} max={65535} value={form.port} onChange={(e) => set({ port: Number(e.target.value) || 587 })} className="font-mono text-[12.5px]" />
            </Field>
            <Field label="Security">
              <Select value={form.security} onValueChange={(v) => set({ security: v as MailAdmin["security"] })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="starttls">STARTTLS (587)</SelectItem>
                  <SelectItem value="ssl">SSL/TLS (465)</SelectItem>
                  <SelectItem value="none">None (local relay)</SelectItem>
                </SelectContent>
              </Select>
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Username" hint="Leave empty for a relay that needs no login.">
              <Input value={form.username} onChange={(e) => set({ username: e.target.value })} autoComplete="off" className="font-mono text-[12.5px]" />
            </Field>
            <Field label="Password" hint={form.has_password ? `Stored, ends in ${form.password_hint}. Type to replace.` : "Stored encrypted."}>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" placeholder={form.has_password ? "••••••••" : ""} className="font-mono text-[12.5px]" />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Sender address" hint="Many providers require this to match the account.">
              <Input type="email" value={form.from_addr} onChange={(e) => set({ from_addr: e.target.value })} placeholder="paper-writer@example.org" className="font-mono text-[12.5px]" />
            </Field>
            <Field label="Sender name">
              <Input value={form.from_name} onChange={(e) => set({ from_name: e.target.value })} placeholder="Paper Writer" />
            </Field>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" loading={save.isPending} disabled={!dirty}>
              Save email settings
            </Button>
            <Button type="button" variant="secondary" onClick={() => test.mutate()} loading={test.isPending} disabled={dirty || !ready} title={dirty ? "Save first" : !ready ? "Switch email on and fill host and sender" : "Sends a message to your own address"}>
              Send a test to me
            </Button>
            {dirty ? <span className="text-[12.5px] text-warning">Unsaved changes</span> : null}
          </div>
        </CardContent>
      </Card>
    </form>
  );
}

// ------------------------------------------------------------------ Pages

function PageEditor({ page, onClose }: { page: PageRow; onClose: () => void }) {
  const qc = useQueryClient();
  const full = useQuery({ queryKey: ["admin-page", page.id], queryFn: () => api.get<PageRow>(`/api/admin/pages/${page.id}`) });
  const [title, setTitle] = useState(page.title);
  const [slug, setSlug] = useState(page.slug);
  const patch = useMutation({
    mutationFn: (body: Partial<PageRow>) => api.patch<PageRow>(`/api/admin/pages/${page.id}`, body),
    onSuccess: (p) => {
      qc.setQueryData(["admin-page", page.id], p);
      void qc.invalidateQueries({ queryKey: ["admin-pages"] });
      void qc.invalidateQueries({ queryKey: ["site"] });
      setSlug(p.slug);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const meta = full.data ?? page;
  return (
    <Card className="p-5">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Title" className="min-w-[200px] flex-1">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => title !== meta.title && patch.mutate({ title })} />
        </Field>
        <Field label="Address" hint={`/p/${slug}`} className="min-w-[160px]">
          <Input value={slug} onChange={(e) => setSlug(e.target.value)} onBlur={() => slug !== meta.slug && patch.mutate({ slug })} className="font-mono text-[12.5px]" />
        </Field>
        <label className="flex items-center gap-2 pb-1 text-[13px]">
          <Switch checked={meta.published} onCheckedChange={(v) => patch.mutate({ published: v })} /> Published
        </label>
        <label className="flex items-center gap-2 pb-1 text-[13px]">
          <Switch checked={meta.show_in_nav} onCheckedChange={(v) => patch.mutate({ show_in_nav: v })} /> In navigation
        </label>
        {meta.published ? (
          <a href={`/p/${meta.slug}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 pb-2 text-[13px] text-primary hover:underline">
            View <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : null}
        <Button type="button" variant="ghost" size="sm" onClick={onClose} className="ml-auto">
          Done
        </Button>
      </div>
      {full.data ? (
        <MarkdownEditor
          value={full.data.content ?? ""}
          onSave={async (content) => {
            await patch.mutateAsync({ content });
          }}
          minHeight={420}
          placeholder={"# About\n\nWrite in Markdown. Headings, lists, links, images and tables all work."}
          emptyHint="Switch to Edit and write the page."
        />
      ) : (
        <Skeleton className="h-[420px]" />
      )}
    </Card>
  );
}

export function PagesPage() {
  const qc = useQueryClient();
  const pages = useQuery({ queryKey: ["admin-pages"], queryFn: () => api.get<PageRow[]>("/api/admin/pages") });
  const [editing, setEditing] = useState<PageRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [del, setDel] = useState<PageRow | null>(null);

  const create = useMutation({
    mutationFn: () => api.post<PageRow>("/api/admin/pages", { title: newTitle.trim() }),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["admin-pages"] });
      setCreating(false);
      setNewTitle("");
      setEditing(p);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/api/admin/pages/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["admin-pages"] });
      void qc.invalidateQueries({ queryKey: ["site"] });
      setDel(null);
      if (editing && del && editing.id === del.id) setEditing(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div>
      <SectionTitle
        right={
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="h-3.5 w-3.5" /> New page
          </Button>
        }
      >
        Public pages
      </SectionTitle>
      <p className="mb-4 -mt-1 text-[13px] text-muted-foreground">
        About, contact, a landing page, terms. Published pages live at /p/slug and can appear in the public navigation. One of them can be the homepage for visitors (Site tab).
      </p>
      {editing ? (
        <div className="mb-5">
          <PageEditor key={editing.id} page={editing} onClose={() => setEditing(null)} />
        </div>
      ) : null}
      {pages.isLoading ? (
        <Skeleton className="h-24" />
      ) : (pages.data ?? []).length === 0 ? (
        <EmptyState icon={<FileText />} title="No pages yet" description="Create an About or Contact page. It is Markdown, with a preview." action={<Button onClick={() => setCreating(true)}>New page</Button>} />
      ) : (
        <Card className="divide-y divide-border">
          {(pages.data ?? []).map((p) => (
            <div key={p.id} className={cn("flex items-center gap-3 px-4 py-3", editing?.id === p.id && "bg-primary-soft/30")}>
              {p.published ? <Eye className="h-4 w-4 text-success" /> : <EyeOff className="h-4 w-4 text-subtle" />}
              <button onClick={() => setEditing(p)} className="min-w-0 flex-1 text-left">
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-medium">{p.title}</span>
                  {p.show_in_nav ? <Badge variant="outline">In nav</Badge> : null}
                  {!p.published ? <Badge>Draft</Badge> : null}
                </div>
                <div className="font-mono text-[11.5px] text-subtle">/p/{p.slug} · updated {timeAgo(p.updated_at)}</div>
              </button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(p)}>
                Edit
              </Button>
              <button onClick={() => setDel(p)} className="rounded p-1.5 text-subtle hover:bg-destructive-soft hover:text-destructive" aria-label="Delete">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </Card>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent title="New page" description="You can change the title and address afterwards.">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <Field label="Title">
              <Input autoFocus value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="About" required />
            </Field>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={create.isPending} disabled={!newTitle.trim()}>
                Create
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={!!del}
        onOpenChange={(o) => !o && setDel(null)}
        title={`Delete “${del?.title}”?`}
        description="The page and its address stop working immediately."
        onConfirm={() => del && remove.mutate(del.id)}
        busy={remove.isPending}
      />
    </div>
  );
}

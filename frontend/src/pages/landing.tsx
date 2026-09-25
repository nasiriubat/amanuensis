import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  Compass,
  FileText,
  Layers,
  Lightbulb,
  MessagesSquare,
  PenLine,
  Quote,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useSite } from "@/lib/site";
import { STEPS, type StepKey } from "@/lib/flow";
import { Button } from "@/components/ui/button";
import { PublicFrame } from "@/pages/public-page";

/** One sentence per step, keyed to the real flow so a new step cannot be forgotten here. */
const STEP_BLURB: Record<StepKey, string> = {
  spec: "Paste a spec, a README or a summary from your coding agent. Everything else reads it.",
  design: "Only have an idea? Refine it or explore the space and get a study plan you can edit.",
  sources: "Five to ten papers of this type from arXiv or PDF. Sections are detected and measured.",
  playbook: "How this genre argues, evaluates, positions itself and where it publishes.",
  interview: "Pointed questions with suggested answers, until the paper has what the venue expects.",
  outline: "Facts are separated into done and planned. You approve the outline before any drafting.",
  studio: "One section at a time, with live preview, house-style lint, versions and a checklist.",
  references: "Placeholders become searches. Candidates are verified against academic APIs before you cite.",
  figures: "Describe a diagram and get Mermaid, rendered in your browser. Upload result plots as they are.",
  review: "A reviewer pass over the whole draft: overclaims, missing evidence, contradictions.",
  export: "LNCS or ACM PDF, DOCX and a LaTeX archive, with gaps printed in red so nothing slips through.",
};

const STEP_ICON: Record<StepKey, React.ComponentType<{ className?: string }>> = {
  spec: FileText,
  design: Lightbulb,
  sources: Layers,
  playbook: BookOpenCheck,
  interview: MessagesSquare,
  outline: Layers,
  studio: PenLine,
  references: Quote,
  figures: Sparkles,
  review: ShieldCheck,
  export: ArrowRight,
};

const DOORS = [
  { icon: FileText, title: "I built something", text: "Start from the specification and let the interview fill the gaps a reviewer would find.", joins: "Describe what you built" },
  { icon: Lightbulb, title: "I only have an idea", text: "Research design turns a vague idea into a study plan, then the same pipeline carries it to a paper.", joins: "Research design" },
  { icon: Users, title: "I want it to read like a specific author", text: "An author profile is learned once from their papers and reused by anyone on the team.", joins: "Author profiles" },
  { icon: PenLine, title: "I have a half-written draft", text: "Paste sections as your own. They are protected, linted and exported like everything else.", joins: "Studio" },
  { icon: Compass, title: "I want a pre-submission review", text: "Run the reviewer pass and the venue check on what you already have.", joins: "Review" },
];

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-0.5 border-l-2 border-primary/40 pl-3">
      <span className="text-[24px] font-semibold tracking-tight tabular-nums">{value}</span>
      <span className="text-[12.5px] text-muted-foreground">{label}</span>
    </div>
  );
}

function FlowStrip() {
  const cols = [
    { label: "You bring", items: ["A working system or an idea", "Example papers from arXiv or PDF", "A colleague's papers for their voice", "Answers to interview questions"] },
    { label: "It builds", items: ["A pattern for the genre", "A voice profile with measured statistics", "Facts, outline and section drafts", "Verified reference records"] },
    { label: "You get", items: ["LNCS or ACM PDF", "DOCX and a LaTeX archive", "A reviewer verdict with fixes", "Three venue suggestions"] },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {cols.map((c, i) => (
        <div key={c.label} className="relative rounded-[var(--radius)] border border-border bg-card p-4 shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-subtle">{c.label}</span>
            {i < cols.length - 1 ? <ArrowRight className="hidden h-4 w-4 text-subtle sm:block" /> : null}
          </div>
          <ul className="flex flex-col gap-1.5 text-[13.5px]">
            {c.items.map((it) => (
              <li key={it} className="flex items-start gap-2">
                <Check className="mt-1 h-3.5 w-3.5 shrink-0 text-primary" /> {it}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function LandingPage() {
  const site = useSite();
  const { user } = useAuth();
  const L = site.landing;
  const to = user ? "/library" : "/login";
  const steps = STEPS.filter((s) => !s.soonPhase);

  return (
    <PublicFrame>
      <div className="mx-auto flex max-w-[1080px] flex-col gap-20 pb-10">
        {/* Hero */}
        <section className="grid items-center gap-10 pt-4 lg:grid-cols-[1.15fr_1fr]">
          <div className="animate-in">
            {L.eyebrow ? <div className="mb-3 text-[12px] font-medium uppercase tracking-[0.12em] text-primary">{L.eyebrow}</div> : null}
            <h1 className="text-balance text-[36px] font-semibold leading-[1.08] tracking-tight sm:text-[48px]">{L.headline}</h1>
            <p className="mt-5 max-w-[58ch] text-[16px] leading-relaxed text-muted-foreground sm:text-[17px]">{L.subheadline}</p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <Link to={to}>
                <Button size="lg">
                  {user ? "Open workspace" : L.cta_primary} <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              {L.cta_secondary ? (
                <a href="#how">
                  <Button size="lg" variant="secondary">
                    {L.cta_secondary}
                  </Button>
                </a>
              ) : null}
            </div>
            <div className="mt-9 grid grid-cols-2 gap-5 sm:grid-cols-4">
              <Stat value="11" label="guided steps, two optional" />
              <Stat value="6" label="paper types, plus your own" />
              <Stat value="5" label="model purposes, any provider" />
              <Stat value="3" label="export formats" />
            </div>
          </div>
          <div className="animate-in [animation-delay:80ms]">
            <FlowStrip />
          </div>
        </section>

        {/* Why */}
        {L.why_chat.length || L.why_us.length ? (
          <section>
            <div className="mb-7 max-w-[64ch]">
              <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.12em] text-primary">Why not a chat window</div>
              <h2 className="text-balance text-[26px] font-semibold leading-tight tracking-tight sm:text-[30px]">A chat forgets, invents, and writes like a chat</h2>
              <p className="mt-3 text-[15px] text-muted-foreground">Everything the model sees is a file you can open. Nothing it cannot back up is asserted. Whatever you edit is yours and stays yours.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[var(--radius)] border border-border bg-card p-6">
                <h3 className="text-[15px] font-semibold">Pasting into a general chatbot</h3>
                <ul className="mt-4 flex flex-col gap-2.5 text-[14px] text-muted-foreground">
                  {L.why_chat.map((t) => (
                    <li key={t} className="flex items-start gap-2.5">
                      <X className="mt-0.5 h-4 w-4 shrink-0 text-subtle" /> {t}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-[var(--radius)] border border-primary/30 bg-primary-soft/40 p-6">
                <h3 className="text-[15px] font-semibold">{site.name}</h3>
                <ul className="mt-4 flex flex-col gap-2.5 text-[14px]">
                  {L.why_us.map((t) => (
                    <li key={t} className="flex items-start gap-2.5">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" /> {t}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
        ) : null}

        {/* How it works */}
        <section id="how" className="scroll-mt-24">
          <div className="mb-7 max-w-[64ch]">
            <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.12em] text-primary">How it works</div>
            <h2 className="text-balance text-[26px] font-semibold leading-tight tracking-tight sm:text-[30px]">Eleven steps, each leaving a file behind</h2>
            <p className="mt-3 text-[15px] text-muted-foreground">One place decides what comes next, so you are never left guessing. Steps can be revisited, and nothing downstream is regenerated behind your back.</p>
          </div>
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {steps.map((s, i) => {
              const Icon = STEP_ICON[s.key];
              return (
                <li key={s.key} className="group relative flex gap-3.5 rounded-[var(--radius)] border border-border bg-card p-4 transition-[border-color,box-shadow] hover:border-border-strong hover:shadow-[0_4px_16px_-6px_rgba(16,24,40,0.12)]">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] text-subtle">{String(i + 1).padStart(2, "0")}</span>
                      <h3 className="text-[14.5px] font-semibold leading-tight">{s.title}</h3>
                      {s.optional ? <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">optional</span> : null}
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{STEP_BLURB[s.key]}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>

        {/* Doors */}
        <section>
          <div className="mb-7 max-w-[64ch]">
            <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.12em] text-primary">Ways in</div>
            <h2 className="text-balance text-[26px] font-semibold leading-tight tracking-tight sm:text-[30px]">Five doors into the same pipeline</h2>
            <p className="mt-3 text-[15px] text-muted-foreground">You do not have to start at step one. Each starting point joins the flow where it makes sense.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {DOORS.map((d) => (
              <div key={d.title} className="flex flex-col gap-2.5 rounded-[var(--radius)] border border-border bg-card p-4">
                <d.icon className="h-5 w-5 text-primary" />
                <h3 className="text-[14.5px] font-semibold leading-snug">{d.title}</h3>
                <p className="text-[13px] leading-relaxed text-muted-foreground">{d.text}</p>
                <div className="mt-auto pt-2 text-[11.5px] text-subtle">
                  Joins at <span className="font-medium text-muted-foreground">{d.joins}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Principles */}
        {L.principles.length ? (
          <section>
            <div className="mb-7 max-w-[64ch]">
              <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.12em] text-primary">Principles</div>
              <h2 className="text-balance text-[26px] font-semibold leading-tight tracking-tight sm:text-[30px]">Rules the code enforces, not just the prompts</h2>
            </div>
            <div className="grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
              {L.principles.map((p) => (
                <div key={p.title} className="border-t-2 border-primary pt-3">
                  <h3 className="text-[15px] font-semibold">{p.title}</h3>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground">{p.text}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {/* Closing */}
        <section className="rounded-[var(--radius-lg)] border border-border bg-card px-6 py-10 text-center sm:px-10">
          <h2 className="text-balance text-[24px] font-semibold tracking-tight">{site.tagline || site.name}</h2>
          {L.closing ? <p className="mx-auto mt-3 max-w-[52ch] text-[14.5px] text-muted-foreground">{L.closing}</p> : null}
          <div className="mt-6">
            <Link to={to}>
              <Button size="lg">
                {user ? "Open workspace" : L.cta_primary} <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </div>
        </section>
      </div>
    </PublicFrame>
  );
}

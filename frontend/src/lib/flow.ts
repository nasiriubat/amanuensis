import type { Project } from "./types";

/**
 * One place that decides what a project needs next. Every screen that shows guidance
 * reads from here, so the user is never told two different things.
 */

export type StepKey = "spec" | "design" | "sources" | "playbook" | "interview" | "outline" | "studio" | "references" | "figures" | "export";
export type StepState = "done" | "current" | "todo" | "locked" | "optional" | "soon";

export interface Step {
  key: StepKey;
  title: string;
  to: (slug: string) => string;
  optional?: boolean;
  soonPhase?: number;
  state: (p: Project) => StepState;
  summary: (p: Project) => string;
}

const approvedStages = ["outline", "drafting", "review", "export"];

export const STEPS: Step[] = [
  {
    key: "spec",
    title: "Describe what you built",
    to: (s) => `/projects/${s}/spec`,
    state: (p) => (p.counts.has_spec ? "done" : "current"),
    summary: (p) => (p.counts.has_spec ? "Specification saved." : "Paste or write the system specification. Everything else reads it."),
  },
  {
    key: "design",
    title: "Research design",
    to: (s) => `/projects/${s}/design`,
    optional: true,
    state: (p) => (p.counts.has_plan ? "done" : "optional"),
    summary: (p) => (p.counts.has_plan ? "Research plan written." : "Optional. Turn an idea into a study reviewers would accept."),
  },
  {
    key: "sources",
    title: "Add exemplar papers",
    to: (s) => `/projects/${s}/sources`,
    state: (p) => (p.counts.exemplars > 0 ? "done" : "todo"),
    summary: (p) => (p.counts.exemplars ? `${p.counts.exemplars} exemplar${p.counts.exemplars === 1 ? "" : "s"} ingested.` : "Five to ten papers of this kind, from arXiv or PDF."),
  },
  {
    key: "playbook",
    title: "Learn the playbook",
    to: (s) => `/projects/${s}/playbook`,
    state: (p) => (p.counts.playbook_files > 0 ? "done" : p.counts.exemplars > 0 ? "todo" : "locked"),
    summary: (p) => (p.counts.playbook_files ? `${p.counts.playbook_files} of 5 playbook files learned.` : p.counts.exemplars ? "Learn how these papers are built." : "Needs exemplars first."),
  },
  {
    key: "interview",
    title: "Interview",
    to: (s) => `/projects/${s}/interview`,
    state: (p) => (p.counts.interview_rounds.done || (p.counts.interview_rounds.rounds > 0 && p.counts.interview_rounds.open === 0) ? "done" : p.counts.has_spec ? "todo" : "locked"),
    summary: (p) => {
      const ir = p.counts.interview_rounds;
      if (ir.done) return `Complete: ${ir.answered} answers over ${ir.rounds} rounds.`;
      if (ir.rounds) return `${ir.answered} answered, ${ir.open} open, ${ir.rounds} round${ir.rounds === 1 ? "" : "s"}.`;
      return "The model asks only what the paper still lacks.";
    },
  },
  {
    key: "outline",
    title: "Outline",
    to: (s) => `/projects/${s}/outline`,
    state: (p) => (approvedStages.includes(p.stage) ? "done" : p.counts.has_spec ? "todo" : "locked"),
    summary: (p) => (approvedStages.includes(p.stage) ? "Approved." : p.counts.has_outline ? "Draft outline written. Approve it to unlock drafting." : "One line per paragraph. You approve it before drafting."),
  },
  {
    key: "studio",
    title: "Draft the paper",
    to: (s) => `/projects/${s}/studio`,
    state: (p) => (p.counts.sections > 0 && p.counts.sections_drafted === p.counts.sections ? "done" : approvedStages.includes(p.stage) ? "todo" : "locked"),
    summary: (p) =>
      p.counts.sections
        ? `${p.counts.sections_drafted} of ${p.counts.sections} sections drafted${p.counts.checklist_open ? `, ${p.counts.checklist_open} open item${p.counts.checklist_open === 1 ? "" : "s"}` : ""}.`
        : approvedStages.includes(p.stage)
          ? "Section by section, from the approved outline."
          : "Needs an approved outline.",
  },
  {
    key: "references",
    title: "References",
    to: (s) => `/projects/${s}/references`,
    state: (p) =>
      p.counts.references > 0 && p.counts.cite_requests === 0 ? "done" : p.counts.sections > 0 ? "todo" : p.counts.has_spec ? "optional" : "locked",
    summary: (p) =>
      p.counts.cite_requests
        ? `${p.counts.references} verified, ${p.counts.cite_requests} claim${p.counts.cite_requests === 1 ? "" : "s"} still need a source.`
        : p.counts.references
          ? `${p.counts.references} verified reference${p.counts.references === 1 ? "" : "s"}.`
          : "Search three indexes, import a .bib, or add by hand. Drafts cite only these.",
  },
  {
    key: "figures",
    title: "Figures",
    to: (s) => `/projects/${s}/figures`,
    optional: true,
    state: (p) => (p.counts.figures > 0 ? "done" : p.counts.has_spec ? "optional" : "locked"),
    summary: (p) => (p.counts.figures ? `${p.counts.figures} figure${p.counts.figures === 1 ? "" : "s"}.` : "Optional. Architecture diagrams from Mermaid; results and screenshots uploaded."),
  },
  {
    key: "export",
    title: "Export",
    to: (s) => `/projects/${s}/export`,
    state: (p) => (p.counts.exports > 0 ? "done" : p.counts.sections_drafted > 0 ? "todo" : "locked"),
    summary: (p) => (p.counts.exports ? `${p.counts.exports} export${p.counts.exports === 1 ? "" : "s"} so far.` : p.counts.sections_drafted ? "LNCS, ACM or your own template. PDF, LaTeX zip and DOCX." : "Needs at least one drafted section."),
  },
];

/** The single step the user should do next. */
export function nextStep(p: Project): Step | null {
  for (const s of STEPS) {
    const st = s.state(p);
    if (st === "current" || st === "todo") return s;
  }
  return null;
}

/** Steps for the stepper, with the "current" one resolved. */
export function stepStates(p: Project): Array<{ step: Step; state: StepState }> {
  const next = nextStep(p);
  return STEPS.map((step) => {
    let state = step.state(p);
    if (next && step.key === next.key) state = "current";
    return { step, state };
  });
}

/** What comes after a given step, for the footer bar on stage pages. */
export function stepAfter(p: Project, key: StepKey): Step | null {
  const idx = STEPS.findIndex((s) => s.key === key);
  const next = nextStep(p);
  if (next && next.key !== key) return next;
  for (const s of STEPS.slice(idx + 1)) {
    const st = s.state(p);
    if (st !== "soon" && st !== "done") return s;
  }
  return null;
}

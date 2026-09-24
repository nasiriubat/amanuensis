export type Role = "admin" | "user";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  must_change_password: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ModelInfo {
  id: string;
  name: string | null;
  context_window: number | null;
}

export type Adapter = "openai_compat" | "anthropic";

export interface Provider {
  id: string;
  name: string;
  adapter: Adapter;
  base_url: string | null;
  has_key: boolean;
  key_hint: string | null;
  enabled: boolean;
  models: ModelInfo[];
  models_fetched_at: string | null;
  models_error: string | null;
  created_at: string;
}

export interface ProviderPreset {
  name: string;
  adapter: Adapter;
  base_url: string | null;
}

export type Purpose = "learn" | "interview" | "draft" | "critique" | "utility";

export interface PurposeAssignment {
  purpose: Purpose;
  description: string;
  provider_id: string | null;
  provider_name: string | null;
  model: string | null;
}

export interface LlmTestResult {
  ok: boolean;
  provider: string;
  model: string;
  text: string;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
}

export interface Profile {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  owner_id: string;
  owner_name: string;
  shareable: boolean;
  status: "empty" | "learning" | "ready";
  source_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCounts {
  exemplars: number;
  sections: number;
  references: number;
  figures: number;
  playbook_files: number;
  has_spec: boolean;
  has_plan: boolean;
  has_outline: boolean;
  sections_drafted: number;
  checklist_open: number;
  cite_requests: number;
  exports: number;
  reviewed: boolean;
  interview_rounds: { rounds: number; answered: number; open: number; done: boolean };
}

export type ProjectEntry = "built" | "idea" | "draft";

export interface Project {
  id: string;
  slug: string;
  title: string;
  owner_id: string;
  owner_name: string;
  kind: string;
  kind_name: string;
  entry: ProjectEntry;
  profile_id: string | null;
  profile_name: string | null;
  venue: string | null;
  stage: string;
  model_overrides: Record<string, unknown> | null;
  counts: ProjectCounts;
  created_at: string;
  updated_at: string;
}

export interface KindSummary {
  slug: string;
  name: string;
  summary: string;
  builtin: boolean;
}

export interface Kind extends KindSummary {
  files: Record<string, string>;
}

export interface UsageRow {
  key: string;
  label: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  errors: number;
}

export interface UsageSummary {
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  by_provider: UsageRow[];
  by_purpose: UsageRow[];
  by_project: UsageRow[];
  recent: Array<{
    id: string;
    purpose: string;
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cached_tokens: number;
    duration_ms: number;
    ok: boolean;
    error: string | null;
    created_at: string;
  }>;
}

export interface HistoryEntry {
  sha: string;
  timestamp: number;
  message: string;
}

export interface Paper {
  id: string;
  title: string;
  authors?: string[];
  year?: number | null;
  arxiv_id?: string;
  url?: string;
  source?: string;
  extraction?: string;
  word_count?: number;
  figures?: Array<{ kind?: string; index: number; caption: string }>;
  figure_files?: string[];
  status: "pending" | "ready" | "failed";
  error?: string;
  abstract?: string;
}

export interface PaperDetail {
  meta: Paper & { sections?: Array<{ level: number; title: string; words: number }> };
  markdown: string;
  summary: string | null;
}

export interface JobInfo {
  id: string;
  type: string;
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  project_id: string | null;
  profile_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterviewQuestion {
  id: string;
  question: string;
  why: string;
  suggested: string;
  confidence: "low" | "medium" | "high";
  answer: string;
  status: "open" | "answered" | "na";
}

export interface InterviewRound {
  index: number;
  title: string;
  rationale: string;
  questions: InterviewQuestion[];
  created_at?: string;
}

export interface InterviewState {
  rounds: InterviewRound[];
  notes: Array<{ id: string; text: string; at: string; unverified?: boolean }>;
  done?: boolean;
  updated_at: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  pin?: string | null;
  at: string;
}

export interface LintFinding {
  line: number;
  kind: string;
  severity: "error" | "warning" | "info";
  message: string;
  excerpt: string;
}

export interface Section {
  id: string;
  slug: string;
  file: string;
  order: number;
  title: string;
  target_words: number;
  lines: string[];
  status: "empty" | "drafted" | "edited" | "mine";
  words?: number;
  open_items?: number;
  lint?: { errors: number; warnings: number; info: number };
  updated_at?: string;
}

export interface StudioState {
  initialized: boolean;
  sections: Section[];
  /** Sections the paper kind expects that this project does not have yet. */
  missing: string[];
}

export interface SectionDetail {
  section: Section;
  content: string;
  lint: LintFinding[];
}

export interface FixProposal {
  text: string;
  changed: boolean;
  mechanical: string;
  model_used: boolean;
  before: { errors: number; warnings: number; info: number };
  before_count: number;
  after: LintFinding[];
  note: string;
  tokens_in: number;
  tokens_out: number;
}

export interface ChecklistItem {
  id: string;
  section: string;
  text: string;
  source: "outline" | "kind" | "draft" | "citation" | "user";
  status: "open" | "resolved" | "limitation";
  created_at: string;
}

export interface RefCandidate {
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  arxiv_id: string | null;
  abstract: string | null;
  citation_count: number | null;
  source: string;
  sources: string[];
  bibtype: string;
  score: number;
}

export interface RefRecord {
  key: string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  arxiv_id: string | null;
  abstract: string | null;
  source: string;
  verified_at: string;
  added_at: string;
  uses: number;
}

export interface RefRequest {
  section: string;
  section_id: string;
  text: string;
  query: string;
}

export interface Figure {
  name: string;
  kind: "mermaid" | "image";
  caption: string;
  file: string | null;
  source_file: string | null;
  png_file: string | null;
  source?: string;
  created_at: string;
  updated_at?: string;
}

export interface TemplateInfo {
  slug: string;
  name: string;
  description: string;
  class: string;
  bib_style: string;
  required_files: string[];
  missing_files: string[];
  ready: boolean;
  files: string[];
  page_limit_hint?: string;
  notes?: string;
  download_url?: string;
  custom?: boolean;
}

export interface PaperMeta {
  authors: Array<{ name: string; affiliation: string; email: string; country: string; orcid: string }>;
  keywords: string[];
  subtitle: string;
}

export interface ExportResult {
  stamp: string;
  template: string;
  files: string[];
  warnings: string[];
  compile_error?: string;
  tools: { pandoc: boolean; tectonic: boolean };
}

export interface ReviewFinding {
  id: string;
  section: string;
  severity: "major" | "minor";
  kind: string;
  quote: string;
  issue: string;
  fix: string;
}

export interface ReviewState {
  verdict: string;
  summary: string;
  strengths: string[];
  findings: ReviewFinding[];
  cross_section: string[];
  page_budget: string;
  words: number;
  drafted_sections: number;
  total_sections: number;
  created_at: string;
}

export interface VenueSuggestions {
  suggestions: Array<{ venue: string; track: string; fit: "high" | "medium"; why: string; typical_length: string; template: string; risk: string; ai_policy_note: string }>;
  recommendation: string;
  before_submitting: string[];
  created_at: string;
}

export interface ScanCandidate {
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  arxiv_id: string | null;
  pdf_url: string | null;
  abstract: string | null;
  citation_count: number | null;
  sources: string[];
  queries: number[];
  relevance: 0 | 1 | 2 | 3;
  why: string;
  already_reference: boolean;
  already_exemplar: boolean;
  adopted_reference: string | null;
  adopted_exemplar: boolean;
}

export interface ScanState {
  queries: string[];
  themes: string[];
  candidates: ScanCandidate[];
  skipped_known: number;
  errors: string[];
  created_at: string;
  tokens_in: number;
  tokens_out: number;
}

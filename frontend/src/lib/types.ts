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
  interview_rounds: { rounds: number; answered: number; open: number; done: boolean };
}

export interface Project {
  id: string;
  slug: string;
  title: string;
  owner_id: string;
  owner_name: string;
  kind: string;
  kind_name: string;
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
  notes: Array<{ id: string; text: string; at: string }>;
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
}

export interface SectionDetail {
  section: Section;
  content: string;
  lint: LintFinding[];
}

export interface ChecklistItem {
  id: string;
  section: string;
  text: string;
  source: "outline" | "kind" | "draft" | "citation" | "user";
  status: "open" | "resolved" | "limitation";
  created_at: string;
}

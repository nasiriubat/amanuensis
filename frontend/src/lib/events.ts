import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { api } from "./api";
import { useSite } from "./site";

/**
 * Opt-in usage events for the user study. Nothing is sent unless an admin switched the
 * study on (the public site payload says so), and no text is ever included: kinds, paths,
 * counts and short labels only. Fire-and-forget; a failure never reaches the user.
 */
export type EventKind =
  | "page"
  | "section_saved"
  | "section_drafted"
  | "fix_accepted"
  | "fix_discarded"
  | "section_added"
  | "export_downloaded"
  | "critique_run"
  | "scan_run"
  | "reference_added";

let enabled = false;

export function setTrackingEnabled(v: boolean) {
  enabled = v;
}

export function track(kind: EventKind, opts: { slug?: string; path?: string; meta?: Record<string, number | boolean | string> } = {}) {
  if (!enabled) return;
  void api
    .post("/api/events", { kind, project_slug: opts.slug, path: opts.path ?? window.location.pathname, meta: opts.meta })
    .catch(() => undefined);
}

const SLUG_RE = /^\/projects\/([^/]+)/;

/** Mount once in the signed-in shell: records a page event on every route change. */
export function usePageTracking() {
  const site = useSite();
  const location = useLocation();
  useEffect(() => {
    setTrackingEnabled(site.study_enabled);
  }, [site.study_enabled]);
  useEffect(() => {
    const m = location.pathname.match(SLUG_RE);
    track("page", { slug: m?.[1], path: location.pathname });
  }, [location.pathname]);
}

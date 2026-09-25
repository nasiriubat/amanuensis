import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface LandingContent {
  eyebrow: string;
  headline: string;
  subheadline: string;
  cta_primary: string;
  cta_secondary: string;
  why_chat: string[];
  why_us: string[];
  principles: Array<{ title: string; text: string }>;
  closing: string;
}

export interface SiteInfo {
  name: string;
  tagline: string;
  footer: string;
  seo: { title: string; description: string; keywords: string; og_image: string; index: boolean };
  homepage: string;
  logo_url: string | null;
  nav_pages: Array<{ slug: string; title: string }>;
  landing: LandingContent;
  /** True when an SMTP server is configured, so "Forgot password?" can be offered. */
  password_reset: boolean;
  /** True while an admin runs the user study; the frontend then sends usage events. */
  study_enabled: boolean;
}

export const EMPTY_LANDING: LandingContent = {
  eyebrow: "",
  headline: "",
  subheadline: "",
  cta_primary: "Sign in",
  cta_secondary: "",
  why_chat: [],
  why_us: [],
  principles: [],
  closing: "",
};

const FALLBACK: SiteInfo = {
  name: "Coscribe",
  tagline: "",
  footer: "",
  seo: { title: "", description: "", keywords: "", og_image: "", index: true },
  homepage: "landing",
  logo_url: null,
  nav_pages: [],
  landing: EMPTY_LANDING,
  password_reset: false,
  study_enabled: false,
};

export function useSite(): SiteInfo {
  const q = useQuery({ queryKey: ["site"], queryFn: () => api.get<SiteInfo>("/api/site"), staleTime: 5 * 60_000 });
  return q.data ?? FALLBACK;
}

function setMeta(name: string, content: string, attr: "name" | "property" = "name") {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${name}"]`);
  if (!content) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, name);
    document.head.appendChild(el);
  }
  el.content = content;
}

/** Applies site name and SEO settings to the document. Pass a page title for sub-pages. */
export function useDocumentMeta(pageTitle?: string) {
  const site = useSite();
  useEffect(() => {
    const base = site.seo.title || site.name;
    document.title = pageTitle ? `${pageTitle} · ${base}` : site.tagline ? `${base} · ${site.tagline}` : base;
    setMeta("description", site.seo.description);
    setMeta("keywords", site.seo.keywords);
    setMeta("robots", site.seo.index ? "" : "noindex, nofollow");
    setMeta("og:title", document.title, "property");
    setMeta("og:description", site.seo.description, "property");
    setMeta("og:image", site.seo.og_image, "property");
    let icon = document.head.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (site.logo_url) {
      if (!icon) {
        icon = document.createElement("link");
        icon.rel = "icon";
        document.head.appendChild(icon);
      }
      icon.href = site.logo_url;
    }
  }, [site, pageTitle]);
  return site;
}

export function SiteLogo({ className = "h-7 w-7", iconClassName = "h-4 w-4" }: { className?: string; iconClassName?: string }) {
  const site = useSite();
  if (site.logo_url) return <img src={site.logo_url} alt={site.name} className={`${className} rounded-lg object-contain`} />;
  return (
    <span className={`${className} flex items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={iconClassName}>
        <path d="M12 7v14" />
        <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
      </svg>
    </span>
  );
}

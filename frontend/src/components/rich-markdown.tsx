import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import "katex/dist/katex.min.css";
import { cn } from "@/lib/utils";

/**
 * Full preview for sections: GFM, math, and the two placeholder syntaxes the drafting
 * step uses. [NEEDS: ...] and [CITE: ...] become highlighted marks; [@key] citations
 * become chips, red when the key is not verified.
 */
export function RichMarkdown({ source, badKeys, className }: { source: string; badKeys?: Set<string>; className?: string }) {
  const html = useMemo(() => {
    let s = source;
    s = s.replace(/\[NEEDS:\s*([^\]]+)\]/g, (_m, t: string) => `<mark class="ph ph-needs" title="Open item">NEEDS: ${escape(t.trim())}</mark>`);
    s = s.replace(/\[CITE:\s*([^\]]+)\]/g, (_m, t: string) => `<mark class="ph ph-cite" title="Needs a verified reference">CITE: ${escape(t.trim())}</mark>`);
    s = s.replace(/\[(@[^\]]+)\]/g, (_m, inner: string) => {
      const keys = inner
        .split(";")
        .map((k) => k.trim().replace(/^@/, ""))
        .filter(Boolean);
      return keys.map((k) => `<cite class="${badKeys?.has(k) ? "ck ck-bad" : "ck"}" title="${badKeys?.has(k) ? "Unverified reference" : "Verified reference"}">@${escape(k)}</cite>`).join(" ");
    });
    return s;
  }, [source, badKeys]);

  return (
    <div className={cn("prose-pw text-[14.5px]", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeRaw, rehypeKatex]}>
        {html}
      </ReactMarkdown>
    </div>
  );
}

function escape(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

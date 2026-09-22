import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Tiny, safe Markdown renderer for phase 1. Builds React elements, never HTML strings,
 * so there is no injection surface. Handles headings, paragraphs, lists, bold, italics,
 * inline code and fenced code. A full renderer with math and citations arrives with the
 * Studio in phase 4.
 */

function inline(text: string, key: number): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) parts.push(<code key={`${key}-${i++}`}>{tok.slice(1, -1)}</code>);
    else if (tok.startsWith("**")) parts.push(<strong key={`${key}-${i++}`}>{tok.slice(2, -2)}</strong>);
    else parts.push(<em key={`${key}-${i++}`}>{tok.slice(1, -1)}</em>);
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function Markdown({ source, className }: { source: string; className?: string }) {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const out: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(lines[i++]);
      i++;
      out.push(
        <pre key={key++} className="my-3 overflow-x-auto rounded-md bg-muted p-3 text-[12.5px] leading-relaxed">
          <code>{buf.join("\n")}</code>
        </pre>,
      );
      continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      const Tag = (`h${level}` as unknown) as "h1";
      out.push(<Tag key={key++}>{inline(h[2], key)}</Tag>);
      i++;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items: React.ReactNode[] = [];
      while (i < lines.length && (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
        const txt = lines[i].replace(/^\s*([-*]|\d+\.)\s+/, "");
        items.push(<li key={key++}>{inline(txt, key)}</li>);
        i++;
        // continuation lines indented under the bullet
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
          items[items.length - 1] = (
            <li key={key++}>
              {inline(txt + " " + lines[i].trim(), key)}
            </li>
          );
          i++;
        }
      }
      out.push(ordered ? <ol key={key++}>{items}</ol> : <ul key={key++}>{items}</ul>);
      continue;
    }
    // paragraph: gather until blank line or block start
    const buf: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4})\s/.test(lines[i]) && !lines[i].startsWith("```") && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
      buf.push(lines[i].trim());
      i++;
    }
    out.push(<p key={key++}>{inline(buf.join(" "), key)}</p>);
  }

  return <div className={cn("prose-pw text-[14px]", className)}>{out}</div>;
}

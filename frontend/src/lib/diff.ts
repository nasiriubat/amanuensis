/** Minimal line diff (LCS) for the version drawer. Good enough for section-sized texts. */
export type DiffLine = { type: "same" | "add" | "del"; text: string };

/** Word-level diff for the redline view. Tokens keep their trailing whitespace so the
 *  result can be rendered inline; newlines stay as their own tokens. */
export function diffWords(a: string, b: string): DiffLine[] {
  const tok = (s: string) => s.match(/\n|[^\s\n]+\s*|\s+/g) ?? [];
  const A = tok(a);
  const B = tok(b);
  const n = A.length;
  const m = B.length;
  if (n * m > 6_000_000) return diffLines(a, b);
  const dp: Uint16Array[] = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  const eq = (x: string, y: string) => x.trim() === y.trim() && (x === "\n") === (y === "\n");
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = eq(A[i], B[j]) ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  const push = (type: DiffLine["type"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.type === type && text !== "\n" && last.text !== "\n") last.text += text;
    else out.push({ type, text });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (eq(A[i], B[j])) {
      push("same", B[j]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) push("del", A[i++]);
    else push("add", B[j++]);
  }
  while (i < n) push("del", A[i++]);
  while (j < m) push("add", B[j++]);
  return out;
}

export function diffLines(a: string, b: string): DiffLine[] {
  const A = a.split("\n");
  const B = b.split("\n");
  const n = A.length;
  const m = B.length;
  if (n * m > 4_000_000) {
    return [...A.map((t) => ({ type: "del" as const, text: t })), ...B.map((t) => ({ type: "add" as const, text: t }))];
  }
  const dp: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) {
      out.push({ type: "same", text: A[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: "del", text: A[i++] });
    } else {
      out.push({ type: "add", text: B[j++] });
    }
  }
  while (i < n) out.push({ type: "del", text: A[i++] });
  while (j < m) out.push({ type: "add", text: B[j++] });
  return out;
}

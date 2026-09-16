#!/usr/bin/env node
// Repo-shape gates that no compiler owns. Language-neutral: every check reads paths, markdown and
// regexes from `llmfw.config.json`, never from stack knowledge. Node is only the runner — the project
// needs no npm dependency. Add a check here when a convention is violated twice
// ("prose does not fail a build", conventions/README.md § escalation ladder).
//
//   node scripts/check-repo.mjs [--config llmfw.config.json] [--root .] [--only check1,check2]
//   node scripts/check-repo.mjs --allow-missing-config   (run with an empty config; every
//                                                          check that needs config entries no-ops)
//
// Exit 1 if any check failed, or if the config is missing and --allow-missing-config wasn't
// passed. Each failure line is `<check>: <message>` so CI can group them.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

// ---------- arguments ----------
const args = Object.fromEntries(
  process.argv
    .slice(2)
    .map((a, i, all) => (a.startsWith("--") ? [a.slice(2), all[i + 1] ?? "true"] : null))
    .filter(Boolean),
);
const root = path.resolve(args.root ?? ".");
const configPath = path.resolve(root, args.config ?? "llmfw.config.json");
let cfg = {};
if (!existsSync(configPath)) {
  if (!args["allow-missing-config"]) {
    console.error(`check-repo: no config at ${configPath} (copy gates/llmfw.config.example.json)`);
    process.exit(1);
  }
} else {
  cfg = JSON.parse(readFileSync(configPath, "utf8"));
}
const only = args.only ? new Set(args.only.split(",")) : null;

// ---------- helpers ----------
const failures = [];
const fail = (check, message) => failures.push(`${check}: ${message}`);
const rel = (p) => path.relative(root, p).split(path.sep).join("/");
// Directory names (globs allowed: `.next*`) skipped everywhere. Build output is never a finding.
const ignoreDirGlobs = cfg.ignoreDirs ?? [
  "node_modules",
  "bin",
  "obj",
  ".next*",
  ".git",
  "dist",
  "build",
  ".venv",
];
const isIgnoredDir = (name) => ignoreDirGlobs.some((g) => globToRegExp(g).test(name));

function walk(dir, predicate, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory() && isIgnoredDir(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, predicate, out);
    else if (predicate(full)) out.push(full);
  }
  return out;
}

// Minimal glob → RegExp: `**` any depth, `*` within a segment, `?` one char. Matched against repo-relative paths.
function globToRegExp(glob) {
  let re = "";
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === "*") {
      if (glob[i + 1] === "*") {
        re += glob[i + 2] === "/" ? "(?:.*/)?" : ".*";
        i += glob[i + 2] === "/" ? 2 : 1;
      } else re += "[^/]*";
    } else if (c === "?") re += "[^/]";
    else re += c.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  }
  return new RegExp(`^${re}$`);
}
const matchesAny = (relPath, globs = []) => globs.some((g) => globToRegExp(g).test(relPath));

function dirsMatching(glob) {
  // Expand a directory glob like `api/src/Modules/*` or `packages/**/src` against the tree.
  const re = globToRegExp(glob);
  const out = [];
  const visit = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory() || isIgnoredDir(entry.name)) continue;
      const full = path.join(dir, entry.name);
      if (re.test(rel(full))) out.push(full);
      visit(full);
    }
  };
  visit(root);
  return out;
}

const read = (p) => readFileSync(p, "utf8");
const lineCount = (text) =>
  text.split("\n").filter((l, i, a) => !(i === a.length - 1 && l === "")).length;
const stripFences = (md) => md.replace(/^```[\s\S]*?^```/gm, "");

function run(name, fn) {
  if (only && !only.has(name)) return;
  try {
    fn();
  } catch (e) {
    fail(name, `check crashed: ${e.message}`);
  }
}

// ---------- checks ----------

// agents-link — every vendor file (CLAUDE.md, .cursorrules, …) is exactly the import line (doc-01).
run("agents-link", () => {
  const importLine = cfg.agents?.vendorImportLine ?? "@AGENTS.md";
  for (const name of cfg.agents?.vendorFiles ?? ["CLAUDE.md"]) {
    for (const file of walk(root, (f) => path.basename(f) === name)) {
      const text = read(file).trim();
      if (text !== importLine)
        fail(
          "agents-link",
          `${rel(file)} must contain only "${importLine}" — edit the sibling AGENTS.md instead`,
        );
      if (!existsSync(path.join(path.dirname(file), cfg.agents?.file ?? "AGENTS.md")))
        fail("agents-link", `${rel(file)} imports AGENTS.md but none exists beside it`);
    }
  }
});

// scope-cards — every scope dir has a card, within the line limit, with resolving file:line pointers (agents/nesting.md).
run("scope-cards", () => {
  const sc = cfg.agents?.scopeCards;
  if (!sc) return;
  const cardName = cfg.agents?.file ?? "AGENTS.md";
  const maxLines = sc.maxLines ?? 40;
  for (const glob of sc.globs ?? []) {
    for (const dir of dirsMatching(glob)) {
      if (matchesAny(rel(dir), sc.exempt ?? [])) continue;
      const card = path.join(dir, cardName);
      if (!existsSync(card)) {
        fail(
          "scope-cards",
          `${rel(dir)} has no ${cardName} (template: agents/templates/AGENTS.scope.md)`,
        );
        continue;
      }
      const text = read(card);
      const n = lineCount(text);
      if (n > maxLines)
        fail("scope-cards", `${rel(card)} is ${n} lines, limit ${maxLines} — pointers, not prose`);
      // `path/to/file.ext:12` or `path/to/file.ext` inside backticks; resolve relative to repo root, then to the card's dir.
      for (const m of text.matchAll(/`([\w./-]+\.[A-Za-z0-9]+)(?::(\d+))?`/g)) {
        const [, p, line] = m;
        if (p.includes("<") || /^(https?:|\.\/?$)/.test(p)) continue;
        const candidates = [path.join(root, p), path.join(dir, p)];
        const hit = candidates.find((c) => existsSync(c) && statSync(c).isFile());
        if (!hit) {
          if (sc.pointersMustResolve !== false)
            fail("scope-cards", `${rel(card)} points at missing ${p}`);
          continue;
        }
        if (line && Number(line) > lineCount(read(hit)))
          fail("scope-cards", `${rel(card)} points at ${p}:${line} but the file has fewer lines`);
      }
    }
  }
});

// rule-ids — an ID (`llm-03`, `con-12`) is defined once across conventions + constitution (conventions/README.md).
run("rule-ids", () => {
  const files = walk(path.join(root, cfg.docs?.conventionsDir ?? "docs/conventions"), (f) =>
    f.endsWith(".md"),
  );
  const constitution = path.join(root, cfg.docs?.constitution ?? "docs/CONSTITUTION.md");
  if (existsSync(constitution)) files.push(constitution);
  const seen = new Map();
  for (const file of files) {
    for (const m of read(file).matchAll(/^#{2,4}\s+`?([a-z][a-z0-9]{1,5}-\d{2})`?/gm)) {
      if (seen.has(m[1]))
        fail("rule-ids", `${m[1]} defined in both ${rel(seen.get(m[1]))} and ${rel(file)}`);
      seen.set(m[1], file);
    }
  }
});

// adr — numbers unique (parallel sessions collide on "next free"), each under the line cap (doc-01).
run("adr", () => {
  const dir = path.join(root, cfg.docs?.adrDir ?? "docs/adr");
  if (!existsSync(dir)) return;
  const maxLines = cfg.docs?.adrMaxLines ?? 45;
  const seen = new Map();
  for (const file of readdirSync(dir)) {
    const m = /^(\d{4})-/.exec(file);
    if (!m) continue;
    if (seen.has(m[1])) fail("adr", `${m[1]} used by both ${seen.get(m[1])} and ${file}`);
    seen.set(m[1], file);
    const n = lineCount(read(path.join(dir, file)));
    if (n > maxLines)
      fail("adr", `${file} is ${n} lines, limit ${maxLines} — an ADR is invariants, not history`);
  }
});

// debt-ledger — every `DEBT #N` in code has a ledger line and vice versa (llm-10).
run("debt-ledger", () => {
  const ledgerPath = path.join(root, cfg.docs?.debtLedger ?? "docs/tech-debts.md");
  const ledger = existsSync(ledgerPath) ? read(ledgerPath) : "";
  const ledgerIds = new Set([...ledger.matchAll(/^\|?\s*#(\d+)\b/gm)].map((m) => m[1]));
  const exts = cfg.source?.extensions ?? [
    ".cs",
    ".ts",
    ".tsx",
    ".mjs",
    ".js",
    ".css",
    ".yml",
    ".yaml",
    ".sql",
  ];
  const codeIds = new Map();
  for (const file of walk(
    root,
    (f) => exts.includes(path.extname(f)) && !matchesAny(rel(f), cfg.source?.exempt ?? []),
  )) {
    if (rel(file).startsWith((cfg.docs?.dir ?? "docs") + "/")) continue;
    for (const m of read(file).matchAll(/DEBT #(\d+)\b/g))
      if (!codeIds.has(m[1])) codeIds.set(m[1], file);
  }
  for (const [id, file] of codeIds)
    if (!ledgerIds.has(id))
      fail("debt-ledger", `DEBT #${id} in ${rel(file)} has no line in ${rel(ledgerPath)}`);
  for (const id of ledgerIds)
    if (!codeIds.has(id))
      fail("debt-ledger", `#${id} in ${rel(ledgerPath)} has no 'DEBT #${id}' comment in code`);
});

// md-links — relative markdown links resolve (doc-03). Fenced blocks are templates, not links.
run("md-links", () => {
  for (const file of walk(
    root,
    (f) => f.endsWith(".md") && !matchesAny(rel(f), cfg.docs?.linkExempt ?? []),
  )) {
    const text = stripFences(read(file));
    for (const m of text.matchAll(/\]\((?!https?:|mailto:|#)([^)\s#]+)(?:#[^)]*)?\)/g)) {
      if (m[1].includes("<")) continue;
      if (!existsSync(path.resolve(path.dirname(file), m[1])))
        fail("md-links", `${rel(file)} links to missing ${m[1]}`);
    }
  }
});

// file-size — a source file fits a context window (llm-06). Generated and migration files are exempt by glob.
run("file-size", () => {
  const fs = cfg.source?.fileSize;
  if (!fs) return;
  const exts = cfg.source?.extensions ?? [];
  for (const file of walk(root, (f) => exts.includes(path.extname(f)))) {
    const r = rel(file);
    if (matchesAny(r, [...(cfg.source?.exempt ?? []), ...(fs.exempt ?? [])])) continue;
    const n = lineCount(read(file));
    if (n > fs.maxLines)
      fail("file-size", `${r} is ${n} lines, limit ${fs.maxLines} — a second responsibility?`);
  }
});

// forbidden-patterns — regexes a stack has no analyzer for (llm-04 scans, vc-09 home paths, …). Each carries its rule ID.
run("forbidden-patterns", () => {
  for (const rule of cfg.forbiddenPatterns ?? []) {
    const re = new RegExp(rule.pattern, "g");
    const fileRe = rule.files ? new RegExp(rule.files) : null;
    for (const file of walk(
      root,
      (f) => (!fileRe || fileRe.test(rel(f))) && !matchesAny(rel(f), rule.exempt ?? []),
    )) {
      const text = read(file);
      const m = re.exec(text);
      re.lastIndex = 0;
      if (m) {
        const line = text.slice(0, m.index).split("\n").length;
        fail(
          "forbidden-patterns",
          `${rel(file)}:${line} matches /${rule.pattern}/ — ${rule.message} (${rule.id})`,
        );
      }
    }
  }
});

// forbidden-paths — grab-bag file or folder names (llm-02), with the one grandfathered allow-list.
run("forbidden-paths", () => {
  for (const rule of cfg.forbiddenPaths ?? []) {
    const re = new RegExp(rule.pattern);
    for (const file of walk(
      root,
      (f) => re.test(rel(f)) && !matchesAny(rel(f), rule.allow ?? []),
    )) {
      fail(
        "forbidden-paths",
        `${rel(file)} matches /${rule.pattern}/ — ${rule.message} (${rule.id})`,
      );
    }
  }
});

// feature-e2e — every feature folder has an end-to-end spec (tst-07).
run("feature-e2e", () => {
  for (const f of cfg.features ?? []) {
    const featuresDir = path.join(root, f.dir);
    if (!existsSync(featuresDir)) continue;
    const specs = existsSync(path.join(root, f.specDir))
      ? readdirSync(path.join(root, f.specDir))
      : [];
    for (const feature of readdirSync(featuresDir)) {
      if (!statSync(path.join(featuresDir, feature)).isDirectory()) continue;
      if (!specs.some((s) => s.startsWith(`${feature}.`) || s.startsWith(`${feature}-`)))
        fail(
          "feature-e2e",
          `${f.dir}/${feature} has no ${f.specDir}/${feature}*.spec.* (${f.id ?? "tst-07"})`,
        );
    }
  }
});

// toolchain-version — one pinned version everywhere (vc-10): a JSON source of truth and files that must agree.
run("toolchain-version", () => {
  for (const t of cfg.toolchain ?? []) {
    const src = path.join(root, t.source);
    if (!existsSync(src)) {
      fail("toolchain-version", `${t.source} missing`);
      continue;
    }
    const expected = t.jsonPath
      ? t.jsonPath.split(".").reduce((o, k) => o?.[k], JSON.parse(read(src)))
      : read(src).trim();
    if (!expected) fail("toolchain-version", `${t.source} has no value at ${t.jsonPath}`);
    if (t.jsonPath && t.requireField) {
      const v = t.requireField.path.split(".").reduce((o, k) => o?.[k], JSON.parse(read(src)));
      if (v !== t.requireField.value)
        fail(
          "toolchain-version",
          `${t.source} ${t.requireField.path} is "${v}", expected "${t.requireField.value}"`,
        );
    }
    for (const target of t.mustMatch ?? []) {
      const fileRe = new RegExp(target.files);
      for (const file of walk(root, (f) => fileRe.test(rel(f)))) {
        for (const m of read(file).matchAll(new RegExp(target.pattern, "g")))
          if (m[1] !== expected)
            fail("toolchain-version", `${rel(file)} uses ${m[1]}, ${t.source} pins ${expected}`);
      }
    }
  }
});

// ---------- report ----------
if (failures.length) {
  console.error(failures.join("\n"));
  console.error(`\ncheck-repo: ${failures.length} failure(s)`);
  process.exit(1);
}
console.log("check-repo: ok");

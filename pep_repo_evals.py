#!/usr/bin/env python3
"""PEP Nuke Tools - repo evals. Pass/fail checks, run before AND after a change.

Encodes the lessons that actually bit us:
  1. every module that uses QtCore imports it   (the bug that shipped twice)
  2. no old-author / other-tool names in published files
  3. footer: only "GitHub" is a link, brand is plain text
  4. every menu command resolves to a real module + function
  5. every shipped tool is documented in README / HELP / CHANGELOG

Run:  python pep_repo_evals.py           (defaults to this file's repo)
Exit code 0 = all pass (safe to commit), 1 = something drifted.
"""
import os
import re
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(REPO, "gizmos", "pep_tools")
SELF = os.path.basename(os.path.abspath(__file__))
# other-tool / other-author names that must never appear in published files.
# (Neat Video is intentionally allowed - it is an optional denoiser feature.)
BANNED = ["luma", "billington", "busquets", "graduo", "fix blacks",
          "clipping degrainer", "nukepedia",
          "geremia", "monroy", "gogavfx", "cragl"]

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))

def pyfiles():
    return [os.path.join(TOOLS, f) for f in os.listdir(TOOLS)
            if f.endswith(".py") and f not in ("__init__.py", "init.py", "menu.py")]

def read(p):
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()

# 1. QtCore import wherever QtCore is used
bad = []
for p in pyfiles():
    t = read(p)
    if "QtCore." in t and not re.search(r"import\s+QtWidgets,\s*QtCore|import\s+QtCore", t):
        bad.append(os.path.basename(p))
check("QtCore imported where used", not bad, "missing in: " + ", ".join(bad))

# 2. no banned names in published .py / .md (skip this eval file - it lists them)
hits = []
for root, dirs, files in os.walk(REPO):
    if ".git" in root:
        continue
    for f in files:
        if f == SELF or not f.endswith((".py", ".md", ".gizmo")):
            continue
        t = read(os.path.join(root, f)).lower()
        for b in BANNED:
            if b in t:
                hits.append("%s:%s" % (f, b))
check("no old-author/tool names", not hits, "; ".join(hits))

# 3. footer format: brand plain text, only GitHub linked
foot_bad = []
for p in pyfiles():
    t = read(p)
    if "_FOOTER" in t and re.search(r'<a[^>]*>[^<]*Pixel Eye Pictures', t):
        foot_bad.append(os.path.basename(p))
check("footer: only GitHub is a link", not foot_bad, "; ".join(foot_bad))

# 4. menu commands resolve to real module.function
menu = read(os.path.join(TOOLS, "menu.py"))
menu_bad = []
for m in re.finditer(r"import (\w+) as \w+; \w+\.(\w+)\(", menu):
    mod, fn = m.group(1), m.group(2)
    modp = os.path.join(TOOLS, mod + ".py")
    if not os.path.exists(modp):
        menu_bad.append("%s (no module)" % mod)
    elif not re.search(r"def %s\b" % re.escape(fn), read(modp)):
        menu_bad.append("%s.%s (no def)" % (mod, fn))
check("menu commands resolve", not menu_bad, "; ".join(menu_bad))

# 5. shipped tools documented in README / HELP / CHANGELOG
readme = read(os.path.join(REPO, "README.md"))
helpmd = read(os.path.join(REPO, "HELP.md"))
change = read(os.path.join(REPO, "CHANGELOG.md"))
SHIPPED = ["TrackPin", "Clipping Degrain", "Gradient", "Match Blacks",
           "Marker Cleanup", "Read Node Manager"]
doc_bad = []
for tool in SHIPPED:
    where = [d for d, txt in (("README", readme), ("HELP", helpmd), ("CHANGELOG", change))
             if tool not in txt]
    if where:
        doc_bad.append("%s (missing in %s)" % (tool, "/".join(where)))
check("tools documented", not doc_bad, "; ".join(doc_bad))

# ---- report ----
npass = sum(1 for _, ok, _ in results if ok)
print("PEP repo evals  %d/%d" % (npass, len(results)))
for name, ok, detail in results:
    print("  [%s] %s%s" % ("x" if ok else " ", name, ("  -> " + detail) if detail and not ok else ""))
sys.exit(0 if npass == len(results) else 1)

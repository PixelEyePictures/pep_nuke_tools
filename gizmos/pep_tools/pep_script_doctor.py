from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path


NODE_START_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\.]*)\s*\{\s*$")
NAME_RE = re.compile(r"^\s*name\s+(.+?)\s*$")
FILE_RE = re.compile(r"^\s*file\s+(.+?)\s*$")
DISABLE_RE = re.compile(r"^\s*disable\s+(.+?)\s*$")


@dataclass
class NodeBlock:
    klass: str
    start: int
    end: int
    name: str = ""
    file_path: str = ""
    disabled: str = ""


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8", errors="replace")


def block_end(lines: list[str], start: int) -> int:
    depth = 0
    for index in range(start, len(lines)):
        line = lines[index]
        depth += line.count("{")
        depth -= line.count("}")
        if depth <= 0 and index > start:
            return index
    return start


def clean_value(value: str) -> str:
    value = value.strip()
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value.strip()


def parse_nodes(lines: list[str]) -> list[NodeBlock]:
    nodes: list[NodeBlock] = []
    index = 0
    while index < len(lines):
        match = NODE_START_RE.match(lines[index].strip())
        if not match:
            index += 1
            continue

        klass = match.group(1)
        end = block_end(lines, index)
        block = lines[index : end + 1]
        node = NodeBlock(klass=klass, start=index, end=end)
        for line in block:
            name_match = NAME_RE.match(line)
            if name_match:
                node.name = clean_value(name_match.group(1))
            file_match = FILE_RE.match(line)
            if file_match:
                node.file_path = clean_value(file_match.group(1))
            disable_match = DISABLE_RE.match(line)
            if disable_match:
                node.disabled = clean_value(disable_match.group(1))
        nodes.append(node)
        index = end + 1
    return nodes


def class_counts(nodes: list[NodeBlock]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node.klass] = counts.get(node.klass, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def looks_missing(path_text: str) -> bool:
    if not path_text or any(token in path_text for token in ("[", "%", "#")):
        return False
    expanded = os.path.expandvars(path_text)
    return (":" in expanded or expanded.startswith(("/", "\\"))) and not os.path.exists(expanded)


def make_report(script_path: Path, lines: list[str], nodes: list[NodeBlock]) -> str:
    counts = class_counts(nodes)
    viewers = [node for node in nodes if node.klass == "Viewer"]
    reads = [node for node in nodes if node.klass in ("Read", "DeepRead", "ReadGeo", "Camera2")]
    missing = [node for node in reads if looks_missing(node.file_path)]
    suspicious = [
        node
        for node in nodes
        if node.klass.lower() in ("rotopaint", "roto", "vectorblur", "defocus", "zdefocus", "scanlinerender")
    ]

    out: list[str] = []
    out.append("PEP Script Doctor Report")
    out.append("=" * 24)
    out.append("")
    out.append(f"script: {script_path}")
    out.append(f"lines: {len(lines)}")
    out.append(f"nodes: {len(nodes)}")
    out.append(f"generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    out.append("")
    out.append("Class counts:")
    for klass, count in counts.items():
        out.append(f"  {klass}: {count}")
    out.append("")
    views = detect_views(lines, nodes)
    if views:
        out.append(f"Views: STEREO / multi-view ({views}) -> turn ALL Viewers "
                   f"off (no_viewers or disconnect_viewers).")
    out.append(f"Viewers: {len(viewers)}")
    if len(viewers) > 1:
        out.append("  (2+ Viewers: keep_one_viewer keeps one disconnected; "
                   "disconnect_viewers turns them all off; no_viewers deletes all.)")
    for node in viewers:
        out.append(f"  line {node.start + 1}: {node.name or node.klass}")
    out.append("")
    out.append("Read-like nodes:")
    for node in reads[:80]:
        status = "MISSING?" if node in missing else "path"
        out.append(f"  line {node.start + 1}: {node.name or node.klass} | {status}: {node.file_path}")
    if len(reads) > 80:
        out.append(f"  ... {len(reads) - 80} more")
    out.append("")
    out.append("Heavy/corruption suspects:")
    for node in suspicious[:120]:
        out.append(f"  line {node.start + 1}: {node.klass} {node.name}")
    if len(suspicious) > 120:
        out.append(f"  ... {len(suspicious) - 120} more")
    out.append("")
    out.append("Notes:")
    out.append("  Original scripts are not edited.")
    out.append("  Rescue copies are plain text .nk files.")
    out.append("  Missing-path detection skips expressions, hashes, and printf patterns.")
    out.append("")
    out.append("If the script LOADS then CRASHES, try in this order:")
    out.append("  1. open_paused_*.bat        -> opens with --pause (nothing evaluates).")
    out.append("  2. rescued_no_viewers.nk    -> crash was a Viewer computing on open.")
    out.append("  3. rescued_disable_all.nk   -> every node inert; re-enable to find culprit.")
    out.append("  4. rescued_no_callbacks.nk  -> crash was a knobChanged/autolabel callback.")
    out.append("  5. rescued_no_viewers_no_roto.nk / rescued_disable_heavy.nk -> corrupt roto / heavy node.")
    out.append("  6. rescued_no_plugins.nk    -> a missing OFX/plugin node crashes on load.")
    out.append("  7. rescued_no_postage.nk    -> a postage-stamp thumbnail crashes on load.")
    out.append("  8. rescued_bisect_first_half.nk / _second_half.nk -> narrow down which half holds the culprit.")
    out.append("  9. rescued_keep_one_viewer.nk / _disconnect_viewers.nk -> stereo / multi-Viewer crash on open.")
    out.append(" 10. rescued_strip_non_ascii.nk -> stray non-ASCII bytes broke the parse (only if any were found).")
    out.append("")
    out.append("Know the offender already? Use Match nodes (by name or knob value) to")
    out.append("disable / disconnect / remove just those, or drop the crash log to auto-target it.")
    return "\n".join(out) + "\n"


def remove_classes(lines: list[str], nodes: list[NodeBlock], classes: set[str]) -> list[str]:
    remove_ranges = [(node.start, node.end) for node in nodes if node.klass in classes]
    if not remove_ranges:
        return list(lines)
    remove_lines: set[int] = set()
    for start, end in remove_ranges:
        remove_lines.update(range(start, end + 1))
    return [line for index, line in enumerate(lines) if index not in remove_lines]


def disable_classes(lines: list[str], nodes: list[NodeBlock], classes,
                    skip: frozenset = frozenset(
                        {"Root", "Viewer", "Dot", "BackdropNode", "StickyNote"})) -> list[str]:
    """Set `disable true` on matching nodes. classes=None means ALL nodes
    (except `skip`, e.g. Root)."""
    out = list(lines)
    for node in reversed(nodes):
        if node.klass in skip:
            continue
        if classes is not None and node.klass not in classes:
            continue
        block = out[node.start : node.end + 1]
        has_disable = any(DISABLE_RE.match(line) for line in block)
        if has_disable:
            for index in range(node.start, node.end + 1):
                if DISABLE_RE.match(out[index]):
                    out[index] = " disable true\n"
                    break
        else:
            out.insert(node.start + 1, " disable true\n")
    return out


# Per-node callback knobs that run code on load / interaction and can crash
# a script the moment it opens.
_CALLBACK_RE = re.compile(
    r"^\s*(knobChanged|onCreate|onDestroy|updateUI|autolabel|beforeRender|"
    r"afterRender|beforeFrameRender|afterFrameRender|onScriptLoad|"
    r"onScriptSave|onScriptClose)\b"
)


def strip_callbacks(lines: list[str]) -> list[str]:
    """Remove per-node callback knob lines (and their brace-continued value),
    so a script that crashes via a callback on open can still load."""
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if _CALLBACK_RE.match(line):
            depth = line.count("{") - line.count("}")
            index += 1
            while index < len(lines) and depth > 0:
                depth += lines[index].count("{") - lines[index].count("}")
                index += 1
            continue
        out.append(line)
        index += 1
    return out


def make_pause_bat(out_dir: Path, nuke_exe: str, script_path: Path) -> Path:
    bat = out_dir / f"open_paused_{script_path.stem}.bat"
    bat.write_text(
        "@echo off\n"
        f'"{nuke_exe}" --pause "{script_path}"\n'
        "pause\n",
        encoding="utf-8",
    )
    return bat


_HEAVY = {"Roto", "RotoPaint", "VectorBlur", "Defocus", "ZDefocus", "ScanlineRender"}
_DISABLE_SKIP = frozenset({"Root", "Viewer", "Dot", "BackdropNode", "StickyNote"})


def disable_nodes(lines: list[str], nodes: list[NodeBlock], subset) -> list[str]:
    """Set `disable true` on a specific set of NodeBlocks (skips structural)."""
    keep = {id(n) for n in subset}
    out = list(lines)
    for node in reversed(nodes):
        if id(node) not in keep or node.klass in _DISABLE_SKIP:
            continue
        block = out[node.start:node.end + 1]
        if any(DISABLE_RE.match(line) for line in block):
            for index in range(node.start, node.end + 1):
                if DISABLE_RE.match(out[index]):
                    out[index] = " disable true\n"
                    break
        else:
            out.insert(node.start + 1, " disable true\n")
    return out


def strip_postage_stamps(lines: list[str]) -> list[str]:
    return [re.sub(r"(\bpostage_stamp)\s+true", r"\1 false", line) for line in lines]


def keep_one_viewer(lines: list[str], nodes: list[NodeBlock]) -> list[str]:
    """When there are 2+ Viewers, delete them all and leave a single
    disconnected Viewer - keeps one usable Viewer without it evaluating."""
    viewers = [n for n in nodes if n.klass == "Viewer"]
    if len(viewers) <= 1:
        return list(lines)                       # nothing to trim
    out = remove_classes(lines, nodes, {"Viewer"})
    out.extend(["Viewer {\n", " inputs 0\n", " name PEP_Viewer\n", "}\n"])
    return out


_INPUTS_RE = re.compile(r"^\s*inputs\s+\d+")


def disconnect_viewers(lines: list[str], nodes: list[NodeBlock]) -> list[str]:
    """Keep every Viewer but disconnect it (inputs 0) - all Viewers off. Good
    for stereo/multi-view scripts where you want none of them evaluating."""
    viewers = [n for n in nodes if n.klass == "Viewer"]
    if not viewers:
        return list(lines)
    out = list(lines)
    for n in sorted(viewers, key=lambda v: -v.start):   # reverse: keep indices valid
        found = None
        for i in range(n.start, n.end + 1):
            if _INPUTS_RE.match(out[i]):
                found = i
                break
        if found is not None:
            out[found] = " inputs 0\n"
        else:
            out.insert(n.start + 1, " inputs 0\n")
    return out


def strip_non_ascii(lines: list[str]) -> list[str]:
    """Drop non-ASCII bytes - stray non-ASCII in a .nk can break the parse."""
    return [line.encode("ascii", "ignore").decode("ascii") for line in lines]


def _disconnect_specific(lines: list[str], nodes: list[NodeBlock], subset) -> list[str]:
    """Set `inputs 0` on a specific set of nodes (disconnect them)."""
    out = list(lines)
    for n in sorted(subset, key=lambda v: -v.start):
        found = None
        for i in range(n.start, n.end + 1):
            if _INPUTS_RE.match(out[i]):
                found = i
                break
        if found is not None:
            out[found] = " inputs 0\n"
        else:
            out.insert(n.start + 1, " inputs 0\n")
    return out


def match_nodes(lines: list[str], nodes: list[NodeBlock], pattern: str,
                where: str = "name", mode: str = "disable", regex: bool = False):
    """Select nodes by name or by any knob value matching `pattern`, then
    disable / disconnect / remove them. Returns (new_lines, matched_names)."""
    if regex:
        try:
            rx = re.compile(pattern)
            test = lambda s: bool(rx.search(s))
        except re.error:
            test = lambda s: pattern in s
    else:
        pat = pattern.lower()
        test = lambda s: pat in s.lower()

    matched = []
    for n in nodes:
        if n.klass == "Root":
            continue
        if where == "name":
            hit = bool(n.name) and test(n.name)
        else:                                    # scan the block's knob lines
            hit = any(test(line) for line in lines[n.start + 1:n.end])
        if hit:
            matched.append(n)

    if not matched:
        return list(lines), []
    if mode == "remove":
        out = remove_nodes(lines, nodes, matched)
    elif mode == "disconnect":
        out = _disconnect_specific(lines, nodes, matched)
    else:
        out = disable_nodes(lines, nodes, matched)
    return out, [n.name or n.klass for n in matched]


def detect_views(lines: list[str], nodes: list[NodeBlock]):
    """Return the view names (e.g. 'left right') if the script is multi-view /
    stereo, else None. Handles Nuke's multi-line `views { {left ..} {right ..} }`
    block and the single-line form."""
    root = next((n for n in nodes if n.klass == "Root"), None)
    if not root:
        return None
    text = "".join(lines[root.start:root.end + 1])
    block = re.search(r"\bviews\s*\{(.*?)\n\s*\}", text, re.S)
    if block:                                    # each view is `{ name colour }`
        names = re.findall(r"\{\s*([A-Za-z_]\w*)", block.group(1))
    else:                                        # single-line: views "left right"
        line = re.search(r"\bviews\s+([^\n{]+)", text)
        names = re.findall(r"[A-Za-z_]\w*", line.group(1)) if line else []
    seen = []
    for x in names:
        if x.lower() != "main" and x not in seen:
            seen.append(x)
    return " ".join(seen) if len(seen) >= 2 else None


def remove_nodes(lines: list[str], nodes: list[NodeBlock], subset) -> list[str]:
    """Remove a specific set of NodeBlocks by text range."""
    kill = {id(n) for n in subset}
    drop: set[int] = set()
    for n in nodes:
        if id(n) in kill:
            drop.update(range(n.start, n.end + 1))
    return [line for i, line in enumerate(lines) if i not in drop] if drop else list(lines)


def _word_re(tok: str):
    return re.compile(r"(?<![A-Za-z0-9_.])" + re.escape(tok) + r"(?![A-Za-z0-9_])")


def analyze_crash_log(log_text: str, nodes: list[NodeBlock]):
    """Scan a Nuke crash log for node classes / names present in the script.
    Returns (class_hits, name_hits, suspect_nodes)."""
    classes = sorted({n.klass for n in nodes}, key=len, reverse=True)
    names = sorted({n.name for n in nodes if n.name and len(n.name) >= 3},
                   key=len, reverse=True)
    class_hits, name_hits = {}, {}
    for c in classes:
        found = _word_re(c).findall(log_text)
        if found:
            class_hits[c] = len(found)
    for nm in names:
        found = _word_re(nm).findall(log_text)
        if found:
            name_hits[nm] = len(found)
    suspects = [n for n in nodes
                if n.klass in class_hits or (n.name and n.name in name_hits)]
    return class_hits, name_hits, suspects


def find_autosaves(script_path: Path) -> list[Path]:
    """Locate Nuke autosave / backup files next to the script (unsaved-work
    recovery)."""
    d = script_path.parent
    stem, name = script_path.stem, script_path.name
    cands: list[Path] = []
    for cand in (d / (name + "~"), d / (stem + ".autosave"),
                 d / (name + ".autosave"), d / (stem + "_autosave.nk")):
        if cand.exists() and cand not in cands:
            cands.append(cand)
    for p in sorted(d.glob("*.autosave")):
        if p not in cands:
            cands.append(p)
    return cands


# --------------------------------------------------------------------------- #
# Rescue steps registry - extensible: add your own with rescue_step(name, desc)
# --------------------------------------------------------------------------- #
RESCUE_STEPS: dict = {}   # name -> {"desc": str, "run": func(lines, nodes)->lines}


def rescue_step(name: str, desc: str):
    def deco(fn):
        RESCUE_STEPS[name] = {"desc": desc, "run": fn}
        return fn
    return deco


rescue_step("no_viewers", "Remove all Viewers (Viewer-eval crash)")(
    lambda lines, nodes: remove_classes(lines, nodes, {"Viewer"}))
rescue_step("no_viewers_no_roto", "Remove Viewers + Roto/RotoPaint (corrupt roto)")(
    lambda lines, nodes: remove_classes(lines, nodes, {"Viewer", "Roto", "RotoPaint"}))
rescue_step("disable_heavy", "Disable heavy nodes (Defocus/VectorBlur/etc.)")(
    lambda lines, nodes: disable_classes(lines, nodes, _HEAVY))
rescue_step("disable_all", "Disable every node (whole graph inert)")(
    lambda lines, nodes: disable_classes(lines, nodes, None))
rescue_step("no_callbacks", "Strip per-node callbacks (load-crash)")(
    lambda lines, nodes: strip_callbacks(lines))
# --- diversified steps (beyond a fixed rescue set) ---
rescue_step("no_plugins", "Remove OFX/plugin nodes (dotted class = missing plugin)")(
    lambda lines, nodes: remove_classes(lines, nodes, {n.klass for n in nodes if "." in n.klass}))
rescue_step("no_postage", "Turn off postage-stamp thumbnails")(
    lambda lines, nodes: strip_postage_stamps(lines))
rescue_step("bisect_first_half", "Disable the FIRST half of the graph (bisect the culprit)")(
    lambda lines, nodes: disable_nodes(lines, nodes, nodes[:len(nodes) // 2]))
rescue_step("bisect_second_half", "Disable the SECOND half of the graph (bisect the culprit)")(
    lambda lines, nodes: disable_nodes(lines, nodes, nodes[len(nodes) // 2:]))
rescue_step("keep_one_viewer", "Keep ONE disconnected Viewer, delete the extras (2+ Viewers)")(
    keep_one_viewer)
rescue_step("disconnect_viewers", "Disconnect ALL Viewers, keep them (all off - good for stereo)")(
    disconnect_viewers)
rescue_step("strip_non_ascii", "Strip non-ASCII characters (stray bytes can break the parse)")(
    lambda lines, nodes: strip_non_ascii(lines))

DEFAULT_RESCUES = {name: True for name in RESCUE_STEPS}


def doctor_script(script_path: Path, out_dir: Path, nuke_exe: str,
                  rescues: dict | None = None, crash_log=None) -> int:
    if not script_path.exists() or script_path.suffix.lower() != ".nk":
        print(f"Not a .nk file: {script_path}")
        return 2

    opts = dict(DEFAULT_RESCUES)
    if rescues:
        opts.update(rescues)

    out_dir.mkdir(parents=True, exist_ok=True)
    original_copy = out_dir / f"{script_path.stem}_original_copy.nk"
    shutil.copy2(str(script_path), str(original_copy))

    lines = read_lines(script_path)
    nodes = parse_nodes(lines)

    report_path = out_dir / f"{script_path.stem}_doctor_report.txt"
    report_path.write_text(make_report(script_path, lines, nodes), encoding="utf-8")

    stem = script_path.stem
    made, skipped, unchanged = [], [], []
    for name, step in RESCUE_STEPS.items():
        if not opts.get(name, True):
            skipped.append(name)
            continue
        result = step["run"](lines, nodes)
        if result == lines:                       # this step changed nothing
            unchanged.append(name)
            continue
        path = out_dir / f"{stem}_rescued_{name}.nk"
        write_lines(path, result)
        made.append(path)

    # ---- crash-log analysis: pinpoint the culprit node(s) and target them ----
    suspects = []
    if crash_log and Path(crash_log).exists():
        log_text = Path(crash_log).read_text(encoding="utf-8", errors="replace")
        class_hits, name_hits, suspects = analyze_crash_log(log_text, nodes)
        with report_path.open("a", encoding="utf-8") as fh:
            fh.write("\n\nCrash-log analysis (%s):\n" % Path(crash_log).name)
            if name_hits:
                fh.write("  node names in the log: " + ", ".join(
                    "%s(%d)" % (k, v) for k, v in sorted(name_hits.items(), key=lambda x: -x[1])) + "\n")
            if class_hits:
                fh.write("  node classes in the log: " + ", ".join(
                    "%s(%d)" % (k, v) for k, v in sorted(class_hits.items(), key=lambda x: -x[1])) + "\n")
            if suspects:
                names = sorted({n.name or n.klass for n in suspects})
                fh.write("  SUSPECTS (disabled in rescued_from_crashlog.nk): %s\n" % ", ".join(names))
            else:
                fh.write("  No script node names/classes matched the log.\n")
        if suspects:
            write_lines(out_dir / f"{stem}_rescued_from_crashlog.nk",
                        disable_nodes(lines, nodes, suspects))
            made.append(out_dir / f"{stem}_rescued_from_crashlog.nk")

    autosaves = find_autosaves(script_path)
    if autosaves:                                 # append to the report
        with report_path.open("a", encoding="utf-8") as fh:
            fh.write("\n\nAutosave / backups found (may hold newer work):\n")
            for p in autosaves:
                fh.write("  %s\n" % p)

    pause_bat = make_pause_bat(out_dir, nuke_exe, script_path)

    print("PEP Script Doctor complete")
    print(f"Report: {report_path}")
    print(f"Original copy: {original_copy}")
    for p in made:
        print(f"Rescue: {p}")
    if unchanged:
        print(f"No change (nothing to fix): {', '.join(unchanged)}")
    if skipped:
        print(f"Skipped (toggled off): {', '.join(skipped)}")
    if autosaves:
        print(f"Autosave/backups found: {', '.join(str(p) for p in autosaves)}")
    if suspects:
        print("Crash-log suspects: %s" % ", ".join(sorted({n.name or n.klass for n in suspects})))
    print(f"Paused launcher: {pause_bat}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PEP Script Doctor for offline .nk rescue.")
    parser.add_argument("script", help="Path to the .nk script to inspect/rescue.")
    parser.add_argument("--out-dir", default="", help="Output folder. Defaults to <script>_doctor.")
    parser.add_argument(
        "--nuke-exe",
        default=r"C:\Program Files\Nuke14.0v2\Nuke14.0.exe",
        help="Nuke executable used in the generated paused launcher.",
    )
    parser.add_argument(
        "--skip", default="",
        help="Comma list of rescues to leave out: %s" % ", ".join(DEFAULT_RESCUES))
    parser.add_argument(
        "--only", default="",
        help="Comma list: generate ONLY these rescues (overrides --skip).")
    parser.add_argument(
        "--crash-log", default="",
        help="Optional crash log to pinpoint the culprit node(s).")
    args = parser.parse_args(argv)

    rescues = None
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        rescues = {k: (k in want) for k in DEFAULT_RESCUES}
    elif args.skip:
        drop = {s.strip() for s in args.skip.split(",") if s.strip()}
        rescues = {k: (k not in drop) for k in DEFAULT_RESCUES}

    script_path = Path(args.script).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else script_path.with_name(f"{script_path.stem}_doctor")
    return doctor_script(script_path, out_dir, args.nuke_exe, rescues,
                         crash_log=(args.crash_log or None))


if __name__ == "__main__":
    raise SystemExit(main())

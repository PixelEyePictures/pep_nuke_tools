# =====================================================================
# PEP Script Doctor - paste into Nuke's Script Editor and press Run.
# Rescues a .nk that loads-then-crashes. It only READS the scene as
# text (never opens it), so it is safe to run even if the scene crashes
# Nuke. Your original file is never modified.
#
# 1) Open Nuke (any empty session).
# 2) Window > Script Editor.  Paste ALL of this.
# 3) Set SCENE_PATH below to the crashing .nk.
# 4) Run (Ctrl+Enter).  Look in the printed <name>_doctor folder.
# =====================================================================

SCENE_PATH = r"PASTE_THE_CRASHING_NK_PATH_HERE.nk"   # <-- a .nk file, OR a folder to scan
OUTPUT_DIR = r""                                      # optional; blank = beside each scene
RECURSE    = True                                     # if SCENE_PATH is a folder, also scan subfolders

# Toggles - flip any to False to skip that rescue.
RESCUES = {
    "safe_mode":          True,   # START HERE: no Viewers + no callbacks + no postage + BlinkScript neutralized
    "no_blink":           True,   # neutralize BlinkScript (its kernel compiles on GUI open; a bad one crashes)
    "no_viewers":         True,   # remove all Viewers (Viewer-eval crash)
    "no_viewers_no_roto": True,   # also remove Roto/RotoPaint (corrupt roto)
    "disable_heavy":      True,   # disable heavy classes only
    "disable_all":        True,   # disable every node (whole graph inert)
    "no_callbacks":       True,   # strip per-node callbacks (load-crash)
    "no_plugins":         True,   # remove OFX/plugin nodes (missing plugin)
    "no_postage":         True,   # turn off postage-stamp thumbnails
    "bisect_first_half":  True,   # disable first half of the graph (bisect)
    "bisect_second_half": True,   # disable second half of the graph (bisect)
    "keep_one_viewer":    True,   # 2+ Viewers -> keep one disconnected, delete rest
    "disconnect_viewers": True,   # keep all Viewers but disconnect (all off / stereo)
    "strip_non_ascii":    True,   # remove stray non-ASCII bytes that break the parse
}

import os, re, shutil, sys, time
from dataclasses import dataclass
from pathlib import Path

NODE_START_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\.]*)\s*\{\s*$")
NAME_RE = re.compile(r"^\s*name\s+(.+?)\s*$")
FILE_RE = re.compile(r"^\s*file\s+(.+?)\s*$")
DISABLE_RE = re.compile(r"^\s*disable\s+(.+?)\s*$")
_CALLBACK_RE = re.compile(
    r"^\s*(knobChanged|onCreate|onDestroy|updateUI|autolabel|beforeRender|"
    r"afterRender|beforeFrameRender|afterFrameRender|onScriptLoad|"
    r"onScriptSave|onScriptClose)\b")


@dataclass
class NodeBlock:
    klass: str
    start: int
    end: int
    name: str = ""
    file_path: str = ""
    disabled: str = ""


def read_lines(path):
    return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)


def write_lines(path, lines):
    path.write_text("".join(lines), encoding="utf-8", errors="replace")


def block_end(lines, start):
    depth = 0
    for index in range(start, len(lines)):
        depth += lines[index].count("{")
        depth -= lines[index].count("}")
        if depth <= 0 and index > start:
            return index
    return start


def clean_value(value):
    value = value.strip()
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1]
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value.strip()


def parse_nodes(lines):
    nodes = []
    index = 0
    while index < len(lines):
        match = NODE_START_RE.match(lines[index].strip())
        if not match:
            index += 1
            continue
        end = block_end(lines, index)
        node = NodeBlock(klass=match.group(1), start=index, end=end)
        for line in lines[index:end + 1]:
            m = NAME_RE.match(line)
            if m:
                node.name = clean_value(m.group(1))
            m = FILE_RE.match(line)
            if m:
                node.file_path = clean_value(m.group(1))
            m = DISABLE_RE.match(line)
            if m:
                node.disabled = clean_value(m.group(1))
        nodes.append(node)
        index = end + 1
    return nodes


def class_counts(nodes):
    counts = {}
    for node in nodes:
        counts[node.klass] = counts.get(node.klass, 0) + 1
    return dict(sorted(counts.items(), key=lambda i: (-i[1], i[0].lower())))


def looks_missing(path_text):
    if not path_text or any(t in path_text for t in ("[", "%", "#")):
        return False
    expanded = os.path.expandvars(path_text)
    return (":" in expanded or expanded.startswith(("/", "\\"))) and not os.path.exists(expanded)


def make_report(script_path, lines, nodes):
    counts = class_counts(nodes)
    viewers = [n for n in nodes if n.klass == "Viewer"]
    reads = [n for n in nodes if n.klass in ("Read", "DeepRead", "ReadGeo", "Camera2")]
    missing = [n for n in reads if looks_missing(n.file_path)]
    suspicious = [n for n in nodes if n.klass.lower() in
                  ("rotopaint", "roto", "vectorblur", "defocus", "zdefocus", "scanlinerender")]
    out = ["PEP Script Doctor Report", "=" * 24, "",
           "script: %s" % script_path, "lines: %d" % len(lines), "nodes: %d" % len(nodes),
           "generated: %s" % time.strftime("%Y-%m-%d %H:%M:%S"), "", "Class counts:"]
    for klass, count in counts.items():
        out.append("  %s: %d" % (klass, count))
    out += ["", "Viewers: %d" % len(viewers)]
    for n in viewers:
        out.append("  line %d: %s" % (n.start + 1, n.name or n.klass))
    out += ["", "Read-like nodes:"]
    for n in reads[:80]:
        out.append("  line %d: %s | %s: %s" %
                   (n.start + 1, n.name or n.klass, "MISSING?" if n in missing else "path", n.file_path))
    if len(reads) > 80:
        out.append("  ... %d more" % (len(reads) - 80))
    out += ["", "Heavy/corruption suspects:"]
    for n in suspicious[:120]:
        out.append("  line %d: %s %s" % (n.start + 1, n.klass, n.name))
    if len(suspicious) > 120:
        out.append("  ... %d more" % (len(suspicious) - 120))
    out += ["", "Notes:",
            "  Original scripts are not edited.",
            "  Rescue copies are plain text .nk files.",
            "  Missing-path detection skips expressions, hashes, and printf patterns.",
            "",
            "If the script LOADS then CRASHES, try in this order:",
            "  1. open_paused_*.bat        -> opens with --pause (nothing evaluates).",
            "  2. rescued_no_viewers.nk    -> crash was a Viewer computing on open.",
            "  3. rescued_disable_all.nk   -> every node inert; re-enable to find culprit.",
            "  4. rescued_no_callbacks.nk  -> crash was a knobChanged/autolabel callback.",
            "  5. rescued_no_viewers_no_roto.nk / rescued_disable_heavy.nk -> corrupt roto / heavy node."]
    return "\n".join(out) + "\n"


def remove_classes(lines, nodes, classes):
    remove = set()
    for n in nodes:
        if n.klass in classes:
            remove.update(range(n.start, n.end + 1))
    return [line for i, line in enumerate(lines) if i not in remove] if remove else list(lines)


def disable_classes(lines, nodes, classes,
                    skip=frozenset({"Root", "Viewer", "Dot", "BackdropNode", "StickyNote"})):
    out = list(lines)
    for node in reversed(nodes):
        if node.klass in skip:
            continue
        if classes is not None and node.klass not in classes:
            continue
        block = out[node.start:node.end + 1]
        if any(DISABLE_RE.match(line) for line in block):
            for i in range(node.start, node.end + 1):
                if DISABLE_RE.match(out[i]):
                    out[i] = " disable true\n"
                    break
        else:
            out.insert(node.start + 1, " disable true\n")
    return out


def strip_callbacks(lines):
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _CALLBACK_RE.match(line):
            depth = line.count("{") - line.count("}")
            i += 1
            while i < len(lines) and depth > 0:
                depth += lines[i].count("{") - lines[i].count("}")
                i += 1
            continue
        out.append(line)
        i += 1
    return out


_DISABLE_SKIP = frozenset({"Root", "Viewer", "Dot", "BackdropNode", "StickyNote"})


def disable_nodes(lines, nodes, subset):
    keep = set(id(n) for n in subset)
    out = list(lines)
    for node in reversed(nodes):
        if id(node) not in keep or node.klass in _DISABLE_SKIP:
            continue
        block = out[node.start:node.end + 1]
        if any(DISABLE_RE.match(line) for line in block):
            for i in range(node.start, node.end + 1):
                if DISABLE_RE.match(out[i]):
                    out[i] = " disable true\n"
                    break
        else:
            out.insert(node.start + 1, " disable true\n")
    return out


def strip_postage_stamps(lines):
    return [re.sub(r"(\bpostage_stamp)\s+true", r"\1 false", line) for line in lines]


def keep_one_viewer(lines, nodes):
    viewers = [n for n in nodes if n.klass == "Viewer"]
    if len(viewers) <= 1:
        return list(lines)
    out = remove_classes(lines, nodes, {"Viewer"})
    out.extend(["Viewer {\n", " inputs 0\n", " name PEP_Viewer\n", "}\n"])
    return out


_INPUTS_RE = re.compile(r"^\s*inputs\s+\d+")


def disconnect_viewers(lines, nodes):
    viewers = [n for n in nodes if n.klass == "Viewer"]
    if not viewers:
        return list(lines)
    out = list(lines)
    for n in sorted(viewers, key=lambda v: -v.start):
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


def strip_non_ascii(lines):
    return [line.encode("ascii", "ignore").decode("ascii") for line in lines]


_CLASS_LINE_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_\.]*)(\s*\{\s*)$")


def reclass_nodes(lines, nodes, classes, new_class="NoOp"):
    # Change the class of matching nodes so they never construct/compile
    # (e.g. BlinkScript, whose kernel compiles the moment the GUI opens it).
    out = list(lines)
    for node in nodes:
        if node.klass not in classes:
            continue
        m = _CLASS_LINE_RE.match(out[node.start])
        if m and m.group(2) == node.klass:
            out[node.start] = "%s%s%s" % (m.group(1), new_class, m.group(3))
    return out


def safe_mode(lines, nodes):
    # The 'just open it' rescue: remove Viewers, strip callbacks, kill postage
    # thumbnails, and neutralize BlinkScript (GUI compiles its kernel on open).
    out = remove_classes(lines, nodes, {"Viewer"})
    out = strip_callbacks(out)
    out = strip_postage_stamps(out)
    out = reclass_nodes(out, parse_nodes(out), {"BlinkScript"}, "NoOp")
    return out


def find_autosaves(script_path):
    d = script_path.parent
    stem, name = script_path.stem, script_path.name
    cands = []
    for cand in (d / (name + "~"), d / (stem + ".autosave"),
                 d / (name + ".autosave"), d / (stem + "_autosave.nk")):
        if cand.exists() and cand not in cands:
            cands.append(cand)
    for p in sorted(d.glob("*.autosave")):
        if p not in cands:
            cands.append(p)
    return cands


def make_pause_bat(out_dir, nuke_exe, script_path):
    bat = out_dir / ("open_paused_%s.bat" % script_path.stem)
    bat.write_text('@echo off\n"%s" --pause "%s"\npause\n' % (nuke_exe, script_path), encoding="utf-8")
    return bat


def doctor_script(script_path, out_dir, nuke_exe):
    if not script_path.exists() or script_path.suffix.lower() != ".nk":
        print("Not a .nk file: %s" % script_path)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(script_path), str(out_dir / ("%s_original_copy.nk" % script_path.stem)))
    lines = read_lines(script_path)
    nodes = parse_nodes(lines)
    (out_dir / ("%s_doctor_report.txt" % script_path.stem)).write_text(
        make_report(script_path, lines, nodes), encoding="utf-8")
    heavy = {"Roto", "RotoPaint", "VectorBlur", "Defocus", "ZDefocus", "ScanlineRender"}
    producers = [
        ("safe_mode",          lambda: safe_mode(lines, nodes)),
        ("no_blink",           lambda: reclass_nodes(lines, nodes, {"BlinkScript"}, "NoOp")),
        ("no_viewers",         lambda: remove_classes(lines, nodes, {"Viewer"})),
        ("no_viewers_no_roto", lambda: remove_classes(lines, nodes, {"Viewer", "Roto", "RotoPaint"})),
        ("disable_heavy",      lambda: disable_classes(lines, nodes, heavy)),
        ("disable_all",        lambda: disable_classes(lines, nodes, None)),
        ("no_callbacks",       lambda: strip_callbacks(lines)),
        ("no_plugins",         lambda: remove_classes(lines, nodes, set(n.klass for n in nodes if "." in n.klass))),
        ("no_postage",         lambda: strip_postage_stamps(lines)),
        ("bisect_first_half",  lambda: disable_nodes(lines, nodes, nodes[:len(nodes) // 2])),
        ("bisect_second_half", lambda: disable_nodes(lines, nodes, nodes[len(nodes) // 2:])),
        ("keep_one_viewer",    lambda: keep_one_viewer(lines, nodes)),
        ("disconnect_viewers", lambda: disconnect_viewers(lines, nodes)),
        ("strip_non_ascii",    lambda: strip_non_ascii(lines)),
    ]
    skipped = []
    for name, producer in producers:
        if not RESCUES.get(name, True):
            skipped.append(name)
            continue
        result = producer()
        if result == lines:            # nothing to fix for this step
            continue
        write_lines(out_dir / ("%s_rescued_%s.nk" % (script_path.stem, name)), result)
    autos = find_autosaves(script_path)
    if autos:
        rp = out_dir / ("%s_doctor_report.txt" % script_path.stem)
        with rp.open("a", encoding="utf-8") as fh:
            fh.write("\n\nAutosave / backups found (may hold newer work):\n")
            for p in autos:
                fh.write("  %s\n" % p)
    make_pause_bat(out_dir, nuke_exe, script_path)
    print("PEP Script Doctor complete. Output folder:")
    print("  %s" % out_dir)
    if autos:
        print("Autosave/backups found: %s" % ", ".join(str(p) for p in autos))
    if skipped:
        print("Skipped (toggled off): %s" % ", ".join(skipped))
    print("Read the *_doctor_report.txt first, then try the rescued_*.nk files.")
    return 0


# --- run (accepts a single .nk file OR a folder of .nk files) ---
def _run_one(scene):
    out = Path(OUTPUT_DIR) if OUTPUT_DIR else scene.with_name(scene.stem + "_doctor")
    return doctor_script(scene, out, sys.executable)  # sys.executable = this Nuke


_target = Path(SCENE_PATH)
if _target.is_dir():
    _nks = sorted(_target.rglob("*.nk") if RECURSE else _target.glob("*.nk"))
    _nks = [p for p in _nks if "_doctor" not in p.parent.name]  # skip our own output
    print("Found %d .nk file(s) under %s" % (len(_nks), _target))
    for _i, _nk in enumerate(_nks, 1):
        print("\n[%d/%d] %s" % (_i, len(_nks), _nk))
        _run_one(_nk)
    print("\nBatch complete: %d file(s)." % len(_nks))
else:
    _run_one(_target)

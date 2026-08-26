"""PEP Script Doctor - GUI panel.

A thin Qt front-end over the offline rescue engine (pep_script_doctor). The
engine stays pure/standalone; this just gives it a panel with per-step toggles,
a file picker and the report output.

Pixel Eye Pictures.
"""

import os
import sys

import nuke

try:
    from PySide2 import QtWidgets, QtCore
except ImportError:  # Nuke 15+/PySide6 fallback
    from PySide6 import QtWidgets, QtCore

_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import pep_script_doctor as sd  # noqa: E402


_FOOTER = ('Pixel Eye Pictures&nbsp;&nbsp;|&nbsp;&nbsp;'
           '<a style="color:#7aa2f7" '
           'href="https://github.com/PixelEyePictures/pep_nuke_tools">GitHub</a>')

_VERSION = "1.1"
_RELEASED = "2026-08-26"

_HELP = """<h2 style="margin:0 0 6px">PEP Script Doctor</h2>
<p>Rescues a Nuke script that won't open or crashes on load. It <b>never opens
the scene</b> &mdash; it reads the <code>.nk</code> as text and writes safe,
openable copies. The original is never modified.</p>

<h3>How to use it</h3>
<ol>
<li>Set <b>Script</b> to the crashing <code>.nk</code> &mdash; browse, or drag it
onto the panel.</li>
<li>Leave the <b>rescue steps</b> on (all by default), or untick any you don't
want.</li>
<li>Press <b>Rescue</b>, then open the report and work down the recovery order.</li>
</ol>

<h3>Where the files are saved</h3>
<p>A folder named <code>&lt;script&gt;_doctor</code> is created <b>next to the
original file</b>. It contains:</p>
<ul>
<li>the <b>report</b> (<code>&hellip;_doctor_report.txt</code>) &mdash; read this
first;</li>
<li>an untouched <b>original copy</b>;</li>
<li>the <b>rescued</b> <code>.nk</code> copies (one per step);</li>
<li>a <b>paused launcher</b> (<code>open_paused_&hellip;.bat</code>);</li>
<li>any <b>autosave/backups</b> found next to the script.</li>
</ul>

<h3>Target specific node types</h3>
<p>Press <b>Analyze script</b> to list every node type and its count (heavy and
plugin types are pre‑ticked). Tick what you suspect, then <b>Disable ticked</b>
or <b>Remove ticked</b> for a surgical rescue.</p>

<h3>Match nodes (name or knob value)</h3>
<p>When you already know the offender, target it directly. In the
<b>Match nodes</b> box:</p>
<ul>
<li><b>Match</b> &mdash; the text to look for (e.g. a node name like
<code>Blur7</code>, or a label such as <code>heavy</code>). Tick <b>regex</b>
to treat it as a regular expression.</li>
<li><b>in</b> &mdash; <b>node name</b> matches the node's name; <b>any knob
value</b> scans every knob line inside the node (label, file path, etc.).</li>
<li><b>then</b> &mdash; what to do to the matches: <b>disable</b> (set
<code>disable&nbsp;true</code>), <b>disconnect</b> (cut its inputs), or
<b>remove</b> (delete the node).</li>
</ul>
<p>Press <b>Apply match</b>. It writes one copy,
<code>&hellip;_rescued_match_&lt;mode&gt;.nk</code>, into the same
<code>&lt;script&gt;_doctor</code> folder and lists every node it touched in the
output box. The original is untouched.</p>

<h3>Stray characters</h3>
<p>The <b>strip_non_ascii</b> step removes odd non‑ASCII bytes that can creep in
from copy/paste and break the parse. It only rewrites a copy if such bytes exist.</p>

<h3>Crash log (optional)</h3>
<p>Drop the crash log from the session that died onto the panel, or into the
<b>Crash log</b> field. Script Doctor scans it for the node it crashed on and
adds a targeted <code>rescued_from_crashlog.nk</code>. A dropped
<code>.nk</code> sets Script; any other file sets the Crash log.</p>

<h3>About</h3>
<p style="color:#8a8a8a; margin-top:2px">Version """ + _VERSION + """ &middot; """ + _RELEASED + """ &middot; Pixel Eye Pictures</p>"""


def _main_window():
    for w in QtWidgets.QApplication.topLevelWidgets():
        if "DockMainWindow" in w.metaObject().className():
            return w
    return None


class ScriptDoctorPanel(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ScriptDoctorPanel, self).__init__(parent or _main_window())
        self.setWindowTitle("PEP Script Doctor  v%s" % _VERSION)
        self.setMinimumWidth(560)
        lay = QtWidgets.QVBoxLayout(self)

        lay.addWidget(QtWidgets.QLabel(
            "<b>Rescue a .nk that crashes / won't open</b> "
            "&mdash; offline, never opens the scene."))

        # file row
        frow = QtWidgets.QHBoxLayout()
        self.script = QtWidgets.QLineEdit()
        self.script.setPlaceholderText("path to the crashing .nk (or a folder to batch)")
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        frow.addWidget(QtWidgets.QLabel("Script:")); frow.addWidget(self.script); frow.addWidget(browse)
        lay.addLayout(frow)

        # optional crash log -> pinpoints the culprit node(s)
        crow = QtWidgets.QHBoxLayout()
        self.crash = QtWidgets.QLineEdit()
        self.crash.setPlaceholderText("(optional) crash log from the last session - finds the culprit node")
        clog = QtWidgets.QPushButton("Browse…")
        clog.clicked.connect(self._browse_log)
        crow.addWidget(QtWidgets.QLabel("Crash log:")); crow.addWidget(self.crash); crow.addWidget(clog)
        lay.addLayout(crow)

        # steps
        box = QtWidgets.QGroupBox("Rescue steps")
        grid = QtWidgets.QGridLayout(box)
        self.checks = {}
        for i, (name, step) in enumerate(sd.RESCUE_STEPS.items()):
            cb = QtWidgets.QCheckBox(name)
            cb.setChecked(True)
            cb.setToolTip(step["desc"])
            grid.addWidget(cb, i // 2, i % 2)
            self.checks[name] = cb
        lay.addWidget(box)

        # analyse -> tick the actual node types in the script
        albox = QtWidgets.QGroupBox("Target node types (press Analyze)")
        alv = QtWidgets.QVBoxLayout(albox)
        arow = QtWidgets.QHBoxLayout()
        self.analyze_btn = QtWidgets.QPushButton("Analyze script")
        self.dis_sel_btn = QtWidgets.QPushButton("Disable ticked")
        self.rem_sel_btn = QtWidgets.QPushButton("Remove ticked")
        arow.addWidget(self.analyze_btn); arow.addStretch()
        arow.addWidget(self.dis_sel_btn); arow.addWidget(self.rem_sel_btn)
        alv.addLayout(arow)
        self.class_scroll = QtWidgets.QScrollArea()
        self.class_scroll.setWidgetResizable(True)
        self.class_scroll.setMinimumHeight(120)
        self.class_host = QtWidgets.QWidget()
        self.class_layout = QtWidgets.QGridLayout(self.class_host)
        self.class_scroll.setWidget(self.class_host)
        alv.addWidget(self.class_scroll)
        lay.addWidget(albox)
        self.class_checks = {}

        # match nodes by name / knob value -> disable / disconnect / remove
        mbox = QtWidgets.QGroupBox("Match nodes")
        mgrid = QtWidgets.QGridLayout(mbox)
        self.match_pattern = QtWidgets.QLineEdit()
        self.match_pattern.setPlaceholderText(
            "text to match, e.g. a node name, or a label like 'heavy'")
        self.match_where = QtWidgets.QComboBox()
        self.match_where.addItems(["node name", "any knob value"])
        self.match_where.setToolTip("Match against the node's name, or against "
                                    "any knob line in the node (label, etc.).")
        self.match_mode = QtWidgets.QComboBox()
        self.match_mode.addItems(["disable", "disconnect", "remove"])
        self.match_regex = QtWidgets.QCheckBox("regex")
        self.match_btn = QtWidgets.QPushButton("Apply match")
        mgrid.addWidget(QtWidgets.QLabel("Match"), 0, 0)
        mgrid.addWidget(self.match_pattern, 0, 1, 1, 3)
        mgrid.addWidget(QtWidgets.QLabel("in"), 1, 0)
        mgrid.addWidget(self.match_where, 1, 1)
        mgrid.addWidget(QtWidgets.QLabel("then"), 1, 2)
        mgrid.addWidget(self.match_mode, 1, 3)
        mgrid.addWidget(self.match_regex, 2, 1)
        mgrid.addWidget(self.match_btn, 2, 3)
        lay.addWidget(mbox)

        # buttons
        brow = QtWidgets.QHBoxLayout()
        self.help_btn = QtWidgets.QPushButton("Help")
        self.all_btn = QtWidgets.QPushButton("All")
        self.none_btn = QtWidgets.QPushButton("None")
        self.rescue_btn = QtWidgets.QPushButton("Rescue")
        self.rescue_btn.setDefault(True)
        brow.addWidget(self.help_btn); brow.addWidget(self.all_btn); brow.addWidget(self.none_btn)
        brow.addStretch(); brow.addWidget(self.rescue_btn)
        lay.addLayout(brow)

        # output
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(200)
        self.output.setPlaceholderText("The rescue report appears here.")
        lay.addWidget(self.output)

        foot = QtWidgets.QLabel(_FOOTER)
        foot.setOpenExternalLinks(True)
        foot.setAlignment(QtCore.Qt.AlignRight)
        lay.addWidget(foot)

        self.help_btn.clicked.connect(self._show_help)
        self.all_btn.clicked.connect(lambda: self._set_all(True))
        self.none_btn.clicked.connect(lambda: self._set_all(False))
        self.rescue_btn.clicked.connect(self._rescue)
        self.analyze_btn.clicked.connect(self._analyze)
        self.dis_sel_btn.clicked.connect(lambda: self._apply_selected("disable"))
        self.rem_sel_btn.clicked.connect(lambda: self._apply_selected("remove"))
        self.match_btn.clicked.connect(self._apply_match)
        self.setAcceptDrops(True)   # drop a .nk or a crash log anywhere on the panel

    def _set_all(self, state):
        for cb in self.checks.values():
            cb.setChecked(state)

    def _show_help(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("PEP Script Doctor - Help")
        dlg.resize(580, 560)
        v = QtWidgets.QVBoxLayout(dlg)
        view = QtWidgets.QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(_HELP)
        v.addWidget(view)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        v.addWidget(bb)
        dlg.exec_()

    def _browse(self):
        f = nuke.getFilename("Rescue which .nk?", "*.nk")
        if f:
            self.script.setText(f)

    def _browse_log(self):
        f = nuke.getFilename("Crash log", "*.log *.txt *.dmp *.*")
        if f:
            self.crash.setText(f)

    def _assign(self, path):
        """Route a dropped file: .nk -> Script, anything else -> Crash log."""
        if path.lower().endswith(".nk"):
            self.script.setText(path)
        elif path:
            self.crash.setText(path)

    _HEAVY_TYPES = {"Viewer", "Roto", "RotoPaint", "Defocus", "ZDefocus",
                    "VectorBlur", "ScanlineRender", "BlinkScript", "Convolve"}

    def _analyze(self):
        from pathlib import Path
        f = self.script.text().strip()
        if not f or not os.path.isfile(f):
            nuke.message("Pick a .nk file to analyze first.")
            return
        self._lines = sd.read_lines(Path(f))
        self._nodes = sd.parse_nodes(self._lines)
        counts = sd.class_counts(self._nodes)
        while self.class_layout.count():                 # clear old checks
            w = self.class_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.class_checks = {}
        for i, (cls, cnt) in enumerate(counts.items()):
            cb = QtWidgets.QCheckBox("%s  (%d)" % (cls, cnt))
            if cls in self._HEAVY_TYPES or "." in cls:   # heavy / OFX pre-ticked
                cb.setChecked(True)
                cb.setToolTip("Heavy or plugin node - a common crash cause.")
            self.class_layout.addWidget(cb, i // 2, i % 2)
            self.class_checks[cls] = cb
        self.output.setPlainText(
            "Analyzed %s\n%d nodes, %d node types. Heavy/plugin types are pre-"
            "ticked. Adjust, then 'Disable ticked' or 'Remove ticked'."
            % (Path(f).name, len(self._nodes), len(counts)))

    def _apply_selected(self, mode):
        from pathlib import Path
        if not getattr(self, "_nodes", None):
            nuke.message("Press Analyze first.")
            return
        sel = {c for c, cb in self.class_checks.items() if cb.isChecked()}
        if not sel:
            nuke.message("Tick at least one node type.")
            return
        script = Path(self.script.text().strip())
        out = script.with_name(script.stem + "_doctor")
        out.mkdir(parents=True, exist_ok=True)
        if mode == "disable":
            result = sd.disable_classes(self._lines, self._nodes, sel)
            path = out / (script.stem + "_rescued_selected_disable.nk")
        else:
            result = sd.remove_classes(self._lines, self._nodes, sel)
            path = out / (script.stem + "_rescued_selected_remove.nk")
        sd.write_lines(path, result)
        self.output.setPlainText(
            "%s %d node type(s):\n  %s\n\nWrote: %s"
            % ("Disabled" if mode == "disable" else "Removed",
               len(sel), ", ".join(sorted(sel)), path))

    def _apply_match(self):
        from pathlib import Path
        f = self.script.text().strip()
        if not f or not os.path.isfile(f):
            nuke.message("Pick a .nk file first.")
            return
        pat = self.match_pattern.text().strip()
        if not pat:
            nuke.message("Enter some text (a name, or a label like 'heavy') to match.")
            return
        lines = sd.read_lines(Path(f))
        nodes = sd.parse_nodes(lines)
        where = "name" if self.match_where.currentIndex() == 0 else "knob"
        mode = self.match_mode.currentText()
        result, matched = sd.match_nodes(
            lines, nodes, pat, where, mode, self.match_regex.isChecked())
        if not matched:
            self.output.setPlainText("No nodes matched '%s' in %s." % (pat, self.match_where.currentText()))
            return
        script = Path(f)
        out = script.with_name(script.stem + "_doctor")
        out.mkdir(parents=True, exist_ok=True)
        path = out / ("%s_rescued_match_%s.nk" % (script.stem, mode))
        sd.write_lines(path, result)
        shown = ", ".join(matched[:60]) + (" ..." if len(matched) > 60 else "")
        self.output.setPlainText(
            "%s %d node(s) matching '%s' in %s:\n  %s\n\nWrote: %s"
            % (mode.capitalize(), len(matched), pat,
               self.match_where.currentText(), shown, path))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            self._assign(url.toLocalFile())
        e.acceptProposedAction()

    def _rescue(self):
        from pathlib import Path
        f = self.script.text().strip()
        if not f or not os.path.exists(f):
            nuke.message("Pick a valid .nk (or folder).")
            return
        rescues = {n: cb.isChecked() for n, cb in self.checks.items()}
        target = Path(f)
        scenes = ([target] if target.is_file()
                  else sorted(target.rglob("*.nk")))
        log = []
        for scene in scenes:
            if "_doctor" in scene.parent.name:
                continue
            out = scene.with_name(scene.stem + "_doctor")
            try:
                sd.doctor_script(scene, out, nuke.EXE_PATH, rescues,
                                 crash_log=(self.crash.text().strip() or None))
                rep = out / ("%s_doctor_report.txt" % scene.stem)
                log.append("== %s ==\nOutput: %s\n" % (scene.name, out))
                if rep.exists():
                    log.append(rep.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                log.append("FAILED %s: %s" % (scene.name, e))
        self.output.setPlainText("\n".join(log) if log else "No .nk found.")


_panel = None


def launch():
    global _panel
    _panel = ScriptDoctorPanel()
    _panel.show()
    return _panel

"""PEP Rename & Relink.

Rename rendered files ON DISK from inside Nuke and relink the node -- fix a
typo, a wrong version, or give a shot a proper name -- for a single file, a
whole sequence, or a batch of selected Read/Write nodes.

Just type the new name in the 'New name' column (double-click), or use
Find/Replace to change many at once. For sequences the frame numbers are kept
automatically.

Rename-only (never deletes), previews before it touches disk, and refuses to
overwrite existing files.

Pixel Eye Pictures.
"""

import os
import re

import nuke

try:
    from PySide2 import QtWidgets, QtCore
except ImportError:  # Nuke 15+/PySide6 fallback
    from PySide6 import QtWidgets, QtCore


_TOKEN_RE = re.compile(r"#+|%0?\d*d|\$\{?F\d*\}?")


def _split(path):
    return os.path.dirname(path), os.path.basename(path)


def resolve_files(pattern):
    """Real files on disk for a node path (expands the frame token)."""
    pattern = pattern.replace("\\", "/")
    d, b = _split(pattern)
    if not d:
        return []
    if _TOKEN_RE.search(b):
        import glob as _glob
        return sorted(f.replace("\\", "/") for f in _glob.glob(os.path.join(d, _TOKEN_RE.sub("*", b))))
    return [pattern] if os.path.exists(pattern) else []


def _old_regex(old_base):
    m = _TOKEN_RE.search(old_base)
    if not m:
        return None
    return re.compile("^" + re.escape(old_base[:m.start()]) + r"(\d+)" +
                      re.escape(old_base[m.end():]) + "$")


def _new_for_frame(new_base, digits):
    m = _TOKEN_RE.search(new_base)
    if not m:
        return new_base
    return new_base[:m.start()] + digits + new_base[m.end():]


def _token_pad(new_base):
    """Digit width of the frame token in new_base (#### -> 4, %04d -> 4)."""
    m = _TOKEN_RE.search(new_base)
    if not m:
        return 0
    tok = m.group(0)
    if tok.startswith("#"):
        return len(tok)
    md = re.search(r"%0?(\d+)d", tok)
    return int(md.group(1)) if md else 0


def _new_for_num(new_base, num):
    """Substitute an integer frame number into new_base's token, zero-padded."""
    pad = _token_pad(new_base)
    return _new_for_frame(new_base, str(num).zfill(pad) if pad else str(num))


def plan_node(node, new_base, frames=None, renumber=None):
    """Plan renaming one node's files so the pattern basename becomes new_base.
    `frames`   : None = all; (first, last) = only that inclusive frame range.
    `renumber` : None = keep original frame numbers; (start, step) = renumber
                 the (in-scope) frames sequentially into new_base's token.
    Returns dict with files [(old,new)], issues."""
    if "file" not in node.knobs():
        return None
    pattern = node["file"].value().replace("\\", "/")
    if not pattern:
        return None
    d, old_base = _split(pattern)
    files = resolve_files(pattern)
    kind = "sequence" if _TOKEN_RE.search(old_base) else "single"
    rx = _old_regex(old_base) if kind == "sequence" else None
    pairs, issues, seen = [], [], set()
    in_scope = 0

    if kind == "sequence":
        # collect (orig_frame, file) in frame order for stable renumbering
        matched = []
        for f in files:
            mm = rx.match(_split(f)[1]) if rx else None
            if mm:
                matched.append((int(mm.group(1)), f))
        matched.sort()
        idx = 0
        for orig, f in matched:
            if frames is not None and not (frames[0] <= orig <= frames[1]):
                continue
            in_scope += 1
            if renumber is not None:
                nb = _new_for_num(new_base, renumber[0] + idx * renumber[1])
            else:
                nb = _new_for_num(new_base, orig)   # keep original frame number
            idx += 1
            fd = _split(f)[0]
            if not nb or nb == _split(f)[1]:
                continue
            nf = (fd + "/" + nb) if fd else nb
            if nf in seen or os.path.exists(nf):
                issues.append("exists: %s" % nb)
            seen.add(nf)
            pairs.append((f, nf))
    else:
        for f in files:
            fd, fb = _split(f)
            in_scope += 1
            nb = new_base
            if not nb or nb == fb:
                continue
            nf = (fd + "/" + nb) if fd else nb
            if nf in seen or os.path.exists(nf):
                issues.append("exists: %s" % nb)
            seen.add(nf)
            pairs.append((f, nf))

    if not files:
        issues.append("no files on disk")
    # Only safe to relink the node when the rename covers EVERY file on disk;
    # a partial-frame rename would split the sequence into two names.
    full = bool(files) and in_scope == len(files)
    if not full and pairs:
        issues.append("partial rename - node left pointing at the old name")
    new_pattern = (d + "/" + new_base) if d else new_base
    return {"node": node, "files": pairs, "new_pattern": new_pattern,
            "kind": kind, "count": len(files), "in_scope": in_scope,
            "full": full, "issues": issues, "old_base": old_base}


def apply_plan(plan):
    node = plan["node"]
    renamed, errors = 0, []
    for old, new in plan["files"]:
        if os.path.exists(new):
            errors.append("skip (exists): %s" % os.path.basename(new)); continue
        try:
            os.rename(old, new); renamed += 1
        except Exception as exc:  # noqa: BLE001
            errors.append("%s: %s" % (os.path.basename(old), exc))
    if renamed and plan.get("full") and plan["new_pattern"]:
        node["file"].setValue(plan["new_pattern"])
    return renamed, errors


# --------------------------------------------------------------------------- #
# Help / window helpers
# --------------------------------------------------------------------------- #
_FOOTER_HTML = ('<span style="color:#8a8a8a">Pixel Eye Pictures</span>'
                '&nbsp;&nbsp;|&nbsp;&nbsp;'
                '<a href="https://github.com/PixelEyePictures/pep_nuke_tools" '
                'style="color:#7aa2f7;text-decoration:none">GitHub</a>')


def _pep_footer():
    lbl = QtWidgets.QLabel(_FOOTER_HTML)
    lbl.setOpenExternalLinks(True)
    lbl.setAlignment(QtCore.Qt.AlignRight)
    return lbl


def _nuke_main_window():
    app = QtWidgets.QApplication.instance()
    if app is None or not hasattr(app, "topLevelWidgets"):
        return None
    for w in app.topLevelWidgets():
        if w.inherits("QMainWindow") and "DockMainWindow" in w.metaObject().className():
            return w
    for w in app.topLevelWidgets():
        if isinstance(w, QtWidgets.QMainWindow):
            return w
    return None


def _show_help(parent, title, html):
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title); dlg.setModal(True); dlg.resize(560, 440)
    lay = QtWidgets.QVBoxLayout(dlg)
    view = QtWidgets.QTextBrowser(); view.setOpenExternalLinks(True); view.setHtml(html)
    lay.addWidget(view)
    btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
    btn.rejected.connect(dlg.reject); lay.addWidget(btn)
    dlg.exec_()


_HELP_HTML = """
<h3>PEP Rename &amp; Relink</h3>
<p>Renames the actual rendered files <b>on disk</b> and relinks the node -- fix
a typo, a wrong version, or name a shot -- without leaving Nuke or re-rendering.</p>
<ol>
<li>Select the Read/Write node(s) and press <b>Refresh from selection</b>.</li>
<li><b>Type the new name</b> in the <i>New name</i> column (double-click a cell).
For a sequence, keep the frame token (<code>####</code>) -- frame numbers are
preserved.</li>
<li>Or use <b>Find / Replace</b> to change many names at once (updates the New
name column live). Toggle <b>Case sensitive</b>.</li>
<li>Check the <b>#files</b> and the New names, then <b>Apply</b>.</li>
</ol>
<p>Single file, whole sequence, and multiple nodes (batch) are all handled.</p>
<p><b>Safe:</b> rename-only (never deletes), never overwrites an existing file,
reports missing / locked frames.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class TagRenameDialog(QtWidgets.QWidget):
    NEW_COL = 4

    def __init__(self, parent=None):
        super(TagRenameDialog, self).__init__(parent)
        self.setWindowTitle("PEP Rename & Relink")
        self.setWindowFlags(QtCore.Qt.Window)
        self.resize(880, 460)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(
            "Type a new name in the New name column (double-click), or use a "
            "Name template / Find-Replace. Keep #### for sequences."))

        # name template (applies to all rows) -- like a batch renamer mask
        tp = QtWidgets.QHBoxLayout()
        self.template = QtWidgets.QLineEdit()
        self.template.setPlaceholderText("Name template for all, e.g. shot010_comp_v02.####.exr  (blank = per-row)")
        tp.addWidget(QtWidgets.QLabel("Name template:")); tp.addWidget(self.template, 1)
        lay.addLayout(tp)

        fr = QtWidgets.QHBoxLayout()
        self.find = QtWidgets.QLineEdit(); self.find.setPlaceholderText("Find in name (optional)...")
        self.repl = QtWidgets.QLineEdit(); self.repl.setPlaceholderText("Replace with...")
        self.cs = QtWidgets.QCheckBox("Case sensitive"); self.cs.setChecked(True)
        fr.addWidget(QtWidgets.QLabel("Find:")); fr.addWidget(self.find, 1)
        fr.addWidget(QtWidgets.QLabel("Replace:")); fr.addWidget(self.repl, 1)
        fr.addWidget(self.cs)
        lay.addLayout(fr)

        # frame scope (sequences)
        fs = QtWidgets.QHBoxLayout()
        fs.addWidget(QtWidgets.QLabel("Frames:"))
        self.scope = QtWidgets.QComboBox()
        self.scope.addItems(["All frames", "Frame range", "Current frame"])
        fs.addWidget(self.scope)
        self.first_sb = QtWidgets.QSpinBox(); self.first_sb.setRange(-1000000, 1000000)
        self.last_sb = QtWidgets.QSpinBox(); self.last_sb.setRange(-1000000, 1000000)
        self.first_sb.setValue(int(nuke.root()["first_frame"].value()))
        self.last_sb.setValue(int(nuke.root()["last_frame"].value()))
        fs.addWidget(QtWidgets.QLabel("first")); fs.addWidget(self.first_sb)
        fs.addWidget(QtWidgets.QLabel("last")); fs.addWidget(self.last_sb)
        fs.addSpacing(20)
        self.renumber = QtWidgets.QCheckBox("Renumber")
        self.start_sb = QtWidgets.QSpinBox(); self.start_sb.setRange(0, 10000000); self.start_sb.setValue(1001)
        self.step_sb = QtWidgets.QSpinBox(); self.step_sb.setRange(1, 1000); self.step_sb.setValue(1)
        fs.addWidget(self.renumber)
        fs.addWidget(QtWidgets.QLabel("start")); fs.addWidget(self.start_sb)
        fs.addWidget(QtWidgets.QLabel("step")); fs.addWidget(self.step_sb)
        fs.addStretch()
        lay.addLayout(fs)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Node", "Kind", "#files", "Old name", "New name (double-click to edit)"])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        h.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        lay.addWidget(self.table)

        self.status = QtWidgets.QLabel("")
        lay.addWidget(self.status)

        btns = QtWidgets.QHBoxLayout()
        self.help_btn = QtWidgets.QPushButton("Help")
        self.refresh_btn = QtWidgets.QPushButton("Refresh from selection")
        self.apply_btn = QtWidgets.QPushButton("Apply (rename on disk)")
        self.close_btn = QtWidgets.QPushButton("Close")
        btns.addWidget(self.help_btn); btns.addWidget(self.refresh_btn)
        btns.addStretch(); btns.addWidget(self.apply_btn); btns.addWidget(self.close_btn)
        lay.addLayout(btns)
        lay.addWidget(_pep_footer())

        self.help_btn.clicked.connect(
            lambda: _show_help(self, "PEP Rename & Relink - Help", _HELP_HTML))
        self.refresh_btn.clicked.connect(self.refresh)
        self.apply_btn.clicked.connect(self.apply)
        self.close_btn.clicked.connect(self.close)
        self.template.textChanged.connect(self._apply_template)
        self.find.textChanged.connect(self._apply_find)
        self.repl.textChanged.connect(self._apply_find)
        self.cs.stateChanged.connect(self._apply_find)
        self.table.itemChanged.connect(self._on_edit)
        self.scope.currentIndexChanged.connect(self._sync_scope)
        self.first_sb.valueChanged.connect(self._update_status)
        self.last_sb.valueChanged.connect(self._update_status)
        self.renumber.stateChanged.connect(self._sync_scope)
        self.start_sb.valueChanged.connect(self._update_status)
        self.step_sb.valueChanged.connect(self._update_status)

        self._rows = []       # [(node, old_base)]
        self._loading = False
        self._sync_scope()
        self.refresh()

    def _selected_io_nodes(self):
        return [n for n in nuke.selectedNodes()
                if n.Class() in ("Read", "Write") and "file" in n.knobs()]

    def refresh(self):
        self._loading = True
        self.table.setRowCount(0)
        self._rows = []
        for n in self._selected_io_nodes():
            pattern = n["file"].value().replace("\\", "/")
            _, old_base = _split(pattern)
            files = resolve_files(pattern)
            kind = "sequence" if _TOKEN_RE.search(old_base) else "single"
            row = self.table.rowCount(); self.table.insertRow(row)
            for c, txt in enumerate((n.name(), kind, str(len(files)), old_base)):
                it = QtWidgets.QTableWidgetItem(txt)
                it.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.table.setItem(row, c, it)
            new_it = QtWidgets.QTableWidgetItem(old_base)   # editable
            self.table.setItem(row, self.NEW_COL, new_it)
            self._rows.append((n, old_base))
        self._loading = False
        self._apply_find()

    def _apply_template(self, *args):
        t = self.template.text()
        if t:
            self._loading = True
            for r in range(len(self._rows)):
                self.table.item(r, self.NEW_COL).setText(t)
            self._loading = False
            self._update_status()
        else:
            self._apply_find()

    def _apply_find(self, *args):
        if self.template.text():          # template overrides find/replace
            return
        find = self.find.text()
        if find:
            self._loading = True
            for r, (_, old_base) in enumerate(self._rows):
                if self.cs.isChecked():
                    nb = old_base.replace(find, self.repl.text())
                else:
                    nb = re.sub(re.escape(find), lambda m: self.repl.text(),
                                old_base, flags=re.IGNORECASE)
                self.table.item(r, self.NEW_COL).setText(nb)
            self._loading = False
        self._update_status()

    def _on_edit(self, item):
        if not self._loading and item.column() == self.NEW_COL:
            self._update_status()

    def _sync_scope(self, *args):
        rng = self.scope.currentIndex() == 1
        self.first_sb.setEnabled(rng)
        self.last_sb.setEnabled(rng)
        rn = self.renumber.isChecked()
        self.start_sb.setEnabled(rn)
        self.step_sb.setEnabled(rn)
        self._update_status()

    def _renumber_arg(self):
        if self.renumber.isChecked():
            return (self.start_sb.value(), self.step_sb.value())
        return None

    def _frames_arg(self):
        idx = self.scope.currentIndex()
        if idx == 1:
            return (self.first_sb.value(), self.last_sb.value())
        if idx == 2:
            f = int(nuke.frame())
            return (f, f)
        return None

    def _plans(self):
        frames = self._frames_arg()
        renumber = self._renumber_arg()
        plans = []
        for r, (node, _) in enumerate(self._rows):
            new_base = self.table.item(r, self.NEW_COL).text().strip()
            if new_base:
                p = plan_node(node, new_base, frames, renumber)
                if p:
                    plans.append(p)
        return plans

    def _update_status(self):
        if not self._rows:
            self.status.setText("Select Read/Write node(s), then Refresh.")
            return
        plans = self._plans()
        files = sum(p["count"] for p in plans)
        ren = sum(len(p["files"]) for p in plans)
        iss = sum(len(p["issues"]) for p in plans)
        self.status.setText("%d node(s), %d file(s) on disk, %d will be renamed%s."
                            % (len(self._rows), files, ren,
                               ", %d issue(s)" % iss if iss else ""))

    def apply(self):
        plans = [p for p in self._plans() if p["files"]]
        if not plans:
            nuke.message("Nothing to rename (edit a New name or use Find/Replace).")
            return
        n_files = sum(len(p["files"]) for p in plans)
        if not nuke.ask("Rename %d file(s) on disk across %d node(s)?\n"
                        "This cannot be undone from Nuke." % (n_files, len(plans))):
            return
        renamed, errs = 0, []
        for p in plans:
            r, e = apply_plan(p); renamed += r; errs.extend(e)
        msg = "Renamed %d file(s)." % renamed
        if errs:
            msg += "\n\nSkipped/errors:\n" + "\n".join(errs[:20])
        nuke.message(msg)
        self.refresh()


_dialog = None


def launch_tagrename():
    global _dialog
    try:
        if _dialog is not None:
            _dialog.close(); _dialog.deleteLater()
    except Exception:
        pass
    _dialog = TagRenameDialog(parent=_nuke_main_window())
    _dialog.show(); _dialog.raise_(); _dialog.activateWindow()
    return _dialog


# backwards-compatible alias
launch_rename = launch_tagrename


if __name__ == "__main__":
    launch_tagrename()

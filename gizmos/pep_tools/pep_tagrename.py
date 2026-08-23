"""PEP TagRename.

Rename rendered files ON DISK from inside Nuke -- fix a typo, a missing dot,
a wrong version -- for a single file, a whole sequence, or a batch of selected
Read/Write nodes, then relink the node(s) so nothing re-renders.

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


# Frame tokens Nuke uses in file paths: ####, %04d/%d, $F, $F4, ${F}
_TOKEN_RE = re.compile(r"#+|%0?\d*d|\$\{?F\d*\}?")


def _split(path):
    return os.path.dirname(path), os.path.basename(path)


def resolve_files(path):
    """Return the real files on disk for a node path (expands frame token).
    Returns [] if nothing is found."""
    path = path.replace("\\", "/")
    d, b = _split(path)
    if not d:
        return []
    if _TOKEN_RE.search(b):
        glob_b = _TOKEN_RE.sub("*", b)
        import glob as _glob
        return sorted(f.replace("\\", "/") for f in _glob.glob(os.path.join(d, glob_b)))
    return [path] if os.path.exists(path) else []


def new_basename(basename, find, repl, case_sensitive):
    if not find:
        return basename
    if case_sensitive:
        return basename.replace(find, repl)
    return re.sub(re.escape(find), lambda m: repl, basename, flags=re.IGNORECASE)


def plan_node(node, find, repl, case_sensitive):
    """Build a rename plan for one node.
    Returns dict: node, files [(old,new)], new_pattern, kind, issues[]."""
    if "file" not in node.knobs():
        return None
    pattern = node["file"].value().replace("\\", "/")
    if not pattern:
        return None
    files = resolve_files(pattern)
    d, b = _split(pattern)
    kind = "sequence" if _TOKEN_RE.search(b) else "single"
    pairs = []
    issues = []
    seen_targets = set()
    for f in files:
        fd, fb = _split(f)
        nb = new_basename(fb, find, repl, case_sensitive)
        nf = (fd + "/" + nb) if fd else nb
        if nb == fb:
            continue
        if nf in seen_targets or os.path.exists(nf):
            issues.append("target exists: %s" % nb)
        seen_targets.add(nf)
        pairs.append((f, nf))
    if not files:
        issues.append("no files found on disk")
    new_pattern = (d + "/" + new_basename(b, find, repl, case_sensitive)) if d else \
        new_basename(b, find, repl, case_sensitive)
    return {"node": node, "files": pairs, "new_pattern": new_pattern,
            "kind": kind, "count": len(files), "issues": issues}


def apply_plan(plan):
    """Rename files on disk and relink the node. Returns (renamed, errors[])."""
    node = plan["node"]
    renamed = 0
    errors = []
    for old, new in plan["files"]:
        if os.path.exists(new):
            errors.append("skip (exists): %s" % os.path.basename(new))
            continue
        try:
            os.rename(old, new)
            renamed += 1
        except Exception as exc:  # noqa: BLE001
            errors.append("%s: %s" % (os.path.basename(old), exc))
    if renamed and plan["new_pattern"]:
        node["file"].setValue(plan["new_pattern"])
    return renamed, errors


# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #
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
<h3>PEP TagRename</h3>
<p>Renames the actual rendered files <b>on disk</b> and relinks the node, so you
can fix a typo / missing dot / wrong version without leaving Nuke or
re-rendering.</p>
<ol>
<li>Select the Read/Write node(s). Single file, whole sequence, and multiple
nodes (batch) are all handled automatically.</li>
<li>Type <b>Find</b> / <b>Replace</b> (applied to the file <i>name</i>, folders
untouched). Toggle <b>Case sensitive</b> if needed.</li>
<li>Check the <b>Old &rarr; New</b> preview and file counts.</li>
<li><b>Apply</b> renames every matching file on disk and updates the node path.</li>
</ol>
<p><b>Safe:</b> rename-only (never deletes), never overwrites an existing file,
and reports missing / locked frames instead of failing silently.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
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


class TagRenameDialog(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(TagRenameDialog, self).__init__(parent)
        self.setWindowTitle("PEP TagRename")
        self.setWindowFlags(QtCore.Qt.Window)
        self.resize(860, 460)
        lay = QtWidgets.QVBoxLayout(self)

        lay.addWidget(QtWidgets.QLabel(
            "Rename rendered files on disk for the selected Read/Write node(s), "
            "then relink. Single / sequence / batch."))

        # find/replace row
        fr = QtWidgets.QHBoxLayout()
        self.find = QtWidgets.QLineEdit(); self.find.setPlaceholderText("Find in file name...")
        self.repl = QtWidgets.QLineEdit(); self.repl.setPlaceholderText("Replace with...")
        self.cs = QtWidgets.QCheckBox("Case sensitive"); self.cs.setChecked(True)
        fr.addWidget(QtWidgets.QLabel("Find:")); fr.addWidget(self.find, 1)
        fr.addWidget(QtWidgets.QLabel("Replace:")); fr.addWidget(self.repl, 1)
        fr.addWidget(self.cs)
        lay.addLayout(fr)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Node", "Kind", "#files", "Old name", "New name"])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        h.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        lay.addWidget(self.table)

        self.status = QtWidgets.QLabel("")
        lay.addWidget(self.status)

        btns = QtWidgets.QHBoxLayout()
        self.help_btn = QtWidgets.QPushButton("Help")
        self.refresh_btn = QtWidgets.QPushButton("Refresh from selection")
        self.preview_btn = QtWidgets.QPushButton("Preview")
        self.apply_btn = QtWidgets.QPushButton("Apply (rename on disk)")
        self.close_btn = QtWidgets.QPushButton("Close")
        btns.addWidget(self.help_btn); btns.addWidget(self.refresh_btn)
        btns.addStretch()
        btns.addWidget(self.preview_btn); btns.addWidget(self.apply_btn)
        btns.addWidget(self.close_btn)
        lay.addLayout(btns)

        self.help_btn.clicked.connect(
            lambda: _show_help(self, "PEP TagRename - Help", _HELP_HTML))
        self.refresh_btn.clicked.connect(self.refresh)
        self.preview_btn.clicked.connect(self.preview)
        self.apply_btn.clicked.connect(self.apply)
        self.close_btn.clicked.connect(self.close)
        self.find.textChanged.connect(self.preview)
        self.repl.textChanged.connect(self.preview)
        self.cs.stateChanged.connect(self.preview)

        self._nodes = []
        self.refresh()

    def _selected_io_nodes(self):
        out = []
        for n in nuke.selectedNodes():
            if n.Class() in ("Read", "Write") and "file" in n.knobs():
                out.append(n)
        return out

    def refresh(self):
        self._nodes = self._selected_io_nodes()
        self.preview()

    def _plans(self):
        plans = []
        for n in self._nodes:
            p = plan_node(n, self.find.text(), self.repl.text(), self.cs.isChecked())
            if p:
                plans.append(p)
        return plans

    def preview(self, *args):
        self.table.setRowCount(0)
        if not self._nodes:
            self.status.setText("Select Read/Write node(s), then Refresh.")
            return
        total_files = total_ren = 0
        issues = 0
        for p in self._plans():
            total_files += p["count"]
            total_ren += len(p["files"])
            issues += len(p["issues"])
            old_ex = os.path.basename(p["files"][0][0]) if p["files"] else \
                (os.path.basename(p["node"]["file"].value()) if p["count"] else "-")
            new_ex = os.path.basename(p["files"][0][1]) if p["files"] else \
                ("(no change)" if not p["issues"] else "; ".join(p["issues"]))
            row = self.table.rowCount(); self.table.insertRow(row)
            for c, txt in enumerate((p["node"].name(), p["kind"], str(p["count"]),
                                     old_ex, new_ex)):
                it = QtWidgets.QTableWidgetItem(txt)
                it.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                self.table.setItem(row, c, it)
        self.status.setText(
            "%d node(s), %d file(s) on disk, %d file(s) will be renamed%s."
            % (len(self._nodes), total_files, total_ren,
               ", %d issue(s)" % issues if issues else ""))

    def apply(self):
        plans = [p for p in self._plans() if p["files"]]
        if not plans:
            nuke.message("Nothing to rename (check Find/Replace and selection).")
            return
        n_files = sum(len(p["files"]) for p in plans)
        if not nuke.ask("Rename %d file(s) on disk across %d node(s)?\n"
                        "This cannot be undone from Nuke." % (n_files, len(plans))):
            return
        renamed = 0
        all_errs = []
        for p in plans:
            r, errs = apply_plan(p)
            renamed += r
            all_errs.extend(errs)
        msg = "Renamed %d file(s)." % renamed
        if all_errs:
            msg += "\n\nSkipped/errors:\n" + "\n".join(all_errs[:20])
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


if __name__ == "__main__":
    launch_tagrename()

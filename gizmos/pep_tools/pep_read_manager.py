"""PEP Read Node Manager.

List every Read / ReadGeo in the script with its status and file path, then
batch enable/disable them or relink their paths (find/replace, or hand-edit
each path) -- without opening every node.

Pixel Eye Pictures.
"""

import nuke

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:  # Nuke 15+/PySide6 fallback
    from PySide6 import QtWidgets, QtCore, QtGui


def _show_help(parent, title, html):
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.resize(560, 440)
    lay = QtWidgets.QVBoxLayout(dlg)
    view = QtWidgets.QTextBrowser()
    view.setOpenExternalLinks(True)
    view.setHtml(html)
    lay.addWidget(view)
    btn = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
    btn.rejected.connect(dlg.reject)
    btn.accepted.connect(dlg.accept)
    lay.addWidget(btn)
    dlg.exec_()


_HELP_HTML = """
<h3>PEP Read Node Manager</h3>
<p>Manage every Read / ReadGeo in the script from one window &mdash; no need to
open each node.</p>
<ul>
<li><b>Scan for</b> Read (Images) / ReadGeo (3D); <b>Refresh List</b> to rescan.</li>
<li><b>Tick</b> rows (or <b>Check All</b> / <b>Uncheck All</b>) to batch-select.</li>
<li><b>Disable / Enable Selected</b> &mdash; mute or wake the ticked nodes
(e.g. kill heavy reference clips before a render).</li>
<li><b>Search/Replace Paths</b> &mdash; relink the ticked nodes.</li>
</ul>
<h4>Search / Replace</h4>
<p>The dialog lists each ticked node's current path (selectable / copyable).</p>
<ul>
<li><b>Selected path &rarr; Find / Replace</b> &mdash; drop a row's path into a
field (no copying from Nuke needed).</li>
<li><b>Preview affects</b> All rows, or Selected (highlighted) rows only.</li>
<li><b>Preview Find/Replace</b> updates the New paths; <b>Reset</b> reverts.</li>
<li>Or <b>double-click a path cell</b> and edit it by hand (per node).</li>
<li><b>Apply to nodes</b> writes only the changed paths.</li>
</ul>
<p><b>Typical use &mdash; move a script to a new shot:</b> Check All &rarr;
Search/Replace &rarr; Find <i>sh045</i> Replace <i>sh052</i> (repeat for the
version) &rarr; Apply. Every pass repoints at once, no re-importing.</p>
<p>Tip: match a distinctive token (<i>sh045</i>, <i>_v003</i>), not a bare
number, so you don't hit dates / resolutions / frame padding.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


def _nuke_main_window():
    """Return Nuke's main window so dialogs parent to it (and don't get lost
    behind Nuke or trap it behind an always-on-top window)."""
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


class ReadNodeManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ReadNodeManager, self).__init__(parent)

        self.setWindowTitle("Read Node Manager")
        self.resize(600, 400)
        # A proper top-level tool window parented to Nuke: it raises above the
        # main window but does NOT force stays-on-top (which would trap modal
        # sub-dialogs behind it and lock Nuke).
        self.setWindowFlags(QtCore.Qt.Window)

        # --- UI Layouts ---
        self.main_layout = QtWidgets.QVBoxLayout()
        self.filter_layout = QtWidgets.QHBoxLayout()
        self.button_layout = QtWidgets.QHBoxLayout()

        self.setLayout(self.main_layout)

        # --- Filter Section ---
        self.filter_label = QtWidgets.QLabel("Scan for:")
        self.chk_read = QtWidgets.QCheckBox("Read (Images)")
        self.chk_read.setChecked(True)
        self.chk_read.stateChanged.connect(self.populate_list)

        self.chk_geo = QtWidgets.QCheckBox("ReadGeo (3D)")
        self.chk_geo.setChecked(True)
        self.chk_geo.stateChanged.connect(self.populate_list)

        self.btn_refresh = QtWidgets.QPushButton("Refresh List")
        self.btn_refresh.clicked.connect(self.populate_list)
        self.btn_help = QtWidgets.QPushButton("Help")
        self.btn_help.clicked.connect(
            lambda: _show_help(self, "Read Node Manager - Help", _HELP_HTML))

        self.filter_layout.addWidget(self.filter_label)
        self.filter_layout.addWidget(self.chk_read)
        self.filter_layout.addWidget(self.chk_geo)
        self.filter_layout.addStretch()
        self.filter_layout.addWidget(self.btn_help)
        self.filter_layout.addWidget(self.btn_refresh)

        # --- The Table List ---
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Node Name", "Status", "File Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        # --- Action Buttons ---
        self.btn_check_all = QtWidgets.QPushButton("Check All")
        self.btn_check_all.clicked.connect(lambda: self._set_all_checks(True))
        self.btn_uncheck_all = QtWidgets.QPushButton("Uncheck All")
        self.btn_uncheck_all.clicked.connect(lambda: self._set_all_checks(False))

        self.btn_disable = QtWidgets.QPushButton("Disable Selected")
        self.btn_disable.setStyleSheet("color: #ffcccc;")
        self.btn_disable.clicked.connect(lambda: self.set_disable_status(True))

        self.btn_enable = QtWidgets.QPushButton("Enable Selected")
        self.btn_enable.setStyleSheet("color: #ccffcc;")
        self.btn_enable.clicked.connect(lambda: self.set_disable_status(False))

        self.btn_replace = QtWidgets.QPushButton("Search/Replace Paths")
        self.btn_replace.clicked.connect(self.search_replace_path)

        self.button_layout.addWidget(self.btn_check_all)
        self.button_layout.addWidget(self.btn_uncheck_all)
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.btn_disable)
        self.button_layout.addWidget(self.btn_enable)
        self.button_layout.addWidget(self.btn_replace)

        # --- Add to Main Layout ---
        self.main_layout.addLayout(self.filter_layout)
        self.main_layout.addWidget(self.table)
        self.main_layout.addLayout(self.button_layout)

        # --- Initial Population ---
        self.populate_list()

    # ---------------------------------------------------------------- helpers
    def _set_all_checks(self, checked):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def get_target_nodes(self):
        """Returns a list of nodes strictly based on checkboxes."""
        target_types = []
        if self.chk_read.isChecked():
            target_types.append("Read")
        if self.chk_geo.isChecked():
            target_types.append("ReadGeo2")

        nodes = []
        for t in target_types:
            nodes.extend(nuke.allNodes(t))
        return nodes

    def populate_list(self):
        """Finds nodes and adds them to the table."""
        self.table.setRowCount(0)
        nodes = self.get_target_nodes()

        for node in nodes:
            row = self.table.rowCount()
            self.table.insertRow(row)

            item_name = QtWidgets.QTableWidgetItem(node.name())
            item_name.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            item_name.setCheckState(QtCore.Qt.Unchecked)

            is_disabled = node['disable'].value()
            status_text = "DISABLED" if is_disabled else "Active"
            item_status = QtWidgets.QTableWidgetItem(status_text)
            item_status.setForeground(QtGui.QColor("red") if is_disabled else QtGui.QColor("green"))

            file_path = node['file'].value() if 'file' in node.knobs() else "N/A"
            item_path = QtWidgets.QTableWidgetItem(file_path)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_status)
            self.table.setItem(row, 2, item_path)

    def get_checked_nodes(self):
        """Returns the Nuke node objects for rows that are checked."""
        selected_nodes = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == QtCore.Qt.Checked:
                node_name = item.text()
                if nuke.exists(node_name):
                    selected_nodes.append(nuke.toNode(node_name))
        return selected_nodes

    def set_disable_status(self, disable_bool):
        """Disables or Enables the checked nodes."""
        nodes = self.get_checked_nodes()
        if not nodes:
            nuke.message("No nodes ticked in the list.")
            return

        for node in nodes:
            if 'disable' in node.knobs():
                node['disable'].setValue(disable_bool)

        self.populate_list()

    def search_replace_path(self):
        """Path editor for the ticked nodes. Shows each current path (copyable),
        lets you grab a path into Find, preview Find/Replace, or hand-edit each
        path individually, then apply. Self-contained so nothing needs to be
        copied from Nuke while it is open."""
        nodes = self.get_checked_nodes()
        if not nodes:
            nuke.message("No nodes ticked in the list.")
            return
        nodes = [n for n in nodes if 'file' in n.knobs()]
        if not nodes:
            nuke.message("None of the ticked nodes have a 'file' path.")
            return

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Batch Path Edit / Replace")
        dlg.setModal(True)
        dlg.resize(820, 460)
        lay = QtWidgets.QVBoxLayout(dlg)
        lay.addWidget(QtWidgets.QLabel(
            "Edit a path cell directly, or use Find/Replace below. "
            "Paths here are selectable / copyable."))

        tbl = QtWidgets.QTableWidget(len(nodes), 2)
        tbl.setHorizontalHeaderLabels(["Node", "File Path (editable)"])
        tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        tbl.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        originals = []
        for r, n in enumerate(nodes):
            p = n['file'].value()
            originals.append(p)
            it_name = QtWidgets.QTableWidgetItem(n.name())
            it_name.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            it_path = QtWidgets.QTableWidgetItem(p)   # editable by default
            tbl.setItem(r, 0, it_name)
            tbl.setItem(r, 1, it_path)
        lay.addWidget(tbl)

        # --- Find / Replace row ---
        fr = QtWidgets.QHBoxLayout()
        find_edit = QtWidgets.QLineEdit(); find_edit.setPlaceholderText("Find...")
        repl_edit = QtWidgets.QLineEdit(); repl_edit.setPlaceholderText("Replace with...")
        fr.addWidget(QtWidgets.QLabel("Find:")); fr.addWidget(find_edit, 1)
        fr.addWidget(QtWidgets.QLabel("Replace:")); fr.addWidget(repl_edit, 1)
        lay.addLayout(fr)

        fr2 = QtWidgets.QHBoxLayout()
        use_btn = QtWidgets.QPushButton("Selected path -> Find")
        use_repl_btn = QtWidgets.QPushButton("Selected path -> Replace")
        fr2.addWidget(use_btn); fr2.addWidget(use_repl_btn); fr2.addStretch()
        lay.addLayout(fr2)

        fr3 = QtWidgets.QHBoxLayout()
        fr3.addWidget(QtWidgets.QLabel("Preview affects:"))
        scope = QtWidgets.QComboBox()
        scope.addItems(["All rows", "Selected (highlighted) rows only"])
        fr3.addWidget(scope)
        preview_btn = QtWidgets.QPushButton("Preview Find/Replace")
        reset_btn = QtWidgets.QPushButton("Reset")
        fr3.addWidget(preview_btn); fr3.addStretch(); fr3.addWidget(reset_btn)
        lay.addLayout(fr3)

        def use_selected():
            row = tbl.currentRow()
            if row < 0:
                nuke.message("Select a row first."); return
            find_edit.setText(tbl.item(row, 1).text())

        def use_selected_replace():
            row = tbl.currentRow()
            if row < 0:
                nuke.message("Select a row first."); return
            repl_edit.setText(tbl.item(row, 1).text())

        def preview():
            s = find_edit.text()
            if not s:
                nuke.message("Enter a 'Find' string."); return
            rp = repl_edit.text()
            if scope.currentIndex() == 1:                       # selected rows only
                rows = sorted({i.row() for i in tbl.selectedIndexes()})
                if not rows:
                    nuke.message("No rows highlighted. Highlight rows, or switch "
                                 "'Preview affects' to All rows."); return
            else:
                rows = range(tbl.rowCount())
            changed = 0
            for r in rows:
                cur = tbl.item(r, 1).text()
                if s in cur:
                    tbl.item(r, 1).setText(cur.replace(s, rp)); changed += 1
            if changed == 0:
                nuke.message("No paths contained the Find text (in scope).")

        def reset():
            for r in range(tbl.rowCount()):
                tbl.item(r, 1).setText(originals[r])

        use_btn.clicked.connect(use_selected)
        use_repl_btn.clicked.connect(use_selected_replace)
        preview_btn.clicked.connect(preview)
        reset_btn.clicked.connect(reset)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Apply | QtWidgets.QDialogButtonBox.Cancel)
        btns.button(QtWidgets.QDialogButtonBox.Apply).setText("Apply to nodes")
        btns.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        count = 0
        for r, n in enumerate(nodes):
            new_path = tbl.item(r, 1).text()
            if new_path != originals[r]:
                n['file'].setValue(new_path)
                count += 1

        nuke.message("Updated paths in %d node(s)." % count)
        self.populate_list()


# Keep a module-level reference so the panel is not garbage-collected.
read_manager_panel = None


def launch_read_manager():
    """Entry point used by menu.py. Reuses/raises any existing instance."""
    global read_manager_panel
    try:
        if read_manager_panel is not None:
            read_manager_panel.close()
            read_manager_panel.deleteLater()
    except Exception:
        pass

    read_manager_panel = ReadNodeManager(parent=_nuke_main_window())
    read_manager_panel.show()
    read_manager_panel.raise_()
    read_manager_panel.activateWindow()
    return read_manager_panel


if __name__ == "__main__":
    launch_read_manager()

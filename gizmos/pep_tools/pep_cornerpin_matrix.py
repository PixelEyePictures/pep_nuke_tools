"""PEP CornerPin -> Matrix.

Convert a CornerPin2D's corner data into a 3x3 planar homography, embedded in
Nuke's 4x4 "extra matrix" convention, and push it into the transform-matrix
knob of a Roto / RotoPaint / CornerPin2D. Lets you
drive a paint or warp with tracked corner-pin data.

Matches a live CornerPin in Nuke 14 (forward map out = M * src, row-major,
translate in cell 3, perspective in cells 12/13; sub-pixel match).

Pixel Eye Pictures.
"""

import nuke

try:
    from PySide2 import QtWidgets
except ImportError:  # Nuke 15+/PySide6 fallback
    from PySide6 import QtWidgets


# class -> list of (label, knob_name) matrix targets.
# Only nodes that actually apply a global 4x4: CornerPin (image warp) and
# Roto/RotoPaint (shape transform).
TARGET_KNOBS = {
    "Roto": [("Extra matrix", "transform_matrix")],
    "RotoPaint": [("Extra matrix", "transform_matrix")],
    "CornerPin2D": [("Extra matrix", "transform_matrix")],
}


# --------------------------------------------------------------------------- #
# Math
# --------------------------------------------------------------------------- #
def solve_homography(src, dst):
    """4 correspondences src->dst -> 9 floats (row-major 3x3, h8 == 1)."""
    A = []
    b = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    n = 8
    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            raise ValueError("Degenerate corners (collinear or coincident).")
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [val / pv for val in M[c]]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] for i in range(n)] + [1.0]


def invert3(h):
    a, b, c, d, e, f, g, hh, i = h
    det = a * (e * i - f * hh) - b * (d * i - f * g) + c * (d * hh - e * g)
    if abs(det) < 1e-18:
        raise ValueError("Matrix not invertible.")
    inv = [
        (e * i - f * hh), (c * hh - b * i), (b * f - c * e),
        (f * g - d * i), (a * i - c * g), (c * d - a * f),
        (d * hh - e * g), (b * g - a * hh), (a * e - b * d),
    ]
    inv = [v / det for v in inv]
    # normalise so h8 == 1
    return [v / inv[8] for v in inv]


def embed_4x4(h):
    """3x3 homography -> Nuke 4x4 extra-matrix (row-major, forward out=M*src)."""
    a, b, c, d, e, f, g, hh, i = h
    return [a, b, 0, c,
            d, e, 0, f,
            0, 0, 1, 0,
            g, hh, 0, i]


# --------------------------------------------------------------------------- #
# CornerPin reading
# --------------------------------------------------------------------------- #
def _pt(knob, frame):
    return (knob.valueAt(frame, 0), knob.valueAt(frame, 1))


def corners_at(cp, frame):
    frm = [_pt(cp["from%d" % i], frame) for i in (1, 2, 3, 4)]
    to = [_pt(cp["to%d" % i], frame) for i in (1, 2, 3, 4)]
    return frm, to


def _transpose16(m):
    return [m[c * 4 + r] for r in range(4) for c in range(4)]


def matrix_at(cp, frame, invert, transpose=False):
    """16 floats for the extra-matrix knob, at the given frame.

    Reproduces the CornerPin's own direction (honours its 'invert' knob),
    then applies the user's extra invert on top. Optional transpose for
    matrices coming from apps that use the opposite row/column convention.
    """
    frm, to = corners_at(cp, frame)
    h = solve_homography(frm, to)          # from -> to (forward pin)
    cp_invert = bool(cp["invert"].value()) if "invert" in cp.knobs() else False
    if cp_invert != bool(invert):          # XOR
        h = invert3(h)
    m = embed_4x4(h)
    return _transpose16(m) if transpose else m


def _kbool(node, name):
    return bool(node[name].value()) if name in node.knobs() else False


def live_cell(node, i):
    """Evaluated per-frame by the v2 gizmo's live 'matrix' knob expressions."""
    return matrix_at(node, nuke.frame(), False, _kbool(node, "transpose"))[i]


def _is_animated(cp):
    for i in (1, 2, 3, 4):
        for side in ("from%d", "to%d"):
            k = cp[side % i]
            if k.isAnimated() or k.hasExpression():
                return True
    return False


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #
# The 4x4 lives under an "extra matrix" tab that must be ENABLED for the matrix
# to actually transform anything on Roto / RotoPaint.
_ENABLE_KNOB = {
    "transform_matrix": "extra matrix",
}


def _enable_extra_matrix(target, knob_name):
    enable = _ENABLE_KNOB.get(knob_name)
    if enable and enable in target.knobs():
        try:
            target[enable].setValue(True)
        except Exception:  # noqa: BLE001
            pass


ROTO_CLASSES = {"Roto", "RotoPaint"}


def _frange(first, last):
    if first is None:
        first = int(nuke.root()["first_frame"].value())
    if last is None:
        last = int(nuke.root()["last_frame"].value())
    return int(first), int(last)


def _apply_roto(cp, target, invert, bake, first, last, transpose=False):
    """Drive the roto root-layer extra matrix directly (renders reliably and
    moves the shapes forward, so the controller follows the pin)."""
    _enable_extra_matrix(target, "transform_matrix")
    xf = target["curves"].rootLayer.getTransform()
    if bake:
        f0, f1 = _frange(first, last)
        frames = list(range(f0, f1 + 1))
    else:
        frames = [nuke.frame()]
    for row in range(4):
        for col in range(4):
            cv = xf.getExtraMatrixAnimCurve(row, col)
            cv.removeAllKeys()
            if bake:
                for f in frames:
                    m = matrix_at(cp, f, invert, transpose)
                    cv.addKey(float(f), float(m[row * 4 + col]))
            else:
                m = matrix_at(cp, frames[0], invert, transpose)
                cv.constantValue = float(m[row * 4 + col])
            xf.setExtraMatrixAnimCurve(row, col, cv)
    # keep the node knob in sync for display
    m0 = matrix_at(cp, frames[0], invert, transpose)
    for i in range(16):
        target["transform_matrix"].setValue(float(m0[i]), i)
    return len(frames)


def apply_matrix(cp, target, knob_name, invert=False, bake=False,
                 first=None, last=None, transpose=False):
    if target.Class() in ROTO_CLASSES:
        return _apply_roto(cp, target, invert, bake, first, last, transpose)

    knob = target[knob_name]
    _enable_extra_matrix(target, knob_name)
    if not bake:
        m = matrix_at(cp, nuke.frame(), invert, transpose)
        for i in range(16):
            knob.setValue(float(m[i]), i)
        return 1

    first, last = _frange(first, last)
    knob.clearAnimated()
    for i in range(16):
        knob.setAnimated(i)
    count = 0
    for f in range(first, last + 1):
        m = matrix_at(cp, f, invert, transpose)
        for i in range(16):
            knob.setValueAt(float(m[i]), f, i)
        count += 1
    return count


def matrix_string(cp, invert=False, transpose=False):
    m = matrix_at(cp, nuke.frame(), invert, transpose)
    rows = ["\t".join("%.10g" % m[r * 4 + c] for c in range(4)) for r in range(4)]
    return "\n".join(rows)


# --------------------------------------------------------------------------- #
# Gizmo button helpers (called from the .gizmo PyScript knobs)
# --------------------------------------------------------------------------- #
def gizmo_solve(node=None, bake=False):
    """Fill the gizmo's 'matrix_str' knob from its own corner knobs."""
    node = node or nuke.thisNode()
    node["matrix_str"].setValue(
        matrix_string(node, invert=False, transpose=_kbool(node, "transpose")))


def gizmo_copy(node=None):
    node = node or nuke.thisNode()
    txt = node["matrix_str"].value() or matrix_string(
        node, invert=False, transpose=_kbool(node, "transpose"))
    try:
        from PySide2 import QtWidgets as _Q
    except ImportError:
        from PySide6 import QtWidgets as _Q
    app = _Q.QApplication.instance()
    if app is None or not hasattr(app, "clipboard"):   # headless / terminal
        nuke.tprint("Matrix:\n%s" % txt)
        return
    app.clipboard().setText(txt)
    nuke.message("Matrix (current frame) copied to clipboard.")


def _sibling_target(node):
    """First selected node at the gizmo's own graph level (not the gizmo)."""
    fn = node.fullName()
    parent = nuke.toNode(fn.rsplit(".", 1)[0]) if "." in fn else nuke.root()
    for n in nuke.allNodes(group=parent):
        if n["selected"].value() and n.fullName() != fn:
            return n
    return None


def _resolve_target(node):
    """Target = the node named in the 'target' knob if set, else the selected
    sibling. Returns None (after a message) if it can't be found."""
    if "target" in node.knobs():
        name = node["target"].value().strip()
        if name:
            t = nuke.toNode(name)
            if t is None:
                nuke.message("Target node '%s' not found." % name)
            return t
    t = _sibling_target(node)
    if t is None:
        nuke.message("Set a target node (type/pick its name in 'target node', "
                     "or select it alongside this gizmo).")
    return t


def gizmo_set_target(node=None):
    """Fill the 'target node' field from the currently selected node."""
    node = node or nuke.thisNode()
    t = _sibling_target(node)
    if t is None:
        nuke.message("Select the target node (together with this gizmo) first.")
        return
    node["target"].setValue(t.name())


def _target_knob_name(node, target):
    """Which matrix knob to write on the target."""
    knobs = TARGET_KNOBS.get(target.Class())
    return knobs[0][1] if knobs else None


def gizmo_paste(node=None):
    """Write the gizmo's matrix into the target node."""
    node = node or nuke.thisNode()
    target = _resolve_target(node)
    if target is None:
        return
    knob_name = _target_knob_name(node, target)
    if not knob_name:
        nuke.message("No matrix knob known for %s." % target.Class())
        return
    bake = _kbool(node, "bake")
    n = apply_matrix(node, target, knob_name, invert=False, bake=bake,
                     first=int(node["first"].value()),
                     last=int(node["last"].value()),
                     transpose=_kbool(node, "transpose"))
    nuke.message("Wrote matrix into %s.%s (%d frame%s)." % (
        target.name(), knob_name, n, "" if n == 1 else "s"))


def gizmo_link(node=None):
    """Live expression-link: point the target's matrix knob at this gizmo's
    live 'matrix' knob, so it updates as the corners change (no baking).

    Only for CornerPin2D targets. Roto/RotoPaint
    shape transforms are curve-based and cannot be expression-linked -- use
    Paste (bake) for those.
    """
    node = node or nuke.thisNode()
    target = _resolve_target(node)
    if target is None:
        return
    if target.Class() in ROTO_CLASSES:
        nuke.message("Live link is not supported for Roto/RotoPaint (their "
                     "shape transform is curve-based). Use Paste (bake) "
                     "instead.")
        return
    knob_name = _target_knob_name(node, target)
    if not knob_name:
        nuke.message("No matrix knob known for %s." % target.Class())
        return
    _enable_extra_matrix(target, knob_name)
    src = node.fullName()
    for i in range(16):
        target[knob_name].setExpression("%s.matrix.%d" % (src, i), i)
    nuke.message("Live-linked %s.%s to %s.matrix (updates with the corners)."
                 % (target.name(), knob_name, node.name()))


# --------------------------------------------------------------------------- #
# Help
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


def _show_help(parent, title, html):
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setModal(True)
    dlg.resize(560, 460)
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
<h3>PEP CornerPin to Matrix</h3>
<p>Turns a CornerPin's corners into a 4x4 matrix and drives another node with
it, so a Roto / RotoPaint follows the pin (or a CornerPin reproduces it).</p>
<ol>
<li>Get corner-pin data (track it, or animate a CornerPin's <i>to</i> corners).</li>
<li>Set / link the <b>to</b> and <b>from</b> corners on this panel (or the gizmo).</li>
<li>Pick the <b>target</b> node (Roto / RotoPaint / CornerPin2D).</li>
<li>Press <b>Apply</b>. Tick <b>bake</b> + set first/last for tracked (animated)
pins.</li>
</ol>
<p><b>invert</b> &mdash; flip the direction if the target moves the wrong way.<br>
<b>Copy matrix to clipboard</b> &mdash; grab the 4x4 for use elsewhere.</p>
<p><b>Targets:</b> CornerPin2D (image warp) and Roto/RotoPaint (shape follow).
GridWarp/SplineWarp are freeform and can't take a global matrix.</p>
<p>The <b>v2 gizmo</b> adds a live expression-link, a target-node field, and a
transpose (swap rows/columns) toggle.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class CornerPinMatrixDialog(QtWidgets.QDialog):
    def __init__(self, cp, target):
        super(CornerPinMatrixDialog, self).__init__()
        self.cp = cp
        self.target = target
        self.setWindowTitle("PEP CornerPin -> Matrix")
        self.setMinimumWidth(430)
        lay = QtWidgets.QVBoxLayout(self)

        src_txt = "Source CornerPin:  %s" % cp.name()
        tgt_txt = ("Target:  %s  (%s)" % (target.name(), target.Class())
                   if target else "Target:  <none selected> -> new CornerPin2D")
        lay.addWidget(QtWidgets.QLabel(src_txt))
        lay.addWidget(QtWidgets.QLabel(tgt_txt))

        form = QtWidgets.QFormLayout()
        self.knob_combo = QtWidgets.QComboBox()
        cls = target.Class() if target else "CornerPin2D"
        for label, kn in TARGET_KNOBS.get(cls, [("Extra matrix", "transform_matrix")]):
            self.knob_combo.addItem("%s  (%s)" % (label, kn), kn)
        form.addRow("Write into:", self.knob_combo)

        self.invert_cb = QtWidgets.QCheckBox("Invert (to -> from)")
        form.addRow("", self.invert_cb)

        self.bake_cb = QtWidgets.QCheckBox("Bake animation over range")
        self.bake_cb.setChecked(_is_animated(cp))
        form.addRow("", self.bake_cb)

        rng = QtWidgets.QHBoxLayout()
        self.first_sb = QtWidgets.QSpinBox(); self.first_sb.setRange(-1000000, 1000000)
        self.last_sb = QtWidgets.QSpinBox(); self.last_sb.setRange(-1000000, 1000000)
        self.first_sb.setValue(int(nuke.root()["first_frame"].value()))
        self.last_sb.setValue(int(nuke.root()["last_frame"].value()))
        rng.addWidget(QtWidgets.QLabel("first")); rng.addWidget(self.first_sb)
        rng.addWidget(QtWidgets.QLabel("last")); rng.addWidget(self.last_sb)
        form.addRow("Range:", rng)
        lay.addLayout(form)

        btns = QtWidgets.QHBoxLayout()
        self.help_btn = QtWidgets.QPushButton("Help")
        self.copy_btn = QtWidgets.QPushButton("Copy matrix to clipboard")
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        btns.addWidget(self.help_btn)
        btns.addWidget(self.copy_btn)
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.apply_btn)
        lay.addLayout(btns)
        lay.addWidget(_pep_footer())

        self.bake_cb.toggled.connect(self._sync_range)
        self.help_btn.clicked.connect(
            lambda: _show_help(self, "CornerPin to Matrix - Help", _HELP_HTML))
        self.copy_btn.clicked.connect(self._copy)
        self.apply_btn.clicked.connect(self._apply)
        self.cancel_btn.clicked.connect(self.reject)
        self._sync_range(self.bake_cb.isChecked())

    def _sync_range(self, on):
        self.first_sb.setEnabled(on)
        self.last_sb.setEnabled(on)

    def _copy(self):
        try:
            QtWidgets.QApplication.clipboard().setText(
                matrix_string(self.cp, self.invert_cb.isChecked()))
            nuke.message("Matrix (current frame) copied to clipboard.")
        except Exception as exc:  # noqa: BLE001
            nuke.message("Copy failed:\n%s" % exc)

    def _apply(self):
        target = self.target
        try:
            if target is None:
                # No target: drop a standalone CornerPin2D that carries the
                # matrix in its extra-matrix knob (identity corners).
                target = nuke.nodes.CornerPin2D(
                    name="CornerPinMatrix", xpos=self.cp.xpos(),
                    ypos=self.cp.ypos() + 80)
                knob_name = "transform_matrix"
            else:
                knob_name = self.knob_combo.currentData()
            n = apply_matrix(self.cp, target, knob_name,
                             invert=self.invert_cb.isChecked(),
                             bake=self.bake_cb.isChecked(),
                             first=self.first_sb.value(),
                             last=self.last_sb.value())
            self.accept()
            nuke.message("Applied matrix into %s.%s\n(%d frame%s)" % (
                target.name(), knob_name, n, "" if n == 1 else "s"))
        except Exception as exc:  # noqa: BLE001
            nuke.message("CornerPin -> Matrix failed:\n%s" % exc)


def _pick_nodes():
    sel = nuke.selectedNodes()
    cp = next((n for n in sel if n.Class() == "CornerPin2D"), None)
    target = next((n for n in sel if n is not cp), None)
    return cp, target


_dialog = None


def launch_cornerpin_matrix():
    """Menu entry point."""
    global _dialog
    cp, target = _pick_nodes()
    if cp is None:
        nuke.message("Select a CornerPin2D (and optionally a target "
                     "Roto / RotoPaint / CornerPin2D).")
        return
    try:
        _dialog = CornerPinMatrixDialog(cp, target)
        _dialog.show()
    except Exception as exc:  # noqa: BLE001
        nuke.message("CornerPin -> Matrix failed to launch:\n%s" % exc)

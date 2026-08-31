"""PEP CornerPin 3D Points.

Turn four 3D points (geometry vertices, or Axis / locator nodes) into an
animated CornerPin by projecting them through a camera. Feed it geometry and a
camera, pick four points, and it traces them to 2D corners over the shot - ready
to export as a CornerPin2D or push straight into PEP CornerPin to Matrix.

Inputs:  1 = geometry (for vertex picking),  2 = camera.

Pixel Eye Pictures.
"""

import math

import nuke

try:
    import nukescripts
except ImportError:  # pragma: no cover
    nukescripts = None

POINT_SOURCES = ["Selected vertices", "Selected Axis nodes"]


# --------------------------------------------------------------------------- #
# camera projection (standard Nuke camera matrix)
# --------------------------------------------------------------------------- #
def _camera_matrix(cam, frame):
    """World -> screen (pixels) projection matrix for `cam` at `frame`."""
    wm = nuke.math.Matrix4()
    for i in range(16):
        wm[i] = cam["matrix"].getValueAt(frame, i)
    wm.transpose()
    cam_transform = wm.inverse()

    m = nuke.math.Matrix4()
    m.makeIdentity()
    m.rotateZ(math.radians(float(cam["winroll"].getValueAt(frame, 0))))
    m.scale(1.0 / float(cam["win_scale"].getValueAt(frame, 0)),
            1.0 / float(cam["win_scale"].getValueAt(frame, 1)), 1.0)
    m.translate(-float(cam["win_translate"].getValueAt(frame, 0)),
                -float(cam["win_translate"].getValueAt(frame, 1)), 0.0)

    focal = float(cam["focal"].getValueAt(frame))
    haperture = float(cam["haperture"].getValueAt(frame))
    near = float(cam["near"].getValueAt(frame))
    far = float(cam["far"].getValueAt(frame))
    persp = int(cam["projection_mode"].getValueAt(frame)) == 0
    p = nuke.math.Matrix4()
    p.projection(focal / haperture, near, far, persp)

    fmt = nuke.root()["format"].value()
    image_aspect = float(fmt.height()) / float(fmt.width())
    t = nuke.math.Matrix4()
    t.makeIdentity()
    t.translate(1.0, 1.0 - (1.0 - image_aspect / float(fmt.pixelAspect())), 0.0)

    x_scale = float(fmt.width()) / 2.0
    y_scale = x_scale * fmt.pixelAspect()
    s = nuke.math.Matrix4()
    s.makeIdentity()
    s.scale(x_scale, y_scale, 1.0)
    return s * t * p * m * cam_transform


def _project(cam, xyz, frame):
    mtx = _camera_matrix(cam, frame)
    v = mtx * nuke.math.Vector4(float(xyz[0]), float(xyz[1]), float(xyz[2]), 1.0)
    if v.w == 0:
        return (0.0, 0.0)
    return (v.x / v.w, v.y / v.w)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _geo(node):
    return node.input(0)


def _camera(node):
    return node.input(1)


def _status(node, text):
    if "status" in node.knobs():
        node["status"].setValue(text)
    nuke.tprint("[PEP CornerPin3D] %s" % text)


def _selected_points():
    if nukescripts is None or not hasattr(nukescripts, "snap3d"):
        return []
    try:
        return [tuple(p) for p in nukescripts.snap3d.selectedPoints()]
    except Exception:  # noqa: BLE001
        return []


def _range(node):
    first = int(node["firstFrame"].value())
    last = int(node["lastFrame"].value())
    if first == 0 and last == 0:
        first, last = int(nuke.root().firstFrame()), int(nuke.root().lastFrame())
        node["firstFrame"].setValue(first)
        node["lastFrame"].setValue(last)
    if last < first:
        first, last = last, first
    return first, last


# --------------------------------------------------------------------------- #
# actions (button callbacks)
# --------------------------------------------------------------------------- #
def get_points(node=None):
    """Set the four source points from the current selection (vertices or Axis)."""
    node = node or nuke.thisNode()
    src = node["pointSource"].value()

    if src == "Selected Axis nodes":
        axes = [n for n in nuke.selectedNodes() if "translate" in n.knobs()]
        if len(axes) < 4:
            nuke.message("Select 4 Axis / locator nodes in the graph first "
                         "(found %d)." % len(axes))
            return
        for i in range(4):
            node["xPt%d" % (i + 1)].setValue(list(axes[i]["translate"].getValue()))
        _status(node, "Got 4 points from Axis nodes. Now press Generate.")
        node["generated"].setValue(False)
        return

    if _geo(node) is None:
        nuke.message("Connect geometry to input 1 to pick vertices.")
        return
    pts = _selected_points()
    if len(pts) < 4:
        nuke.message("Select at least 4 vertices on the geometry in the 3D "
                     "viewer, then press Get Points (got %d)." % len(pts))
        return
    for i in range(4):
        node["xPt%d" % (i + 1)].setValue(list(pts[i]))
    _status(node, "Got 4 vertices. Now press Generate.")
    node["generated"].setValue(False)


def _order(corners):
    """Order 4 (x,y) corners as bottom-left, bottom-right, top-right, top-left."""
    cx = sum(c[0] for c in corners) / 4.0
    cy = sum(c[1] for c in corners) / 4.0
    bl = min(corners, key=lambda c: (c[0] - cx) + (c[1] - cy))
    tr = max(corners, key=lambda c: (c[0] - cx) + (c[1] - cy))
    rest = [c for c in corners if c not in (bl, tr)]
    if len(rest) == 2:
        br, tl = (rest[0], rest[1]) if rest[0][0] > rest[1][0] else (rest[1], rest[0])
    else:  # degenerate - fall back to angle sort
        ordered = sorted(corners, key=lambda c: math.atan2(c[1] - cy, c[0] - cx))
        return ordered
    return [bl, br, tr, tl]


def generate(node=None):
    """Project the four source points through the camera across the range."""
    node = node or nuke.thisNode()
    cam = _camera(node)
    if cam is None or "focal" not in cam.knobs():
        nuke.message("Connect a Camera to input 2.")
        return
    first, last = _range(node)
    pts = [node["xPt%d" % (i + 1)].getValue() for i in range(4)]
    if all(p == [0, 0, 0] for p in pts):
        nuke.message("Set the four points first (Get Points).")
        return

    for i in range(4):
        node["to%d" % (i + 1)].clearAnimated()
        node["to%d" % (i + 1)].setAnimated()

    task = nuke.ProgressTask("PEP CornerPin 3D") if nuke.GUI else None
    total = max(1, last - first)
    ct = nuke.nodes.CurveTool()          # forces the camera to evaluate per frame
    try:
        for f in range(first, last + 1):
            nuke.execute(ct, f, f)        # so cam['matrix'] is valid at frame f
            projected = [_project(cam, p, f) for p in pts]
            ordered = _order(projected)
            for i in range(4):
                node["to%d" % (i + 1)].setValueAt(ordered[i][0], f, 0)
                node["to%d" % (i + 1)].setValueAt(ordered[i][1], f, 1)
            if task:
                if task.isCancelled():
                    break
                task.setProgress(int((f - first) * 100 / total))
    finally:
        del task
        nuke.delete(ct)

    node["generated"].setValue(True)
    if int(node["refFrame"].value()) == 0:
        node["refFrame"].setValue(first)
    _status(node, "Generated corners for %d-%d. Export or Send to Matrix." % (first, last))


def _make_cornerpin(node):
    cp = nuke.nodes.CornerPin2D()
    cp.setInput(0, None)
    for i in range(1, 5):
        cp["to%d" % i].copyAnimations(node["to%d" % i].animations())
    return cp


def export_cornerpin(node=None):
    """Create a CornerPin2D driven by the generated corners."""
    node = node or nuke.thisNode()
    if not node["generated"].value():
        nuke.message("Press Generate first.")
        return
    cp = _make_cornerpin(node)
    cp.setXYpos(node.xpos() + 120, node.ypos() + 40)
    _status(node, "Exported CornerPin2D '%s'." % cp.name())


def send_to_matrix(node=None):
    """Export the CornerPin and hand it to PEP CornerPin to Matrix (if present)."""
    node = node or nuke.thisNode()
    if not node["generated"].value():
        nuke.message("Press Generate first.")
        return
    cp = _make_cornerpin(node)
    cp.setXYpos(node.xpos() + 120, node.ypos() + 40)
    try:
        import pep_cornerpin_matrix  # noqa: F401
        cp.setSelected(True)
        _status(node, "Exported '%s'. Select your Roto/paint too, then run "
                      "PEP Tools > CornerPin to Matrix (Paste)." % cp.name())
        nuke.message("Created CornerPin2D '%s'.\n\nNow select it together with "
                     "your Roto / RotoPaint and use PEP Tools > CornerPin to "
                     "Matrix to bake the follow." % cp.name())
    except Exception:  # noqa: BLE001
        _status(node, "Exported CornerPin2D '%s' (Matrix tool not found)." % cp.name())


# --------------------------------------------------------------------------- #
# vertex averaging + per-point tracing
# --------------------------------------------------------------------------- #
def _avg_selected():
    """Average all currently-selected vertices into one (x,y,z), or None."""
    pts = _selected_points()
    if not pts:
        return None
    n = float(len(pts))
    return (sum(p[0] for p in pts) / n,
            sum(p[1] for p in pts) / n,
            sum(p[2] for p in pts) / n)


def set_point(node=None, idx=1, animated=False):
    """Set source point `idx` from the selected vertices (their average).

    animated=False sets a single value at the current frame; animated=True
    traces the average across the range (for a moving vertex cluster)."""
    node = node or nuke.thisNode()
    idx = int(idx)
    if _geo(node) is None:
        nuke.message("Connect geometry to input 1 to pick vertices.")
        return
    knob = node["xPt%d" % idx]

    if not animated:
        avg = _avg_selected()
        if avg is None:
            nuke.message("Select one or more vertices on the geometry first.")
            return
        knob.clearAnimated()
        knob.setValue(list(avg))
        _status(node, "Set pt %d from %d vertices. Set the rest, then Generate."
                % (idx, len(_selected_points())))
        node["generated"].setValue(False)
        return

    first, last = _range(node)
    knob.clearAnimated()
    knob.setAnimated()
    ct = nuke.nodes.CurveTool()
    task = nuke.ProgressTask("Trace pt %d" % idx) if nuke.GUI else None
    total = max(1, last - first)
    try:
        for f in range(first, last + 1):
            nuke.execute(ct, f, f)          # refresh the 3D eval at this frame
            avg = _avg_selected()
            if avg:
                for a in range(3):
                    knob.setValueAt(avg[a], f, a)
            if task:
                if task.isCancelled():
                    break
                task.setProgress(int((f - first) * 100 / total))
    finally:
        del task
        nuke.delete(ct)
    _status(node, "Traced pt %d over %d-%d. Set the rest, then Generate."
            % (idx, first, last))
    node["generated"].setValue(False)


# --------------------------------------------------------------------------- #
# Transform export (match-move from the projected corners)
#
# Nuke 14's Tracker4 `tracks` is a Table_Knob that cannot be populated from
# Python (setValueAt silently no-ops - the old Py2 tracker scripts are dead on
# Nuke 14). A Transform gives the same match-move and plugs in directly, so we
# bake the corner motion into standard, reliable animation knobs instead.
# --------------------------------------------------------------------------- #
def export_transform(node=None, two=False):
    """Bake the projected corner(s) into a Transform. One corner -> translate
    (match-move); two corners -> translate + rotate + scale, relative to the
    reference frame."""
    node = node or nuke.thisNode()
    if not node["generated"].value():
        nuke.message("Press Generate first.")
        return
    first, last = _range(node)
    ref = int(node["refFrame"].value()) or first
    a = int(node["trkA"].getValue()) + 1                    # 0 -> to1
    b = int(node["trkB"].getValue()) + 1

    ax0, ay0 = node["to%d" % a].valueAt(ref)
    if two:
        bx0, by0 = node["to%d" % b].valueAt(ref)
        vx0, vy0 = bx0 - ax0, by0 - ay0
        rot0 = math.degrees(math.atan2(vy0, vx0))
        len0 = math.hypot(vx0, vy0) or 1e-6

    tr = nuke.nodes.Transform(name="CP3D_Match")
    tr.setInput(0, None)
    tr.setXYpos(node.xpos() + 120, node.ypos() + 120)
    tr["center"].setValue([ax0, ay0])
    for kn in ("translate", "rotate", "scale"):
        tr[kn].setAnimated()

    for f in range(first, last + 1):
        ax, ay = node["to%d" % a].valueAt(f)
        tr["translate"].setValueAt(ax - ax0, f, 0)
        tr["translate"].setValueAt(ay - ay0, f, 1)
        if two:
            bx, by = node["to%d" % b].valueAt(f)
            vx, vy = bx - ax, by - ay
            tr["rotate"].setValueAt(math.degrees(math.atan2(vy, vx)) - rot0, f)
            tr["scale"].setValueAt(math.hypot(vx, vy) / len0, f)

    kind = "translate + rotate/scale" if two else "translate"
    _status(node, "Exported match-move Transform '%s' (%s)." % (tr.name(), kind))
    return tr


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def _btn(name, label, fn, start=False):
    b = nuke.PyScript_Knob(
        name, label,
        "import pep_cornerpin3d; pep_cornerpin3d.%s(nuke.thisNode())" % fn)
    if start:
        b.setFlag(nuke.STARTLINE)
    return b


def _cmd_btn(name, label, call, start=False):
    """Button whose command is an arbitrary pep_cornerpin3d.<call>."""
    b = nuke.PyScript_Knob(name, label,
                           "import pep_cornerpin3d; pep_cornerpin3d.%s" % call)
    if start:
        b.setFlag(nuke.STARTLINE)
    else:
        b.clearFlag(nuke.STARTLINE)
    return b


def build_cornerpin3d():
    """Create a PEP CornerPin 3D Points node. Menu entry point."""
    group = nuke.createNode("Group", inpanel=False)
    group.setName("PEP_CornerPin3Dpoints", uncollide=True)
    with group:
        geo = nuke.nodes.Input(name="geometry")
        cam = nuke.nodes.Input(name="camera"); cam["number"].setValue(1)
        nuke.nodes.Output(name="Output1").setInput(0, geo)

    k = group.addKnob
    k(nuke.Tab_Knob("cp3d", "CornerPin 3D"))
    k(nuke.Text_Knob("howto", "", (
        "<b>1.</b> Connect <b>geometry</b> (input 1) and a <b>camera</b> "
        "(input 2).<br><b>2.</b> Pick 4 points, press <b>Get Points</b>."
        "<br><b>3.</b> <b>Generate</b>, then <b>Export</b> or <b>Send to Matrix</b>.")))

    ps = nuke.Enumeration_Knob("pointSource", "pick from", POINT_SOURCES)
    ps.setTooltip("Vertices: select 4 points on the geometry in the 3D viewer. "
                  "Axis nodes: select 4 Axis / locator nodes in the graph.")
    k(ps)
    gp = _btn("getPts", "Get Points", "get_points", start=True)
    k(gp)

    k(nuke.Text_Knob("div_pts", "Source points (3D)"))
    k(nuke.Text_Knob("pts_hint", "", (
        "<i>Get Points</i> fills all four at once. Or set each corner from the "
        "average of the selected vertices with <i>Set</i> (single) / <i>anim</i> "
        "(trace a moving cluster over the range).")))
    for i in range(1, 5):
        pk = nuke.XYZ_Knob("xPt%d" % i, "pt %d" % i)
        k(pk)
        k(_cmd_btn("setPt%d" % i, "Set",
                   "set_point(nuke.thisNode(), %d)" % i))
        k(_cmd_btn("setPt%dAni" % i, "anim",
                   "set_point(nuke.thisNode(), %d, True)" % i))

    k(nuke.Text_Knob("div_gen", "Generate"))
    ff = nuke.Int_Knob("firstFrame", "first"); k(ff)
    lf = nuke.Int_Knob("lastFrame", "last"); lf.clearFlag(nuke.STARTLINE); k(lf)
    gb = _btn("gen", "Generate", "generate", start=True); k(gb)
    for i in range(1, 5):
        tk = nuke.XY_Knob("to%d" % i, "to %d" % i)
        tk.setEnabled(False)
        k(tk)

    k(nuke.Text_Knob("div_out", "Output"))
    rf = nuke.Int_Knob("refFrame", "reference frame"); k(rf)
    ex = _btn("export", "Export CornerPin", "export_cornerpin", start=True); k(ex)
    sm = _btn("toMatrix", "Send to Matrix", "send_to_matrix"); k(sm)

    k(nuke.Text_Knob("div_trk", "Export as Transform (match-move)"))
    ta = nuke.Enumeration_Knob("trkA", "point A", ["to 1", "to 2", "to 3", "to 4"])
    ta.setTooltip("Corner used for the 1-point match-move, and the first point "
                  "of the 2-point (rotation/scale) match-move.")
    k(ta)
    tb = nuke.Enumeration_Knob("trkB", "point B", ["to 1", "to 2", "to 3", "to 4"])
    tb.setValue("to 2")
    tb.setTooltip("Second point of the 2-point match-move (sets rotation + scale).")
    tb.clearFlag(nuke.STARTLINE); k(tb)
    k(_cmd_btn("trk1", "Export 1-pt Transform",
               "export_transform(nuke.thisNode(), False)", start=True))
    k(_cmd_btn("trk2", "Export 2-pt Transform (rot/scale)",
               "export_transform(nuke.thisNode(), True)"))

    st = nuke.Multiline_Eval_String_Knob("status", "")
    st.setValue("Connect geometry + camera, then Get Points.")
    st.setEnabled(False); k(st)

    gen = nuke.Boolean_Knob("generated", ""); gen.setVisible(False); k(gen)

    k(nuke.Text_Knob("footer", "", _FOOTER))

    k(nuke.Tab_Knob("help_tab", "Help"))
    k(nuke.Text_Knob("help_text", "", _HELP_HTML))
    hb = _btn("help_btn", "Open help", "show_help", start=True); k(hb)
    k(nuke.Text_Knob("footer2", "", _FOOTER))

    k(nuke.Tab_Knob("about_tab", "About"))
    k(nuke.Text_Knob("about_name", "", "<b>PEP CornerPin 3D Points</b>"))
    k(nuke.Text_Knob("about_ver", "Version:", _VERSION))
    k(nuke.Text_Knob("about_date", "Released:", _RELEASED))
    k(nuke.Text_Knob("about_author", "Author:", "Pixel Eye Pictures"))
    k(nuke.Text_Knob("about_notes", "Release notes:", _NOTES))
    k(nuke.Text_Knob("about_footer", "", _FOOTER))
    return group


def show_help(node=None):
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("PEP CornerPin 3D Points - Help")
    dlg.resize(560, 520)
    lay = QtWidgets.QVBoxLayout(dlg)
    view = QtWidgets.QTextBrowser(); view.setOpenExternalLinks(True)
    view.setHtml(_HELP_HTML)
    lay.addWidget(view)
    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
    btns.rejected.connect(dlg.reject)
    lay.addWidget(btns)
    dlg.exec_()


_FOOTER = ('Pixel Eye Pictures&nbsp;&nbsp;|&nbsp;&nbsp;'
           '<a style="color:#7aa2f7" '
           'href="https://github.com/PixelEyePictures/pep_nuke_tools">GitHub</a>')

_VERSION = "1.1"
_RELEASED = "2026-08-30"
_NOTES = ("Project 4 tracked 3D points (geo vertices or Axis nodes) through a "
          "camera into an animated CornerPin. Guided workflow with status "
          "readout, auto corner-ordering, whole-range trace, export to "
          "CornerPin2D, and Send to Matrix.<br>v1.1: per-corner Set from a "
          "vertex-cluster average + animated trace, and export projected corners "
          "as a 1-point or 2-point (rotation/scale) match-move Transform.")

_HELP_HTML = """
<h3>PEP CornerPin 3D Points</h3>
<p>Projects four 3D points through a camera to build an animated CornerPin -
useful for sticking a 2D element onto a planar surface from a 3D track.</p>
<ol>
<li>Connect the <b>geometry</b> to input 1 and the <b>camera</b> to input 2.</li>
<li><b>pick from</b>: <i>Selected vertices</i> - select 4 points on the geo in
the 3D viewer; or <i>Selected Axis nodes</i> - select 4 Axis / locator nodes in
the node graph. Press <b>Get Points</b>.</li>
<li>Set the <b>first</b> / <b>last</b> frames (blank = whole script) and press
<b>Generate</b>. The four points are projected and ordered
(bottom-left, bottom-right, top-right, top-left) over the range.</li>
<li><b>Export CornerPin</b> makes a CornerPin2D you can drop on your element; or
<b>Send to Matrix</b> makes the CornerPin and hands it to <i>PEP Tools &gt;
CornerPin to Matrix</i> so a Roto / RotoPaint follows the plane.</li>
</ol>
<p>The <b>status</b> line at the bottom tells you the next step at each stage.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""

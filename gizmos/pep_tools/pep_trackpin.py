"""PEP TrackPin.

A stabilize / match-move CornerPin rig, cleanly organised.

You paste (or fill) a 4-point track into the pin's `to` corners, pick a
reference frame, choose a mode, and press Apply:

  * Match Move  -> a held still frame rides the track (insert / patch sticks).
  * Stabilize   -> the plate is locked to the reference frame.

Built as a Group wrapping a FrameHold + CornerPin2D. Every button is a one-line
call into this module (no escaped-python knobs), so it stays readable and
maintainable. Hands off to PEP CornerPin -> Matrix to bake the pin onto a
Roto / RotoPaint.

Pixel Eye Pictures.
"""

import nuke

CORNERS = (1, 2, 3, 4)
_CP = "CornerPin2D1"
_FH = "FrameHold1"


# --------------------------------------------------------------------------- #
# Node access
# --------------------------------------------------------------------------- #
def _inner(group, name):
    n = nuke.toNode("%s.%s" % (group.fullName(), name))
    if n is None:
        raise RuntimeError("TrackPin is missing its inner %s." % name)
    return n


def _cp(group):
    return _inner(group, _CP)


# --------------------------------------------------------------------------- #
# Corner plumbing
# --------------------------------------------------------------------------- #
def _has_track(cp):
    """True if the `to` corners carry real animation to work from."""
    for i in CORNERS:
        k = cp["to%d" % i]
        if k.isAnimated() and k.animation(0) is not None:
            return True
    return False


def _copy_to_into_from(cp):
    """Copy the raw `to` track (its keyframe curves) into `from`."""
    for i in CORNERS:
        to, frm = cp["to%d" % i], cp["from%d" % i]
        for c in (0, 1):
            anim = to.animation(c)
            if anim is not None:
                frm.copyAnimation(c, anim)


def _set_all(cp, side, expr):
    for i in CORNERS:
        cp["%s%d" % (side, i)].setExpression(expr)


# --------------------------------------------------------------------------- #
# Buttons
# --------------------------------------------------------------------------- #
def set_ref_current(group=None):
    group = group or nuke.thisNode()
    group["ref_frame"].setValue(nuke.frame())


def apply(group=None):
    """Wire the pin for the chosen mode at the reference frame."""
    group = group or nuke.thisNode()
    cp = _cp(group)
    if not _has_track(cp):
        nuke.message("No track on the corners yet.\n\nFill the 'to' corners "
                     "first (paste a 4-point track, or use 'Fill corners from "
                     "node').")
        return
    ref = int(group["ref_frame"].value())
    stabilize = group["mode"].value() == "Stabilize"

    _set_all(cp, "to", "curve")          # read the raw track
    _copy_to_into_from(cp)               # duplicate it onto `from`
    if stabilize:
        _set_all(cp, "from", "curve")    # from moves with the track
        _set_all(cp, "to", "curve(%d)" % ref)   # to frozen at ref
        group["enable_frame_hold"].setValue(False)
    else:                                # Match Move
        _set_all(cp, "to", "curve")      # to moves with the track
        _set_all(cp, "from", "curve(%d)" % ref)  # from frozen at ref
        group["enable_frame_hold"].setValue(True)
    _apply_edges(group)
    nuke.message("%s applied at frame %d." %
                 ("Stabilize" if stabilize else "Match Move", ref))


def reset(group=None):
    """Return the corners to their raw track (undo stabilize/matchmove)."""
    group = group or nuke.thisNode()
    cp = _cp(group)
    _set_all(cp, "to", "curve")
    _set_all(cp, "from", "curve")
    group["enable_frame_hold"].setValue(False)


def _apply_edges(group):
    """Keep-edges option: don't crop the stabilized plate to black."""
    cp = _cp(group)
    if "black_outside" in cp.knobs():
        cp["black_outside"].setValue(not bool(group["keep_edges"].value()))


# --------------------------------------------------------------------------- #
# Fill corners from another node
# --------------------------------------------------------------------------- #
def _source_node(group):
    name = group["source_node"].value().strip() if "source_node" in group.knobs() else ""
    if name:
        n = nuke.toNode(name)
        if n is None:
            nuke.message("Source node '%s' not found." % name)
        return n
    for n in nuke.selectedNodes():
        if n.fullName() != group.fullName():
            return n
    nuke.message("Type a node name in 'source node', or select the node to "
                 "copy corners from.")
    return None


def fill_from_node(group=None):
    """Copy `to1..4` animation from a selected/named CornerPin (or a node that
    exposes to1..4, e.g. a Tracker's exported CornerPin2D)."""
    group = group or nuke.thisNode()
    src = _source_node(group)
    if src is None:
        return
    if not all(("to%d" % i) in src.knobs() for i in CORNERS):
        nuke.message("'%s' has no to1..4 corners.\n\nExport a CornerPin from "
                     "your Tracker (Tracker > export > CornerPin2D 'matchmove') "
                     "and point at that." % src.name())
        return
    cp = _cp(group)
    copied = 0
    for i in CORNERS:
        s, d = src["to%d" % i], cp["to%d" % i]
        for c in (0, 1):
            anim = s.animation(c)
            if anim is not None:
                d.copyAnimation(c, anim)
                copied += 1
            else:
                d.setValue(s.value(c), c)
    nuke.message("Filled corners from %s (%d curves)." % (src.name(), copied))


# --------------------------------------------------------------------------- #
# Bake expressions -> keyframes
# --------------------------------------------------------------------------- #
def bake_keys(group=None):
    """Freeze the evaluated corners to real keyframes and drop the expressions,
    so the rig renders/ships without relying on the live expression logic."""
    group = group or nuke.thisNode()
    cp = _cp(group)
    first = int(nuke.root()["first_frame"].value())
    last = int(nuke.root()["last_frame"].value())
    frames = range(first, last + 1)
    for side in ("to", "from"):
        for i in CORNERS:
            k = cp["%s%d" % (side, i)]
            samples = [(f, k.valueAt(f, 0), k.valueAt(f, 1)) for f in frames]
            k.clearAnimated()
            for c in (0, 1):
                k.setAnimated(c)
            for f, x, y in samples:
                k.setValueAt(x, f, 0)
                k.setValueAt(y, f, 1)
    group["enable_frame_hold"].setValue(False)
    nuke.message("Baked corners to keyframes (%d-%d)." % (first, last))


# --------------------------------------------------------------------------- #
# Hand off to CornerPin -> Matrix
# --------------------------------------------------------------------------- #
def _matrix_target(group):
    name = group["matrix_target"].value().strip() if "matrix_target" in group.knobs() else ""
    if name:
        t = nuke.toNode(name)
        if t is None:
            nuke.message("Target node '%s' not found." % name)
        return t
    for n in nuke.selectedNodes():
        if n.Class() in ("Roto", "RotoPaint", "CornerPin2D") and n.fullName() != group.fullName():
            return n
    nuke.message("Select a Roto / RotoPaint / CornerPin2D target (or name it "
                 "in 'matrix target').")
    return None


def send_to_matrix(group=None):
    """Bake this pin's 4x4 into a Roto/RotoPaint/CornerPin2D via PEP CornerPin
    -> Matrix."""
    group = group or nuke.thisNode()
    try:
        import pep_cornerpin_matrix as m
    except ImportError:
        nuke.message("PEP CornerPin -> Matrix module not found on the path.")
        return
    target = _matrix_target(group)
    if target is None:
        return
    cp = _cp(group)
    first = int(nuke.root()["first_frame"].value())
    last = int(nuke.root()["last_frame"].value())
    n = m.apply_matrix(cp, target, "transform_matrix", invert=False, bake=True,
                       first=first, last=last)
    nuke.message("Sent matrix into %s.transform_matrix (%d frames)." %
                 (target.name(), n))


# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #
_HELP_HTML = """
<h3>PEP TrackPin</h3>
<p>A stabilize / match-move CornerPin, tidied up.</p>
<ol>
<li>Put a 4-point track into the <b>to</b> corners &mdash; paste it, or use
<b>Fill corners from node</b> (point at a CornerPin exported from your Tracker).</li>
<li>Set the <b>reference frame</b> (or <b>Set to current</b>).</li>
<li>Pick <b>mode</b>: <i>Match Move</i> (a held still rides the track) or
<i>Stabilize</i> (lock the plate to the reference frame).</li>
<li>Press <b>Apply</b>.</li>
</ol>
<p><b>Keep edges</b> &mdash; don't crop the stabilized plate to black so you can
recover the edges downstream.<br>
<b>Bake to keyframes</b> &mdash; freeze the corners so the rig renders without the
live expressions.<br>
<b>Send to Matrix</b> &mdash; bake this pin's 4x4 onto a selected Roto / RotoPaint
/ CornerPin2D (uses PEP CornerPin -> Matrix).</li></p>
<p><b>Round trip:</b> Stabilize &rarr; paint your fix on the locked frame &rarr;
switch mode to Match Move &amp; Apply to re-apply the motion.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


def show_help(group=None):
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("PEP TrackPin - Help")
    dlg.resize(560, 520)
    lay = QtWidgets.QVBoxLayout(dlg)
    view = QtWidgets.QTextBrowser()
    view.setOpenExternalLinks(True)
    view.setHtml(_HELP_HTML)
    lay.addWidget(view)
    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
    btns.rejected.connect(dlg.reject)
    lay.addWidget(btns)
    dlg.exec_()


# --------------------------------------------------------------------------- #
# Build the rig
# --------------------------------------------------------------------------- #
_FOOTER = ('Pixel Eye Pictures&nbsp;&nbsp;|&nbsp;&nbsp;'
           '<a style="color:#7aa2f7" '
           'href="https://github.com/PixelEyePictures/pep_nuke_tools">GitHub</a>')


def _btn(name, label, fn, flags=""):
    cmd = "import pep_trackpin; pep_trackpin.%s(nuke.thisNode())" % fn
    k = nuke.PyScript_Knob(name, label, cmd)
    return k


def build_trackpin():
    """Create a wired PEP TrackPin group. Menu entry point."""
    group = nuke.createNode("Group", inpanel=False)
    group.setName("PEP_TrackPin", uncollide=True)

    with group:
        inp = nuke.nodes.Input(name="Input1")
        fh = nuke.nodes.FrameHold(name=_FH, firstFrame=1)
        fh.setInput(0, inp)
        fh["disable"].setExpression("!parent.enable_frame_hold")
        cp = nuke.nodes.CornerPin2D(name=_CP)
        cp.setInput(0, fh)
        out = nuke.nodes.Output(name="Output1")
        out.setInput(0, cp)

    k = group.addKnob
    k(nuke.Tab_Knob("trackpin", "TrackPin"))

    ref = nuke.Int_Knob("ref_frame", "reference frame")
    ref.setValue(int(nuke.frame()))
    k(ref)
    setref = _btn("set_ref", "Set to current", "set_ref_current")
    setref.setFlag(nuke.STARTLINE)
    k(setref)

    mode = nuke.Enumeration_Knob("mode", "mode", ["Match Move", "Stabilize"])
    k(mode)
    fhold = nuke.Boolean_Knob("enable_frame_hold", "frame hold on")
    fhold.setFlag(nuke.STARTLINE)
    k(fhold)

    ap = _btn("apply", "Apply", "apply")
    ap.setFlag(nuke.STARTLINE)
    k(ap)
    k(_btn("reset", "Reset", "reset"))

    k(nuke.Text_Knob("div_src", "Source"))
    src = nuke.String_Knob("source_node", "source node")
    k(src)
    fill = _btn("fill", "Fill corners from node", "fill_from_node")
    fill.setFlag(nuke.STARTLINE)
    k(fill)

    k(nuke.Text_Knob("div_corners", "Corners"))
    for i in CORNERS:
        lk = nuke.Link_Knob("to%d" % i)
        lk.setLink("%s.to%d" % (_CP, i))
        k(lk)
    for i in CORNERS:
        lk = nuke.Link_Knob("from%d" % i)
        lk.setLink("%s.from%d" % (_CP, i))
        k(lk)
    for kn in ("invert", "black_outside", "motionblur"):
        lk = nuke.Link_Knob(kn)
        lk.setLink("%s.%s" % (_CP, kn))
        k(lk)

    k(nuke.Text_Knob("div_out", "Output / Bake"))
    edges = nuke.Boolean_Knob("keep_edges", "keep edges (no crop on stabilize)")
    edges.setFlag(nuke.STARTLINE)
    k(edges)
    bake = _btn("bake", "Bake to keyframes", "bake_keys")
    bake.setFlag(nuke.STARTLINE)
    k(bake)
    mt = nuke.String_Knob("matrix_target", "matrix target")
    k(mt)
    sm = _btn("send_matrix", "Send to Matrix", "send_to_matrix")
    sm.setFlag(nuke.STARTLINE)
    k(sm)

    k(nuke.Text_Knob("footer", "", _FOOTER))

    hk = nuke.Tab_Knob("help_tab", "Help")
    k(hk)
    k(nuke.Text_Knob("help_text", "", _HELP_HTML))
    hb = _btn("help_btn", "Open help", "show_help")
    hb.setFlag(nuke.STARTLINE)
    k(hb)
    k(nuke.Text_Knob("footer2", "", _FOOTER))
    return group

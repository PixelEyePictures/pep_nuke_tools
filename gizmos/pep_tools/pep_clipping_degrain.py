"""PEP Clipping Degrain.

Denoise cleanly near crushed blacks / blown whites.

Denoisers struggle at clipped values (0 or 1) because there is no variation to
work from. This rig lifts the signal off the clip point, denoises in that
headroom, then reverses the lift exactly:

    Input -> PreGrade (lift) -> Denoiser -> PostGrade (reverse) -> Output

Features:
  * No plugin lock-in. The denoiser is a swappable inner node with an
    "Open denoiser controls" button, so there are no missing-knob errors when a
    plugin isn't installed. One-click swap to Nuke Denoise / Median / Neat Video
    (auto-detected).
  * A single pre/post grade pair and a Blacks / Whites / Both mode.
  * Lossless when the denoiser is a passthrough: in == out exactly.

Pixel Eye Pictures.
"""

import nuke

_PRE = "PreGrade"
_POST = "PostGrade"
_DEN = "Denoiser"
_CLIP = "ShowClipTest"
_SW = "ShowSwitch"

_DEFAULT_DENOISER = "Median"   # universal; swap to Denoise2 / Neat Video as needed


def _neat_video_class():
    """Auto-detect the installed Neat Video OFX class (any version), or None.

    The OFX class is version-specific (neatvideo_v2 / _v3 / _v4 / _v5 ...), so
    we scan the registered node classes and pick the highest match."""
    try:
        classes = nuke.allNodeClasses()
    except Exception:  # noqa: BLE001
        classes = []
    cands = sorted(c for c in classes if "neatvideo" in c.lower())
    return cands[-1] if cands else None

# grade expressions (mode: 0 Blacks, 1 Whites, 2 Both)
_BLACK_EXPR = "parent.mode==1?0:parent.amount_blacks"
_WHITE_EXPR = "parent.mode==0?1:1-parent.amount_whites"


# --------------------------------------------------------------------------- #
# Node access
# --------------------------------------------------------------------------- #
def _inner(group, name):
    n = nuke.toNode("%s.%s" % (group.fullName(), name))
    if n is None:
        raise RuntimeError("Clipping Degrain is missing its inner %s." % name)
    return n


# --------------------------------------------------------------------------- #
# Buttons
# --------------------------------------------------------------------------- #
def open_denoiser(group=None):
    """Show the inner denoiser's own properties (works with any denoiser)."""
    group = group or nuke.thisNode()
    try:
        nuke.show(_inner(group, _DEN))
    except Exception as e:  # noqa: BLE001
        nuke.message("Couldn't open the denoiser:\n\n%s" % e)


_BASE_CLASS = {"Median": "Median", "Nuke Denoise (NukeX)": "Denoise2"}


def _swap(group, klass, label, announce=True):
    """Replace the inner denoiser with a fresh node of `klass`, preserving the
    connections. Returns True on success, False if the class is unavailable."""
    old = _inner(group, _DEN)
    if old.Class() == klass:
        return True   # already that denoiser, nothing to do
    up = old.input(0)
    consumers = [(n, i) for n in nuke.allNodes(group=group)
                 for i in range(n.inputs()) if n.input(i) and
                 n.input(i).fullName() == old.fullName()]
    group.begin()
    try:
        try:
            new = nuke.createNode(klass, inpanel=False)
        except Exception:  # noqa: BLE001
            nuke.message("'%s' isn't available in this Nuke (plugin not "
                         "installed or NukeX-only)." % label)
            return False
        new.setInput(0, up)
        xpos, ypos = old.xpos(), old.ypos()
        nuke.delete(old)
        new.setName(_DEN)
        new.setXYpos(xpos, ypos)
        for n, i in consumers:
            n.setInput(i, new)
    finally:
        group.end()
    if announce:
        nuke.message("Denoiser set to %s. Open its controls to load a profile "
                     "/ tune it." % label)
    return True


def _swap_to_base(group):
    label = group["base_denoiser"].value()
    _swap(group, _BASE_CLASS.get(label, "Median"), label, announce=False)


def on_knob_changed(group=None, knob=None):
    """Live handler wired to the group's knobChanged: keeps the inner denoiser
    in sync with the 'Use Neat Video' checkbox and the base dropdown."""
    group = group or nuke.thisNode()
    knob = knob or nuke.thisKnob()
    if knob is None:
        return
    name = knob.name()
    if name == "use_neat_video":
        if group["use_neat_video"].value():
            klass = _neat_video_class()
            if klass is None:
                nuke.message("Neat Video isn't installed in this Nuke.")
                group["use_neat_video"].setValue(False)
            elif not _swap(group, klass, "Neat Video"):
                group["use_neat_video"].setValue(False)   # revert if it fails
        else:
            _swap_to_base(group)
    elif name == "base_denoiser":
        if not group["use_neat_video"].value():
            _swap_to_base(group)


# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #
_HELP_HTML = """
<h3>PEP Clipping Degrain</h3>
<p>Denoise cleanly right up against crushed blacks or blown whites.</p>
<ol>
<li>Turn on <b>Show clip</b> &mdash; remaining clipped pixels flag white.</li>
<li>Raise <b>Remove clip (blacks / whites)</b> until the white disappears
(you're lifting the signal off the clip point).</li>
<li>Turn off <b>Show clip</b>.</li>
<li><b>Open denoiser controls</b> and set up your denoiser (load a Neat Video
profile, or dial Denoise / Median). Re-profile if you change the lift.</li>
</ol>
<p><b>Mode</b> &mdash; protect Blacks, Whites, or Both ends at once.<br>
<b>Denoiser</b> &mdash; swap between Nuke Denoise (NukeX), Median, or Neat Video.
No plugin lock-in and no missing-knob errors when a plugin isn't installed.</p>
<p>The pre-grade and post-grade are exact inverses, so with the denoiser idle
the image is unchanged &mdash; the tool only ever adds the denoise itself.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


def show_help(group=None):
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("PEP Clipping Degrain - Help")
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
# Build
# --------------------------------------------------------------------------- #
_FOOTER = ('Pixel Eye Pictures&nbsp;&nbsp;|&nbsp;&nbsp;'
           '<a style="color:#7aa2f7" '
           'href="https://github.com/PixelEyePictures/pep_nuke_tools">GitHub</a>')


def _btn(name, label, fn):
    cmd = "import pep_clipping_degrain; pep_clipping_degrain.%s(nuke.thisNode())" % fn
    return nuke.PyScript_Knob(name, label, cmd)


def _grade(name, reverse):
    g = nuke.nodes.Grade(name=name)
    g["black"].setExpression(_BLACK_EXPR)
    g["white"].setExpression(_WHITE_EXPR)
    g["black_clamp"].setValue(False)
    if reverse:
        g["reverse"].setValue(True)
    return g


def build_clipping_degrain():
    """Create a wired PEP Clipping Degrain group. Menu entry point."""
    group = nuke.createNode("Group", inpanel=False)
    group.setName("PEP_ClippingDegrain", uncollide=True)

    with group:
        inp = nuke.nodes.Input(name="Input1")
        pre = _grade(_PRE, reverse=False); pre.setInput(0, inp)
        den = nuke.createNode(_DEFAULT_DENOISER, inpanel=False)
        den.setName(_DEN); den.setInput(0, pre)
        post = _grade(_POST, reverse=True); post.setInput(0, den)
        clip = nuke.nodes.ClipTest(name=_CLIP); clip.setInput(0, pre)
        sw = nuke.nodes.Switch(name=_SW)
        sw.setInput(0, post)   # normal
        sw.setInput(1, clip)   # show-clip preview
        sw["which"].setExpression("parent.show_clip")
        out = nuke.nodes.Output(name="Output1"); out.setInput(0, sw)

    k = group.addKnob
    k(nuke.Tab_Knob("degrain", "Clipping Degrain"))

    mode = nuke.Enumeration_Knob("mode", "mode", ["Blacks", "Whites", "Both"])
    k(mode)

    ab = nuke.Double_Knob("amount_blacks", "remove clip (blacks)")
    ab.setRange(0, 0.1); ab.setValue(0.011)
    k(ab)
    aw = nuke.Double_Knob("amount_whites", "remove clip (whites)")
    aw.setRange(0, 0.1); aw.setValue(0.011)
    k(aw)

    sc = nuke.Boolean_Knob("show_clip", "show clip")
    sc.setFlag(nuke.STARTLINE)
    sc.setTooltip("Highlight pixels still below 0 / above 1 after the lift.")
    k(sc)

    k(nuke.Text_Knob("div_den", "Denoiser"))
    base = nuke.Enumeration_Knob("base_denoiser", "denoiser",
                                 ["Median", "Nuke Denoise (NukeX)"])
    base.setTooltip("Denoiser used when 'Use Neat Video' is off.")
    k(base)
    nv = nuke.Boolean_Knob("use_neat_video", "Use Neat Video")
    nv.setFlag(nuke.STARTLINE)
    has_nv = _neat_video_class() is not None
    nv.setEnabled(has_nv)   # auto-detect: greyed out when not installed
    nv.setTooltip("Swap the denoiser to the installed Neat Video (OFX, any "
                  "version, auto-detected)." if has_nv else
                  "Neat Video not detected in this Nuke.")
    k(nv)
    ob = _btn("open_denoiser", "Open denoiser controls", "open_denoiser")
    ob.setFlag(nuke.STARTLINE)
    k(ob)

    k(nuke.Text_Knob("footer", "", _FOOTER))

    k(nuke.Tab_Knob("help_tab", "Help"))
    k(nuke.Text_Knob("help_text", "", _HELP_HTML))
    hb = _btn("help_btn", "Open help", "show_help"); hb.setFlag(nuke.STARTLINE)
    k(hb)
    k(nuke.Text_Knob("footer2", "", _FOOTER))

    # Live: keep the inner denoiser in sync with the checkbox / dropdown.
    if "knobChanged" in group.knobs():
        group["knobChanged"].setValue(
            "import pep_clipping_degrain as _c; "
            "_c.on_knob_changed(nuke.thisNode(), nuke.thisKnob())")
    return group

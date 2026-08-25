"""PEP Spot Remover.

Fast, smooth spot / marker fill. Given a plate (input 0) and a control matte
(input 1) over the spot, it pulls the surrounding pixels in and fills the hole
with an exponential blur - smoother and faster than an iterative patch.

The fill engine (premult surrounding -> exponential blur -> unpremult -> keymix)
is exposed as a reusable builder so Marker Cleanup can drive it too.

Controls:
  * Fill Blur Size - how far the surrounding pixels spread into the hole.
  * Edge Blur Size - softness on the control matte edge.
  * Sample Size    - how far outside the spot the fill samples from.
  * Blur Angle     - directional bias to the fill.
  * mix            - blend with the original.

Pixel Eye Pictures.
"""

import nuke


def _inner(group, name):
    n = nuke.toNode("%s.%s" % (group.fullName(), name))
    if n is None:
        raise RuntimeError("PEP Spot Remover is missing its inner %s." % name)
    return n


# --------------------------------------------------------------------------- #
# Reusable fill engine
# --------------------------------------------------------------------------- #
def _exponential_blur(src, size_expr, mult=2, prefix="Ex"):
    """Cascade of 'over' merges of increasingly large blurs = smooth, fast,
    exponential spread. `size_expr` is a knob-expression string for the base."""
    prev = src
    for i, factor in enumerate((1, mult, mult * 2, mult * 4)):
        b = nuke.nodes.Blur(name="%sBlur%d" % (prefix, i))
        b.setInput(0, src)
        b["size"].setExpression("(%s)*%d" % (size_expr, factor))
        if i == 0:
            prev = b
        else:
            m = nuke.nodes.Merge2(name="%sMerge%d" % (prefix, i), operation="over")
            m.setInput(0, prev)   # B (under)
            m.setInput(1, b)      # A (over)
            prev = m
    return prev


def build_fill(rgba, matte, ns_expr="parent.SampleSize",
               edge_expr="parent.EdgeBlur", fill_expr="parent.FillBlur",
               rot_expr="parent.BlurAngle"):
    """Build the spot-fill network from an rgba node and a matte node.
    Returns the final filled node (before mix). Callable from Marker Cleanup."""
    # matte -> a single control alpha (works from painted alpha OR an rgb blob)
    ctrl = nuke.nodes.Expression(name="MatteToAlpha"); ctrl.setInput(0, matte)
    ctrl["expr3"].setValue("max(a,max(r,max(g,b)))")

    plate_a = nuke.nodes.Copy(name="PlateAlpha")
    plate_a.setInput(0, rgba); plate_a.setInput(1, ctrl)
    plate_a["from0"].setValue("rgba.alpha"); plate_a["to0"].setValue("rgba.alpha")

    spot = nuke.nodes.Blur(name="SpotMatte", channels="alpha")
    spot.setInput(0, plate_a); spot["size"].setExpression(edge_expr)

    outside = nuke.nodes.Invert(name="Outside", channels="alpha")
    outside.setInput(0, spot)
    # sample size: pull the sampled region a little away from the spot edge
    erode = nuke.nodes.Dilate(name="SampleErode", channels="alpha")
    erode.setInput(0, outside)
    erode["size"].setExpression("-(%s)" % ns_expr)

    colored = nuke.nodes.Copy(name="ColorOutside")
    colored.setInput(0, rgba); colored.setInput(1, erode)
    colored["from0"].setValue("rgba.alpha"); colored["to0"].setValue("rgba.alpha")
    prem = nuke.nodes.Premult(name="PremultOutside"); prem.setInput(0, colored)

    # directional: rotate -> blur -> rotate back
    rot1 = nuke.nodes.Transform(name="RotIn"); rot1.setInput(0, prem)
    rot1["rotate"].setExpression(rot_expr)
    blurred = _exponential_blur(rot1, fill_expr)
    rot2 = nuke.nodes.Transform(name="RotOut"); rot2.setInput(0, blurred)
    rot2["rotate"].setExpression("-(%s)" % rot_expr)

    filled = nuke.nodes.Unpremult(name="UnpremultFill"); filled.setInput(0, rot2)

    # keymix: inside the spot (mask=1) -> filled (B); outside -> original (A)
    km = nuke.nodes.Keymix(name="SpotKeymix", channels="rgb")
    km.setInput(0, rgba)     # A
    km.setInput(1, filled)   # B
    km.setInput(2, spot)     # mask
    return km


# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #
_HELP_HTML = """
<h3>PEP Spot Remover</h3>
<p>Fast, smooth fill for spots / markers. Feed the plate into input 1 and a
matte over the spot into input 2 (painted alpha or a white blob both work).</p>
<ol>
<li><b>Fill Blur Size</b> - how far surrounding pixels spread into the hole.</li>
<li><b>Edge Blur Size</b> - soften the matte edge.</li>
<li><b>Sample Size</b> - how far outside the spot to sample from.</li>
<li><b>Blur Angle</b> - directional bias (like a directional blur).</li>
<li><b>mix</b> - blend against the original.</li>
</ol>
<p><b>Follow a track:</b> put a Tracker (match-move) or a Transform exported from
it in the <b>tracker</b> field (or <i>Set from selected</i>) and press
<b>Link tracker</b> - the matte and the fill ride the track over the shot.
<i>Unlink</i> resets it.</p>
<p>The surrounding pixels are premultiplied and spread inward with an
exponential blur, then keyed back in over the spot. Stock nodes, no plugins.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


def show_help(group=None):
    nuke.message(_HELP_HTML)


# --------------------------------------------------------------------------- #
# Tracking: make the matte (and so the fill) follow a Tracker / Transform
# --------------------------------------------------------------------------- #
_TRACK_KNOBS = ("translate", "rotate", "scale", "skewX", "skewY", "center")


def set_tracker_from_selected(group=None):
    """Fill the 'tracker' field from the currently selected node."""
    group = group or nuke.thisNode()
    fn = group.fullName()
    for n in nuke.selectedNodes():
        if n.fullName() != fn:
            group["tracker"].setValue(n.name())
            return
    nuke.message("Select the Tracker / Transform node first.")


def link_tracker(group=None):
    """Copy a Tracker's / match-move Transform's animation onto the matte, so
    the spot fill follows the track."""
    group = group or nuke.thisNode()
    name = group["tracker"].value().strip()
    if not name:
        nuke.message("Type or drop a Tracker / Transform node name into "
                     "'tracker' (or use 'Set from selected').")
        return
    src = nuke.toNode(name)
    if src is None:
        nuke.message("Node '%s' not found." % name)
        return
    mt = _inner(group, "MatteTrack")
    linked = 0
    for kn in _TRACK_KNOBS:
        if kn not in src.knobs() or kn not in mt.knobs():
            continue
        s, d = src[kn], mt[kn]
        size = d.arraySize() if hasattr(d, "arraySize") else 1
        for c in range(size):
            anim = s.animation(c) if s.isAnimated() else None
            if anim is not None:
                d.copyAnimation(c, anim)
            else:
                try:
                    d.setValue(s.getValue(c) if size > 1 else s.getValue(), c)
                except Exception:  # noqa: BLE001
                    pass
        linked += 1
    nuke.message("Linked the matte to %s (%d knobs). The spot fill now follows "
                 "the track.\n\nTip: link a Tracker set to match-move, or a "
                 "Transform exported from your Tracker." % (name, linked))


def unlink_tracker(group=None):
    """Drop the track link and reset the matte transform to identity."""
    group = group or nuke.thisNode()
    mt = _inner(group, "MatteTrack")
    for kn in _TRACK_KNOBS:
        if kn in mt.knobs():
            try:
                mt[kn].clearAnimated()
            except Exception:  # noqa: BLE001
                pass
    mt["translate"].setValue([0, 0])
    mt["rotate"].setValue(0)
    mt["scale"].setValue(1)
    nuke.message("Unlinked - the matte is back to identity.")


# --------------------------------------------------------------------------- #
# Build the standalone node
# --------------------------------------------------------------------------- #
_FOOTER = ('Pixel Eye Pictures&nbsp;&nbsp;|&nbsp;&nbsp;'
           '<a style="color:#7aa2f7" '
           'href="https://github.com/PixelEyePictures/pep_nuke_tools">GitHub</a>')


_VERSION = "1.1"
_RELEASED = "2026-08-23"
_NOTES = ("Exponential-blur spot fill with Fill Blur, Edge Blur, Sample Size "
          "and Blur Angle; reusable engine shared with Marker Cleanup. v1.1 "
          "adds a tracker link so the matte and fill follow a track.")


def _btn(name, label, fn):
    return nuke.PyScript_Knob(
        name, label,
        "import pep_spot_remover; pep_spot_remover.%s(nuke.thisNode())" % fn)


def _about_tab(add, title, version, released, notes):
    """Standard PEP About / Version tab."""
    add(nuke.Tab_Knob("about_tab", "About"))
    add(nuke.Text_Knob("about_name", "", "<b>%s</b>" % title))
    add(nuke.Text_Knob("about_ver", "Version:", version))
    add(nuke.Text_Knob("about_date", "Released:", released))
    add(nuke.Text_Knob("about_author", "Author:", "Pixel Eye Pictures"))
    add(nuke.Text_Knob("about_notes", "Release notes:", notes))
    add(nuke.Text_Knob("about_footer", "", _FOOTER))


def build_spot_remover():
    """Create a wired PEP Spot Remover group. Menu entry point."""
    group = nuke.createNode("Group", inpanel=False)
    group.setName("PEP_SpotRemover", uncollide=True)

    with group:
        rgba = nuke.nodes.Input(name="rgba")
        matte = nuke.nodes.Input(name="matte"); matte["number"].setValue(1)
        # optional tracking: the matte (and so the fill) rides a linked track
        mtrack = nuke.nodes.Transform(name="MatteTrack"); mtrack.setInput(0, matte)
        mtrack["black_outside"].setValue(False)
        filled = build_fill(rgba, mtrack)
        mix = nuke.nodes.Dissolve(name="Mix")
        mix.setInput(0, filled); mix.setInput(1, rgba)   # which=0 -> filled (mix=1)
        mix["which"].setExpression("1-parent.mix")
        nuke.nodes.Output(name="Output1").setInput(0, mix)

    k = group.addKnob
    k(nuke.Tab_Knob("spot", "Spot Remover"))
    fb = nuke.Double_Knob("FillBlur", "Fill Blur Size"); fb.setRange(0, 200)
    fb.setValue(20); k(fb)
    eb = nuke.Double_Knob("EdgeBlur", "Edge Blur Size"); eb.setRange(0, 50)
    eb.setValue(5); k(eb)
    ss = nuke.Double_Knob("SampleSize", "Sample Size"); ss.setRange(0, 100)
    ss.setValue(5); k(ss)
    ba = nuke.Double_Knob("BlurAngle", "Blur Angle"); ba.setRange(-180, 180)
    ba.setValue(0); k(ba)
    mx = nuke.Double_Knob("mix", "mix"); mx.setRange(0, 1); mx.setValue(1); k(mx)

    k(nuke.Text_Knob("div_track", "Tracking (optional)"))
    tk = nuke.String_Knob("tracker", "tracker / transform")
    tk.setTooltip("Name of a Tracker (match-move) or a Transform exported from "
                  "it. Link it so the matte and the fill follow the track.")
    k(tk)
    sset = _btn("set_from_sel", "Set from selected", "set_tracker_from_selected")
    sset.setFlag(nuke.STARTLINE); k(sset)
    k(_btn("link_trk", "Link tracker", "link_tracker"))
    k(_btn("unlink_trk", "Unlink", "unlink_tracker"))

    k(nuke.Text_Knob("footer", "", _FOOTER))
    k(nuke.Tab_Knob("help_tab", "Help"))
    k(nuke.Text_Knob("help_text", "", _HELP_HTML))
    hb = _btn("help_btn", "Open help", "show_help"); hb.setFlag(nuke.STARTLINE)
    k(hb)
    k(nuke.Text_Knob("footer2", "", _FOOTER))
    _about_tab(k, "PEP Spot Remover", _VERSION, _RELEASED, _NOTES)
    return group

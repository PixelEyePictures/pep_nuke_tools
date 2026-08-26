"""PEP Gradient.

A robust background / gradient generator - much more than a base colour and a
single ramp:

  * Up to 4 colour stops (position + colour each) via a ColorLookup, so it's a
    real multi-stop gradient, not just base + ramp.
  * Shapes: Linear, Radial (circle), Box (square), Diamond, and Depth.
  * Depth mode: plug a depth pass into the input and it remaps the depth
    through the colour stops - an instant depth fog / atmosphere.
  * Noise break-up: an fBm noise disturbs the gradient position to kill banding
    and give organic, patchy falloff (great for the fog), with amount / size /
    detail / seed controls.

Built as a Group of stock nodes; the colour stops drive a ColorLookup that is
rebuilt from the knobs. Menu entry: PEP Tools -> Gradient.

Pixel Eye Pictures.
"""

import nuke

MAX_STOPS = 4
_SWITCH = "ShapeSwitch"
_GRAD = "Grad"
_NOISE = "NoiseGen"

# shape index -> inner source node feeding the ShapeSwitch
_SHAPES = ["Linear", "Radial", "Box", "Diamond", "Depth"]


def _inner(group, name):
    n = nuke.toNode("%s.%s" % (group.fullName(), name))
    if n is None:
        raise RuntimeError("PEP Gradient is missing its inner %s." % name)
    return n


# --------------------------------------------------------------------------- #
# Colour-stop LUT
# --------------------------------------------------------------------------- #
def rebuild_lut(group=None):
    """Rewrite the ColorLookup curves from the colour-stop knobs."""
    group = group or nuke.thisNode()
    lut = _inner(group, _GRAD)["lut"]
    for name in ("red", "green", "blue", "alpha"):   # clear -> identity
        try:
            lut.delCurve(name)
            lut.addCurve(name, "")
        except Exception:  # noqa: BLE001
            pass
    n = min(int(group["num_stops"].value()), MAX_STOPS)
    for i in range(1, n + 1):
        pos = group["pos%d" % i].value()
        col = group["color%d" % i]
        for ci in range(4):                          # r,g,b,a -> curves 1..4
            lut.setValueAt(col.value(ci), pos, ci + 1)


def on_knob_changed(group=None, knob=None):
    group = group or nuke.thisNode()
    knob = knob or nuke.thisKnob()
    if knob is None:
        return
    name = knob.name()
    if name == "lock_center":
        group["center"].setEnabled(not group["lock_center"].value())
        return
    if name == "num_stops":
        group["num_stops"].setValue(min(int(group["num_stops"].value()), MAX_STOPS))
        rebuild_lut(group)
    elif name.startswith("color") or name.startswith("pos"):
        rebuild_lut(group)


def randomize_seed(group=None):
    group = group or nuke.thisNode()
    # deterministic-ish nudge without Math.random: walk the seed
    group["noise_seed"].setValue(group["noise_seed"].value() + 7.0)


# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #
_HELP_HTML = """
<h3>PEP Gradient</h3>
<p>A multi-stop background / gradient generator with shapes, depth fog and
noise break-up.</p>
<ol>
<li>Set <b>number of stops</b> (1-4) and each stop's <b>colour</b> + <b>position</b>
(0 = start, 1 = end).</li>
<li>Pick a <b>shape</b>: Linear (drag the ramp handles), Radial / Box / Diamond
(set centre + radius), or <b>Depth</b>.</li>
<li><b>Depth</b> mode: plug a depth pass into the input, then set <b>depth
near / far</b> to frame the range - the stops become a depth fog.</li>
<li><b>Break-up</b>: raise <b>noise amount</b> to disturb the gradient (kills
banding, makes fog patchy). Tune <b>size / detail / gain / seed</b>.</li>
</ol>
<p>Stops drive a ColorLookup, so it's a true multi-colour gradient. Everything
is stock nodes - no plugins.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


def show_help(group=None):
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("PEP Gradient - Help")
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

_DEFAULT_COLORS = [
    (0.0, 0.62, 0.30, 1.0),   # base green (from the original)
    (0.90, 0.10, 0.09, 1.0),  # ramp red
    (0.10, 0.20, 0.60, 1.0),
    (0.95, 0.95, 0.95, 1.0),
]

# shape-field expressions (write grayscale t into r,g,b)
_C = "parent.center"
_R = "parent.radius"
_RADIAL = "clamp(sqrt(pow((x-%s.x)/%s_x,2)+pow((y-%s.y)/%s_y,2)))" % (_C, _R, _C, _R)
_BOX = "clamp(max(abs((x-%s.x)/%s_x),abs((y-%s.y)/%s_y)))" % (_C, _R, _C, _R)
_DIAMOND = "clamp(abs((x-%s.x)/%s_x)+abs((y-%s.y)/%s_y))" % (_C, _R, _C, _R)
_DEPTH = "clamp((depth.Z-parent.depth_near)/(parent.depth_far-parent.depth_near))"


def _btn(name, label, fn):
    return nuke.PyScript_Knob(
        name, label,
        "import pep_gradient; pep_gradient.%s(nuke.thisNode())" % fn)


def _expr_field(name, formula):
    e = nuke.nodes.Expression(name=name)
    for i in range(3):
        e["expr%d" % i].setValue(formula)
    e["expr3"].setValue("1")
    return e


def build_gradient():
    """Create a wired PEP Gradient group. Menu entry point."""
    fmt = nuke.root().format()
    w, h = fmt.width(), fmt.height()

    group = nuke.createNode("Group", inpanel=False)
    group.setName("PEP_Gradient", uncollide=True)

    with group:
        inp = nuke.nodes.Input(name="Input1")            # optional depth pass

        ramp = nuke.nodes.Ramp(name="LinearRamp")
        ramp["color"].setValue([1, 1, 1, 1])
        ramp["p0"].setExpression("parent.rampto0.x", 0)
        ramp["p0"].setExpression("parent.rampto0.y", 1)
        ramp["p1"].setExpression("parent.rampto1.x", 0)
        ramp["p1"].setExpression("parent.rampto1.y", 1)

        e_rad = _expr_field("ExprRadial", _RADIAL)
        e_box = _expr_field("ExprBox", _BOX)
        e_dia = _expr_field("ExprDiamond", _DIAMOND)
        e_dep = _expr_field("ExprDepth", _DEPTH); e_dep.setInput(0, inp)

        sw = nuke.nodes.Switch(name=_SWITCH)
        for idx, node in enumerate([ramp, e_rad, e_box, e_dia, e_dep]):
            sw.setInput(idx, node)
        sw["which"].setExpression("parent.shape")

        noise = nuke.nodes.Noise(name=_NOISE)
        for kn, expr in [("size", "parent.noise_size"),
                         ("octaves", "parent.noise_octaves"),
                         ("gain", "parent.noise_gain"),
                         ("zoffset", "parent.noise_seed")]:
            if kn in noise.knobs():
                noise[kn].setExpression(expr)

        noiseb = nuke.nodes.Blur(name="NoiseBlur"); noiseb.setInput(0, noise)
        noiseb["size"].setExpression("parent.noise_smooth")

        brk = nuke.nodes.MergeExpression(name="BreakUp")
        brk.setInput(0, noiseb)  # B = (softened) noise
        brk.setInput(1, sw)      # A = gradient t
        for i, ch in enumerate("rgb"):
            brk["expr%d" % i].setValue(
                "clamp(A%s + (B%s-0.5)*parent.noise_amount)" % (ch, ch))
        brk["expr3"].setValue("1")

        grad = nuke.nodes.ColorLookup(name=_GRAD); grad.setInput(0, brk)

        outb = nuke.nodes.Blur(name="OutBlur"); outb.setInput(0, grad)
        outb["size"].setExpression("parent.smooth")

        out = nuke.nodes.Output(name="Output1"); out.setInput(0, outb)

    k = group.addKnob
    k(nuke.Tab_Knob("gradient", "Gradient"))

    shape = nuke.Enumeration_Knob("shape", "shape", _SHAPES)
    k(shape)

    # linear handles (on-screen labels)
    r0 = nuke.XY_Knob("rampto0", "RampFrom0"); r0.setValue([0, h // 2])
    k(r0)
    r1 = nuke.XY_Knob("rampto1", "Rampto1"); r1.setValue([w, h // 2])
    k(r1)

    # radial / box / diamond
    ctr = nuke.XY_Knob("center", "centre"); ctr.setValue([w // 2, h // 2])
    k(ctr)
    lc = nuke.Boolean_Knob("lock_center", "lock centre")
    lc.setFlag(nuke.STARTLINE)
    lc.setTooltip("Lock the centre handle so it can't be nudged by accident.")
    k(lc)
    rx = nuke.Double_Knob("radius_x", "radius x"); rx.setRange(1, max(w, h))
    rx.setValue(w // 2); k(rx)
    ry = nuke.Double_Knob("radius_y", "radius y"); ry.setRange(1, max(w, h))
    ry.setValue(h // 2); k(ry)

    # depth
    k(nuke.Text_Knob("div_depth", "Depth (plug a depth pass into the input)"))
    dn = nuke.Double_Knob("depth_near", "depth near"); dn.setRange(0, 100000)
    dn.setValue(0); k(dn)
    df = nuke.Double_Knob("depth_far", "depth far"); df.setRange(0, 100000)
    df.setValue(1000); k(df)

    # stops
    k(nuke.Text_Knob("div_stops", "Colour stops"))
    ns = nuke.Int_Knob("num_stops", "number of stops"); ns.setRange(1, MAX_STOPS)
    ns.setValue(2); k(ns)
    for i in range(1, MAX_STOPS + 1):
        col = nuke.AColor_Knob("color%d" % i, "colour %d" % i)
        col.setValue(list(_DEFAULT_COLORS[i - 1]))
        k(col)
        p = nuke.Double_Knob("pos%d" % i, "position %d" % i)
        p.setRange(0, 1); p.setValue(round((i - 1) / float(MAX_STOPS - 1), 3))
        p.clearFlag(nuke.STARTLINE)
        k(p)

    # break-up
    k(nuke.Text_Knob("div_noise", "Break-up (noise)"))
    na = nuke.Double_Knob("noise_amount", "noise amount"); na.setRange(0, 1)
    na.setValue(0); k(na)
    nsz = nuke.Double_Knob("noise_size", "noise size"); nsz.setRange(1, 2000)
    nsz.setValue(200); k(nsz)
    noc = nuke.Int_Knob("noise_octaves", "detail (octaves)"); noc.setRange(1, 10)
    noc.setValue(4); k(noc)
    ng = nuke.Double_Knob("noise_gain", "gain"); ng.setRange(0, 1)
    ng.setValue(0.5); k(ng)
    nsd = nuke.Double_Knob("noise_seed", "seed"); nsd.setRange(0, 1000)
    nsd.setValue(0); k(nsd)
    nsm = nuke.Double_Knob("noise_smooth", "noise blur"); nsm.setRange(0, 100)
    nsm.setValue(0)
    nsm.setTooltip("Blur/soften the noise pattern before it breaks up the gradient.")
    k(nsm)
    rnd = _btn("rand_seed", "Randomize seed", "randomize_seed")
    rnd.setFlag(nuke.STARTLINE); k(rnd)

    # output smoothing
    k(nuke.Text_Knob("div_smooth", "Output"))
    sm = nuke.Double_Knob("smooth", "smooth (blur)"); sm.setRange(0, 100)
    sm.setValue(0)
    sm.setTooltip("Blur the final gradient - softens banding and the noise break-up.")
    k(sm)

    k(nuke.Text_Knob("footer", "", _FOOTER))

    k(nuke.Tab_Knob("help_tab", "Help"))
    k(nuke.Text_Knob("help_text", "", _HELP_HTML))
    hb = _btn("help_btn", "Open help", "show_help"); hb.setFlag(nuke.STARTLINE)
    k(hb)
    k(nuke.Text_Knob("footer2", "", _FOOTER))

    rebuild_lut(group)
    if "knobChanged" in group.knobs():
        group["knobChanged"].setValue(
            "import pep_gradient; "
            "pep_gradient.on_knob_changed(nuke.thisNode(), nuke.thisKnob())")
    return group

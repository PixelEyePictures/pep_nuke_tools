"""PEP Match Blacks.

Match / neutralise / crush the low value range of an image without touching the
mids or highlights. Remaps a Source colour in the shadows to a Target colour,
with a pinned black point and optional clamp.

Features:

  * Neutralise  - set Target to neutral grey at the source luminance (kill a
    colour cast in the blacks).
  * Zero blacks - crush the source colour to true black.
  * Reference input + Match to reference - sample this plate's black level and a
    reference's black level, and fill Source / Target automatically.
  * Softness - feather the correction into the mids instead of a hard clamp.

Pixel Eye Pictures.
"""

import nuke

_REC709 = (0.2126, 0.7152, 0.0722)
_GRADE = "Grade2"
_SYNC_CLAMPS = ("Clamp3", "Clamp4", "Clamp5")


def _inner(group, name):
    n = nuke.toNode("%s.%s" % (group.fullName(), name))
    if n is None:
        raise RuntimeError("PEP Match Blacks is missing its inner %s." % name)
    return n


# --------------------------------------------------------------------------- #
# Low-range sampling
# --------------------------------------------------------------------------- #
def _avg_low(src, pin_black, samples=48):
    """Average colour of the darkest pixels of `src` (a grid sample)."""
    fmt = nuke.root().format()
    w, h = fmt.width(), fmt.height()
    if src.width() > 0:
        w, h = src.width(), src.height()
    pts = []
    for i in range(samples):
        x = int(w * i / float(samples - 1))
        for j in range(samples):
            y = int(h * j / float(samples - 1))
            r = src.sample("rgba.red", x, y)
            g = src.sample("rgba.green", x, y)
            b = src.sample("rgba.blue", x, y)
            lum = _REC709[0] * r + _REC709[1] * g + _REC709[2] * b
            pts.append((lum, r, g, b))
    lows = [p for p in pts if p[0] <= pin_black]
    if len(lows) < 10:                       # fall back to the darkest 5%
        pts.sort()
        lows = pts[:max(10, len(pts) // 20)]
    n = float(len(lows))
    return (sum(p[1] for p in lows) / n,
            sum(p[2] for p in lows) / n,
            sum(p[3] for p in lows) / n)


# --------------------------------------------------------------------------- #
# Buttons
# --------------------------------------------------------------------------- #
def neutralise(group=None):
    """Target = neutral grey at the source luminance (removes the cast)."""
    group = group or nuke.thisNode()
    r, g, b = [group["FromColor"].value(i) for i in range(3)]
    lum = _REC709[0] * r + _REC709[1] * g + _REC709[2] * b
    group["ToColor"].setValue([lum, lum, lum])


def zero_blacks(group=None):
    group = group or nuke.thisNode()
    group["ToColor"].setValue([0, 0, 0])


def sample_source(group=None):
    """Fill Source from this plate's black level."""
    group = group or nuke.thisNode()
    src = group.input(0)
    if src is None:
        nuke.message("Connect an image to the main input first.")
        return
    group["FromColor"].setValue(list(_avg_low(src, group["pinBlack"].value())))


def match_reference(group=None):
    """Source = this plate's blacks, Target = the reference's blacks."""
    group = group or nuke.thisNode()
    src = group.input(0)
    ref = group.input(2)
    if src is None:
        nuke.message("Connect an image to the main input first.")
        return
    pin = group["pinBlack"].value()
    group["FromColor"].setValue(list(_avg_low(src, pin)))
    if ref is None:
        nuke.message("Source set from the plate. Connect a plate to the "
                     "'Reference' input to also set the Target.")
        return
    group["ToColor"].setValue(list(_avg_low(ref, pin)))


def on_knob_changed(group=None, knob=None):
    """Keep the inner clamps' channels / unpremult in sync (as the original)."""
    group = group or nuke.thisNode()
    knob = knob or nuke.thisKnob()
    if knob is None:
        return
    name = knob.name()
    if name not in ("channels", "unpremult", "invert_unpremult"):
        return
    src = _inner(group, _GRADE)[name]
    for c in _SYNC_CLAMPS:
        try:
            _inner(group, c)[name].fromScript(src.toScript())
        except Exception:  # noqa: BLE001
            pass
    if name == "channels":
        for kn in ("Achannels", "Bchannels", "output"):
            try:
                _inner(group, "Merge2")[kn].fromScript(src.toScript())
            except Exception:  # noqa: BLE001
                pass
        try:
            _inner(group, "FinalKeymix")["channels"].fromScript(src.toScript())
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Help
# --------------------------------------------------------------------------- #
_HELP_HTML = """
<h3>PEP Match Blacks</h3>
<p>Colour-correct the low range only - match, neutralise or crush the blacks
without touching mids / highlights.</p>
<ol>
<li>Set <b>Pin Blacks</b> to the top of the range you want to affect.</li>
<li>Set <b>Source Color</b> (the cast you have) and <b>Target Color</b> (what
you want) - use the colour knob's eyedropper on the viewer.</li>
<li>Or press <b>Neutralise</b> (kill the cast), <b>Zero blacks</b> (crush to
black), or <b>Match to reference</b> (sample a reference plate's blacks).</li>
<li><b>Softness</b> feathers the correction into the mids. <b>Clamp</b> holds the
low end to the Target. Mask + <b>mix</b> as usual.</li>
</ol>
<p><b>Match to reference:</b> connect a reference plate to the <b>Reference</b>
input, then press the button - Source is sampled from this plate's blacks and
Target from the reference's blacks.</p>
<p style="color:#888">Pixel Eye Pictures</p>
"""


def show_help(group=None):
    try:
        from PySide2 import QtWidgets
    except ImportError:
        from PySide6 import QtWidgets
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle("PEP Match Blacks - Help")
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

_LUM = "(%g*r+%g*g+%g*b)" % _REC709


def _btn(name, label, fn):
    return nuke.PyScript_Knob(
        name, label,
        "import pep_match_blacks; pep_match_blacks.%s(nuke.thisNode())" % fn)


def _set3(knob, expr_fmt):
    for i, ch in enumerate("rgb"):
        knob.setExpression(expr_fmt % ch if "%s" in expr_fmt else expr_fmt, i)


def build_match_blacks():
    """Create a wired PEP Match Blacks group. Menu entry point."""
    group = nuke.createNode("Group", inpanel=False)
    group.setName("PEP_MatchBlacks", uncollide=True)

    with group:
        main = nuke.nodes.Input(name="Input")
        mask = nuke.nodes.Input(name="Mask"); mask["number"].setValue(1)
        ref = nuke.nodes.Input(name="Reference"); ref["number"].setValue(2)

        # external mask -> alpha, defaulting to 1 (full effect) when no mask is
        # connected, so the correction applies everywhere by default.
        mprep = nuke.nodes.Expression(name="MaskPrep"); mprep.setInput(0, mask)
        mprep["expr0"].setValue("r"); mprep["expr1"].setValue("g")
        mprep["expr2"].setValue("b")
        mprep["expr3"].setValue("[exists parent.input1]?a:1")

        # low branch: clamp to pinBlack -> grade From->To -> optional clamp
        c4 = nuke.nodes.Clamp(name="Clamp4", channels="rgb"); c4.setInput(0, main)
        c4["minimum_enable"].setValue(False)
        _set3(c4["maximum"], "parent.pinBlack")
        _set3(c4["MaxClampTo"], "parent.pinBlack")
        c4["MaxClampTo_enable"].setValue(True)
        c4["unpremult"].setValue("rgba.alpha")

        grade = nuke.nodes.Grade(name=_GRADE); grade.setInput(0, c4)
        _set3(grade["blackpoint"], "min(parent.pinBlack,parent.FromColor.%s)")
        _set3(grade["whitepoint"], "max(parent.pinBlack,parent.FromColor.%s)")
        _set3(grade["white"], "max(parent.pinBlack,parent.FromColor.%s)")
        for i, ch in enumerate("rgb"):
            grade["black"].setExpression("parent.ToColor.%s" % ch, i)
        grade["black"].setExpression("0", 3)
        grade["black_clamp"].setValue(False)
        grade["unpremult"].setValue("rgba.alpha")

        c5 = nuke.nodes.Clamp(name="Clamp5", channels="rgb"); c5.setInput(0, grade)
        _set3(c5["minimum"], "min(parent.pinBlack,parent.ToColor.%s)")
        c5["minimum_enable"].setExpression("parent.clamp")
        _set3(c5["maximum"], "max(parent.pinBlack,parent.ToColor.%s)")
        c5["maximum_enable"].setExpression("parent.clamp")
        c5["unpremult"].setValue("rgba.alpha")

        # high branch: floor to pinBlack
        c3 = nuke.nodes.Clamp(name="Clamp3", channels="rgb"); c3.setInput(0, main)
        _set3(c3["minimum"], "parent.pinBlack")
        c3["maximum_enable"].setValue(False)
        c3["MinClampTo_enable"].setValue(True)
        c3["unpremult"].setValue("rgba.alpha")

        m2 = nuke.nodes.Merge2(name="Merge2", operation="max")
        m2["Achannels"].setValue("rgb"); m2["Bchannels"].setValue("rgb")
        m2["output"].setValue("rgb")
        m2.setInput(0, c3); m2.setInput(1, c5)

        # softness: feather corrected into original by luminance
        soft = nuke.nodes.Expression(name="SoftMask"); soft.setInput(0, main)
        soft["expr0"].setValue("r"); soft["expr1"].setValue("g"); soft["expr2"].setValue("b")
        # mask=0 in the blacks -> Keymix keeps A (corrected); ramps to 1 by
        # pinBlack+softness -> B (original). So the correction feathers out.
        soft["expr3"].setValue(
            "clamp((%s-parent.pinBlack)/max(parent.softness,1e-6))" % _LUM)
        softkm = nuke.nodes.Keymix(name="SoftKeymix", channels="rgb")
        softkm.setInput(0, m2)      # A (mask=0) = corrected
        softkm.setInput(1, main)    # B (mask=1) = original
        softkm.setInput(2, soft)    # mask = luminance feather

        soft_sw = nuke.nodes.Switch(name="SoftSwitch")
        soft_sw.setInput(0, m2)
        soft_sw.setInput(1, softkm)
        soft_sw["which"].setExpression("parent.softness>0?1:0")

        # final external-mask keymix. Keymix: mask=1 -> B, mask=0/none -> A.
        # The mask chain yields alpha=1 when no Mask is connected, so B (the
        # correction) applies fully by default.
        km = nuke.nodes.Keymix(name="FinalKeymix", channels="rgb")
        km.setInput(0, main)        # A (mask=0) = original
        km.setInput(1, soft_sw)     # B (mask=1 / no mask) = corrected
        km.setInput(2, mprep)       # mask (alpha=1 when unconnected)
        km["mix"].setExpression("parent.mix")
        km["invertMask"].setExpression("[exists parent.input1] && parent.invertMask")

        out = nuke.nodes.Output(name="Output1"); out.setInput(0, km)

    k = group.addKnob
    k(nuke.Tab_Knob("user", "Match Blacks"))
    ch = nuke.Link_Knob("channels", "channels"); ch.setLink("%s.channels" % _GRADE)
    k(ch)

    pb = nuke.Double_Knob("pinBlack", "Pin Blacks"); pb.setRange(0, 1)
    pb.setValue(0.1); k(pb)

    fc = nuke.Color_Knob("FromColor", "Source Color"); fc.setValue([0, 0, 0]); k(fc)
    tc = nuke.Color_Knob("ToColor", "Target Color"); tc.setValue([0, 0, 0]); k(tc)

    b_neu = _btn("neutralise", "Neutralise", "neutralise")
    b_neu.setFlag(nuke.STARTLINE); k(b_neu)
    k(_btn("zero", "Zero blacks", "zero_blacks"))
    k(_btn("sample_src", "Sample source", "sample_source"))
    k(_btn("match_ref", "Match to reference", "match_reference"))

    cl = nuke.Boolean_Knob("clamp", "clamp to target"); cl.setValue(True)
    cl.setFlag(nuke.STARTLINE)
    cl.setTooltip("Clamp the lower end of the range to the Target Color.")
    k(cl)
    sf = nuke.Double_Knob("softness", "softness"); sf.setRange(0, 0.5)
    sf.setValue(0)
    sf.setTooltip("Feather the correction into the mids (0 = hard, as original).")
    k(sf)

    k(nuke.Text_Knob("div1", ""))
    up = nuke.Link_Knob("unpremult", "(un)premult by"); up.setLink("%s.unpremult" % _GRADE)
    k(up)
    iu = nuke.Link_Knob("invert_unpremult", "invert")
    iu.setLink("%s.invert_unpremult" % _GRADE); iu.clearFlag(nuke.STARTLINE); k(iu)
    mix = nuke.Double_Knob("mix", "mix"); mix.setRange(0, 1); mix.setValue(1); k(mix)
    im = nuke.Boolean_Knob("invertMask", "invert mask"); im.clearFlag(nuke.STARTLINE)
    k(im)

    k(nuke.Text_Knob("footer", "", _FOOTER))

    k(nuke.Tab_Knob("help_tab", "Help"))
    k(nuke.Text_Knob("help_text", "", _HELP_HTML))
    hb = _btn("help_btn", "Open help", "show_help"); hb.setFlag(nuke.STARTLINE)
    k(hb)
    k(nuke.Text_Knob("footer2", "", _FOOTER))

    if "knobChanged" in group.knobs():
        group["knobChanged"].setValue(
            "import pep_match_blacks; "
            "pep_match_blacks.on_knob_changed(nuke.thisNode(), nuke.thisKnob())")
    return group

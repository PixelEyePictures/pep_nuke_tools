"""PEP Marker Cleanup.

Automates the "channel-swap" tracking-marker removal technique, plus a
patch-fill mode for black / neutral markers.

Core idea: a coloured tracking marker on a backing screen almost always
dominates a single RGB channel. Copy a *clean* channel over the damaged one,
grade it back to the screen colour, then re-key the foreground so the patch
only lands on the screen, never on the actor.

The tool builds the full node network from a selected plate, ready for the
artist to refine the roto and grade.

Pixel Eye Pictures.
"""

import nuke

try:
    from PySide2 import QtWidgets
except ImportError:  # Nuke 15+/PySide6 fallback
    from PySide6 import QtWidgets


# --------------------------------------------------------------------------- #
# Presets: (damaged channel dominated by markers, clean donor channel,
#           needs a hue-key pre-grade before the swap)
# --------------------------------------------------------------------------- #
PRESETS = {
    "Green screen / warm markers (orange, red, yellow)": ("red", "blue", False),
    "Green screen / magenta markers": ("green", "blue", False),
    "Blue screen / green markers": ("green", "blue", True),
    "Blue screen / warm markers (orange, red)": ("red", "green", True),
    "Custom": ("red", "blue", False),
}

CHANNELS = ["red", "green", "blue"]


def _node_pos(base, dx=0, dy=0):
    return int(base[0] + dx), int(base[1] + dy)


def build_network(plate, damaged, donor, pre_grade):
    """Construct the marker-cleanup node tree fed by *plate*.

    damaged  : channel the markers dominate (gets overwritten)
    donor    : clean channel copied into the damaged one
    pre_grade: insert a HueKeyer -> Grade stage before the swap
    """
    if damaged == donor:
        raise ValueError("Damaged and donor channels must be different.")

    x, y = plate.xpos(), plate.ypos()
    col = 150  # column offset for the side branch

    # Anchor dot on the plate so we can branch from a single point.
    src = nuke.nodes.Dot(name="MC_src", xpos=_node_pos((x, y))[0] + 34,
                         ypos=y + 80)
    src.setInput(0, plate)

    upstream = src

    # -- Optional pre-grade (example 2: knock the contaminating colour down) --
    if pre_grade:
        huekey = nuke.nodes.HueKeyer(name="MC_preHueKey")
        huekey.setInput(0, upstream)
        huekey.setXYpos(src.xpos() - col, src.ypos() + 60)
        pregrade = nuke.nodes.Grade(name="MC_preGrade")
        pregrade.setInput(0, huekey)
        pregrade["channels"].setValue("rgb")
        # Dial the damaged channel's gain down so the marker stops bleeding
        # into the donor channel before the swap.
        idx = CHANNELS.index(damaged)
        pregrade["white"].setSingleValue(False)
        pregrade["white"].setValue(0.5, idx)
        pregrade["maskChannelInput"].setValue("alpha")
        pregrade.setXYpos(huekey.xpos(), huekey.ypos() + 60)
        upstream = pregrade

    # -- Roto mask around the markers (artist paints this) --
    roto = nuke.nodes.Roto(name="MC_MarkerMask")
    roto.setInput(0, upstream)
    roto["output"].setValue("alpha")
    roto.setXYpos(upstream.xpos(), upstream.ypos() + 80)
    roto["label"].setValue("PAINT marker regions here")

    # -- Shuffle: copy the clean donor channel over the damaged one --
    shuffle = nuke.nodes.Shuffle(name="MC_SwapChannel")
    shuffle.setInput(0, roto)
    shuffle[damaged].setValue(donor)          # out.<damaged> <- in.<donor>
    shuffle.setXYpos(roto.xpos(), roto.ypos() + 40)
    shuffle["label"].setValue("%s <- %s" % (damaged, donor))

    # -- Grade the swapped channel back to the backing-screen colour --
    grade = nuke.nodes.Grade(name="MC_MatchScreen")
    grade.setInput(0, shuffle)
    grade["channels"].setValue("rgb")
    grade["white"].setSingleValue(False)      # un-gang so artist tweaks one ch
    grade.setXYpos(shuffle.xpos(), shuffle.ypos() + 40)
    grade["label"].setValue("wipe & match the %s channel to screen" % damaged)

    # -- Restore the marker mask alpha onto the graded stream --
    copy = nuke.nodes.Copy(name="MC_CopyMask")
    copy.setInput(0, grade)
    copy.setInput(1, roto)
    copy["from0"].setValue("rgba.alpha")
    copy["to0"].setValue("rgba.alpha")
    copy.setXYpos(grade.xpos(), grade.ypos() + 40)

    # -- Key the foreground subject off the ORIGINAL plate --
    fgkey = nuke.nodes.Keyer(name="MC_FG_Key")
    fgkey.setInput(0, src)
    fgkey["operation"].setValue("luminance key")
    fgkey["output"].setValue("alpha")
    fgkey.setXYpos(src.xpos() + col, src.ypos() + 200)
    fgkey["label"].setValue("pull a quick FG matte")

    # -- Stencil the FG out of the patch so we never paint over the actor --
    # Nuke Merge inputs: index 0 = B, index 1 = A.
    stencil = nuke.nodes.Merge2(name="MC_StencilFG")
    stencil["operation"].setValue("stencil")
    stencil.setInput(1, fgkey)   # A = foreground matte
    stencil.setInput(0, copy)    # B = graded, mask-carrying patch
    stencil.setXYpos(copy.xpos(), copy.ypos() + 80)

    # -- Premult the finished patch by its alpha --
    premult = nuke.nodes.Premult(name="MC_PremultPatch")
    premult.setInput(0, stencil)
    premult.setXYpos(stencil.xpos(), stencil.ypos() + 40)

    # -- Merge the patch back over the original plate --
    over = nuke.nodes.Merge2(name="MC_MergeOverPlate")
    over["operation"].setValue("over")
    over.setInput(1, premult)  # A = patch
    over.setInput(0, plate)    # B = original plate
    over.setXYpos(int((premult.xpos() + plate.xpos()) / 2),
                  premult.ypos() + 80)

    # Backdrop to keep the branch tidy.
    bd = nuke.nodes.BackdropNode(name="MC_Backdrop")
    bd["label"].setValue("PEP Marker Cleanup\n%s <- %s" % (damaged, donor))
    bd["note_font_size"].setValue(28)
    bd["tile_color"].setValue(0x554433ff)
    left = min(n.xpos() for n in (src, roto, shuffle, fgkey, over)) - 60
    top = src.ypos() - 90
    right = max(n.xpos() for n in (src, fgkey)) + 200
    bottom = over.ypos() + 120
    bd["xpos"].setValue(left)
    bd["ypos"].setValue(top)
    bd["bdwidth"].setValue(right - left)
    bd["bdheight"].setValue(bottom - top)

    for n in nuke.selectedNodes():
        n["selected"].setValue(False)
    over["selected"].setValue(True)
    return over


def build_patch_network(plate, fill_size=40, grow=3):
    """Patch-fill network for BLACK / neutral markers (channel-swap can't do
    those). Luminance-key the dark markers, grow the matte, and fill the holes
    with blurred surrounding screen, then merge back over the plate.

    fill_size : Blur size used to smear surrounding screen into the holes.
    grow      : Dilate size to cover marker edges / anti-aliasing.
    """
    x, y = plate.xpos(), plate.ypos()

    src = nuke.nodes.Dot(name="MC_src", xpos=x + 34, ypos=y + 80)
    src.setInput(0, plate)

    # -- key the DARK markers (low luminance) --
    key = nuke.nodes.Keyer(name="MC_DarkKey")
    key.setInput(0, src)
    key["operation"].setValue("luminance key")
    key["output"].setValue("alpha")
    # keep low luminance (the dark markers); tune in the Viewer
    key["range"].setValue([0.0, 0.0, 0.08, 0.15])
    key.setXYpos(src.xpos(), src.ypos() + 60)
    key["label"].setValue("isolate the DARK markers (tune range)")

    # -- optional rough region limiter (artist paints; identity if empty) --
    roto = nuke.nodes.Roto(name="MC_Region")
    roto.setInput(0, key)
    roto.setXYpos(key.xpos(), key.ypos() + 40)
    roto["label"].setValue("(optional) limit to marker regions")

    # -- grow the matte to cover marker edges --
    dilate = nuke.nodes.Dilate(name="MC_Grow")
    dilate.setInput(0, roto)
    dilate["size"].setValue(grow)
    dilate.setXYpos(roto.xpos(), roto.ypos() + 40)

    # -- fill: blur the plate so surrounding screen smears over the holes --
    fill = nuke.nodes.Blur(name="MC_Fill")
    fill.setInput(0, src)
    fill["size"].setValue(fill_size)
    fill["channels"].setValue("rgb")
    fill.setXYpos(src.xpos() + 150, src.ypos() + 120)
    fill["label"].setValue("surrounding-screen fill")

    # -- carry the marker matte onto the fill, premult, merge over plate --
    copy = nuke.nodes.Copy(name="MC_CopyMatte")
    copy.setInput(0, fill)
    copy.setInput(1, dilate)
    copy["from0"].setValue("rgba.alpha")
    copy["to0"].setValue("rgba.alpha")
    copy.setXYpos(fill.xpos(), fill.ypos() + 60)

    premult = nuke.nodes.Premult(name="MC_PremultPatch")
    premult.setInput(0, copy)
    premult.setXYpos(copy.xpos(), copy.ypos() + 40)

    over = nuke.nodes.Merge2(name="MC_MergeOverPlate")
    over["operation"].setValue("over")
    over.setInput(1, premult)   # A = patch
    over.setInput(0, plate)     # B = original plate
    over.setXYpos(int((premult.xpos() + plate.xpos()) / 2),
                  premult.ypos() + 80)

    bd = nuke.nodes.BackdropNode(name="MC_Backdrop")
    bd["label"].setValue("PEP Marker Cleanup\nPatch fill (dark markers)")
    bd["note_font_size"].setValue(28)
    bd["tile_color"].setValue(0x335544ff)
    left = min(n.xpos() for n in (src, over)) - 60
    top = src.ypos() - 90
    right = max(n.xpos() for n in (src, fill)) + 200
    bottom = over.ypos() + 120
    bd["xpos"].setValue(left); bd["ypos"].setValue(top)
    bd["bdwidth"].setValue(right - left); bd["bdheight"].setValue(bottom - top)

    for n in nuke.selectedNodes():
        n["selected"].setValue(False)
    over["selected"].setValue(True)
    return over


def build_compare_combos(plate):
    """Build a labeled contact sheet of every channel-swap combo off the plate,
    so the artist can eyeball which swap neutralizes the markers. Scratch nodes
    the artist can delete after choosing."""
    x, y = plate.xpos(), plate.ypos()
    src = nuke.nodes.Dot(name="MC_cmp_src", xpos=x + 34, ypos=y + 80)
    src.setInput(0, plate)

    fmt = plate.format()
    tiles = []
    combos = [(d, s) for d in CHANNELS for s in CHANNELS if d != s]  # 6
    for i, (dmg, dnr) in enumerate(combos):
        sh = nuke.nodes.Shuffle(name="MC_cmp_%s_%s" % (dmg, dnr))
        sh.setInput(0, src)
        sh[dmg].setValue(dnr)
        sh.setXYpos(src.xpos() + (i % 3) * 120, src.ypos() + 60 + (i // 3) * 60)
        t = nuke.nodes.Text2(name="MC_cmplbl_%d" % i)
        t.setInput(0, sh)
        t["message"].setValue("%s <- %s" % (dmg, dnr))
        try:
            t["global_font_scale"].setValue(0.5)
            t["xjustify"].setValue("left"); t["yjustify"].setValue("top")
            t["box"].setValue([20, 20, fmt.width() - 20, fmt.height() - 20])
        except Exception:  # noqa: BLE001
            pass
        t.setXYpos(sh.xpos(), sh.ypos() + 30)
        tiles.append(t)

    cs = nuke.nodes.ContactSheet(name="MC_Compare")
    cs["width"].setValue(fmt.width() * 3)
    cs["height"].setValue(fmt.height() * 2)
    cs["rows"].setValue(2); cs["columns"].setValue(3)
    for i, t in enumerate(tiles):
        cs.setInput(i, t)
    cs.setXYpos(src.xpos(), src.ypos() + 260)
    cs["label"].setValue("Marker channel-swap compare\n(pick a combo, then Build)")

    bd = nuke.nodes.BackdropNode(name="MC_CompareBackdrop")
    bd["label"].setValue("PEP Marker Cleanup - Compare combos")
    bd["note_font_size"].setValue(24); bd["tile_color"].setValue(0x446633ff)
    left = src.xpos() - 60; top = src.ypos() - 90
    right = src.xpos() + 3 * 120 + 200; bottom = cs.ypos() + 120
    bd["xpos"].setValue(left); bd["ypos"].setValue(top)
    bd["bdwidth"].setValue(right - left); bd["bdheight"].setValue(bottom - top)

    for n in nuke.selectedNodes():
        n["selected"].setValue(False)
    cs["selected"].setValue(True)
    return cs


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
<h3>PEP Marker Cleanup</h3>
<p>Removes tracking markers by rebuilding the network for you. Two methods:</p>

<h4>Channel swap (coloured markers)</h4>
<p>A coloured marker usually blows out <b>one</b> RGB channel. Copy a clean
donor channel over that damaged channel, then grade it back to the screen
colour. Pick a <b>preset</b> or set the channels by hand:</p>
<ul>
<li><b>Green screen / warm markers</b> (orange, red, yellow) &rarr; damaged
<b>red</b>, donor <b>blue</b></li>
<li><b>Green screen / magenta markers</b> &rarr; damaged <b>green</b>, donor
<b>blue</b></li>
<li><b>Blue screen / green markers</b> &rarr; damaged <b>green</b>, donor
<b>blue</b> (+ pre-grade)</li>
<li><b>Blue screen / warm markers</b> &rarr; damaged <b>red</b>, donor
<b>green</b> (+ pre-grade)</li>
</ul>
<p>After building, wipe the <b>MC_MatchScreen</b> grade in the Viewer to match
the swapped channel to the backing, and paint the <b>MC_MarkerMask</b> roto
around the markers.</p>

<h4>Patch fill (black / neutral markers)</h4>
<p>Black markers have no dominant channel, so channel-swap can't help. This
mode luminance-keys the dark markers, grows the matte, and fills the holes
with surrounding screen (blurred plate). Tune <b>Fill blur size</b> and
<b>Matte grow</b>, and the <b>MC_DarkKey</b> range in the Viewer.</p>

<h4>Honest caveats</h4>
<ul>
<li><b>Blue screen + red markers</b> is only partial with channel-swap (red
markers also darken blue) &mdash; use the pre-grade and grade the blue back,
or switch to Patch fill.</li>
<li><b>Black / neutral markers</b>: Patch fill only.</li>
</ul>
<p style="color:#888">Pixel Eye Pictures</p>
"""


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class MarkerCleanupDialog(QtWidgets.QDialog):
    def __init__(self):
        super(MarkerCleanupDialog, self).__init__()
        self.setWindowTitle("PEP Marker Cleanup")
        self.setMinimumWidth(420)
        lay = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(
            "Builds a marker-removal network from the selected plate.\n"
            "Channel swap = coloured markers (dominate one channel).\n"
            "Patch fill = black / neutral markers."
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QtWidgets.QFormLayout()
        self.method = QtWidgets.QComboBox()
        self.method.addItems(["Channel swap (coloured markers)",
                              "Patch fill (black / neutral markers)"])
        form.addRow("Method:", self.method)

        # -- channel-swap controls --
        self.preset = QtWidgets.QComboBox()
        self.preset.addItems(PRESETS.keys())
        self.damaged = QtWidgets.QComboBox(); self.damaged.addItems(CHANNELS)
        self.donor = QtWidgets.QComboBox(); self.donor.addItems(CHANNELS)
        self.pre_grade = QtWidgets.QCheckBox("Add hue-key pre-grade")
        self.row_preset = form.addRow("Preset:", self.preset)
        form.addRow("Marker (damaged) channel:", self.damaged)
        form.addRow("Clean donor channel:", self.donor)
        form.addRow("", self.pre_grade)

        # -- patch-fill controls --
        self.fill_size = QtWidgets.QSpinBox(); self.fill_size.setRange(1, 500)
        self.fill_size.setValue(40)
        self.grow = QtWidgets.QSpinBox(); self.grow.setRange(0, 100)
        self.grow.setValue(3)
        form.addRow("Fill blur size:", self.fill_size)
        form.addRow("Matte grow:", self.grow)
        lay.addLayout(form)
        self._form = form

        btns = QtWidgets.QHBoxLayout()
        self.help_btn = QtWidgets.QPushButton("Help")
        self.compare_btn = QtWidgets.QPushButton("Compare combinations")
        self.build_btn = QtWidgets.QPushButton("Build Network")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        btns.addWidget(self.help_btn)
        btns.addWidget(self.compare_btn)
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.build_btn)
        lay.addLayout(btns)
        lay.addWidget(_pep_footer())

        self.method.currentIndexChanged.connect(self._sync_method)
        self.preset.currentTextChanged.connect(self._apply_preset)
        self.build_btn.clicked.connect(self._build)
        self.cancel_btn.clicked.connect(self.reject)
        self.compare_btn.clicked.connect(self._compare)
        self.help_btn.clicked.connect(lambda: _show_help(self, "Marker Cleanup - Help", _HELP_HTML))
        self._apply_preset(self.preset.currentText())
        self._sync_method()

    def _is_swap(self):
        return self.method.currentIndex() == 0

    def _sync_method(self, *args):
        swap = self._is_swap()
        for w in (self.preset, self.damaged, self.donor, self.pre_grade):
            w.setEnabled(swap)
        for w in (self.fill_size, self.grow):
            w.setEnabled(not swap)
        self.compare_btn.setEnabled(swap)   # channel-swap only

    def _compare(self):
        sel = nuke.selectedNodes()
        plate = sel[0] if sel else None
        if plate is None:
            nuke.message("Select the plate (Read) node first.")
            return
        try:
            build_compare_combos(plate)
            self.accept()
            if hasattr(nuke, "zoomToFitSelected"):
                nuke.zoomToFitSelected()
        except Exception as exc:  # noqa: BLE001
            nuke.message("Compare error:\n%s" % exc)

    def _apply_preset(self, name):
        damaged, donor, pre = PRESETS[name]
        self.damaged.setCurrentText(damaged)
        self.donor.setCurrentText(donor)
        self.pre_grade.setChecked(pre)

    def _build(self):
        sel = nuke.selectedNodes()
        plate = sel[0] if sel else None
        if plate is None:
            nuke.message("Select the plate (Read) node first.")
            return
        try:
            if self._is_swap():
                damaged = self.damaged.currentText()
                donor = self.donor.currentText()
                if damaged == donor:
                    nuke.message("Damaged and donor channels must differ.")
                    return
                build_network(plate, damaged, donor, self.pre_grade.isChecked())
            else:
                build_patch_network(plate, self.fill_size.value(),
                                    self.grow.value())
            self.accept()
            if hasattr(nuke, "zoomToFitSelected"):
                nuke.zoomToFitSelected()
        except Exception as exc:  # noqa: BLE001
            nuke.message("Marker Cleanup error:\n%s" % exc)


_dialog = None


def launch_marker_cleanup():
    """Menu entry point."""
    global _dialog
    try:
        _dialog = MarkerCleanupDialog()
        _dialog.show()
    except Exception as exc:  # noqa: BLE001
        nuke.message("Marker Cleanup failed to launch:\n%s" % exc)

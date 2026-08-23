# PEP Nuke Tools

Nuke gizmos and tools from **Pixel Eye Pictures**. Free to use and modify
under the GPL-3.0 license (see `LICENSE`).

**Nuke 14+** — built and tested in Nuke 14 (Python 3; PySide2 with a PySide6
fallback for Nuke 15+).

---

## Preview

**CornerPin → Matrix** — drive a Roto/paint from a corner pin so it follows the plate:

![CornerPin to Matrix](images/cornerpin_follow.png)

**Fringe Fix** — clamp coloured edge fringing:

![Fringe Fix](images/fringe_before_after.png)

**Marker Cleanup** — remove tracking markers (patch-fill mode shown):

![Marker Cleanup](images/marker_before_after.png)

---

## Tools

| Tool | Type | What it does |
|------|------|--------------|
| **CornerPin to Matrix** | gizmo `PEP_CornerPinMatrix` | Convert a CornerPin's corners into a 4x4 matrix and paste it into a Roto / RotoPaint / CornerPin2D so the shape follows the pin. Static or baked over a range. |
| **CornerPin to Matrix v2** | gizmo `PEP_CornerPinMatrix_v2` | Same, plus a **transpose** toggle and a **live expression-link** (target updates as the corners move) for CornerPin2D targets. |
| **CornerPin to Matrix (panel)** | Python | Dialog version of the above (no gizmo node). |
| **Fringe Fix** | gizmo `PEP_FringeFix` | Kill coloured edge fringing (red/blue/magenta) by clamping the channel to the average of the other two, or realign chromatic aberration with a per-channel chroma shift. Mix control; mask externally if needed. |
| **Marker Cleanup** | Python | Tracking-marker removal. **Channel swap** for coloured markers (green/blue screen, orange/red/green/magenta) and **Patch fill** for black/neutral markers (luminance-key → grow → surrounding-screen fill). Builds the network for you. |

---

## Install

### Automatic (recommended)

Add the `gizmos/pep_tools` folder to your `NUKE_PATH`, or add this line to
your `~/.nuke/init.py`:

```python
import nuke
nuke.pluginAddPath('/path/to/pep_nuke_tools/gizmos/pep_tools')
```

Nuke auto-loads the gizmos (available under **Tab**) and adds a **PEP Tools**
menu. Restart Nuke after installing.

### Manual (studio setup)

Copy the `gizmos/pep_tools` folder into any location already on your
`NUKE_PATH`. See Foundry's guides on *Loading Gizmos, Plugins, Scripts* and
*Custom Menus and Toolbars*.

---

## Usage — CornerPin to Matrix

1. Get your corner-pin data (track it, or animate a `CornerPin2D`'s `to` corners).
2. **Tab → `PEP_CornerPinMatrix`** (or **PEP Tools → CornerPin to Matrix**).
3. Set / link the gizmo's `to` / `from` corners.
4. Draw your Roto / RotoPaint.
5. Select the **gizmo + your target**, then on the **Matrix** tab:
   - **Paste matrix into selected node** — bakes the matrix (tick *bake* +
     set *first/last* for animated pins).
   - **v2 → Live link** — expression-links the target to the gizmo so it
     updates as the corners change (CornerPin2D targets only).

The controller follows the pin. If it ever moves the wrong way, toggle
**invert** and re-apply.

> Note: live-link is not available for Roto/RotoPaint (their shape transform
> is curve-based and cannot be expression-linked) — use **Paste / bake** there.

Every gizmo also has a **Help** tab in its properties panel.

---

## Examples

### Stick a paint/roto to a tracked surface
1. Track 4 points on the surface → **Tracker → CornerPin** (creates a `CornerPin2D`).
2. Tab → **`PEP_CornerPinMatrix_v2`**. Link its `from`/`to` to the CornerPin (copy/paste the corner values, or expression-link).
3. Paint your fix on frame 1 with a **RotoPaint** drawn over the reference frame.
4. In the gizmo's **Matrix** tab: set **target node** = your RotoPaint (or *Set from selected*), tick **bake**, set **first/last** to the shot range, press **Paste matrix into target**.
5. Scrub — the paint now rides the corner pin. Wrong direction? toggle **invert**, paste again.

### Live-updating screen replacement
1. Tab → **`PEP_CornerPinMatrix_v2`**, set/link its corners.
2. Add a **CornerPin2D** for your insert, set **target node** to it, press **Live link into target**.
3. Now tweaking the gizmo's corners updates the insert live — no re-baking.

### Kill a blue/purple edge fringe
1. Tab → **`PEP_FringeFix`** after the offending node.
2. **method** = *Channel clamp*, **channel** = *blue* (or the fringing channel), **mix** = 1.
3. Still hot on hard edges? drop **mix**, or mask the node with a garbage matte so it only touches the fringe.

### Realign chromatic aberration
1. **`PEP_FringeFix`**, **method** = *Chroma shift*, pick the **channel** that's off, nudge **chroma scale** (e.g. `1.001` / `0.999`) until the channels register.

### Remove orange markers on green screen
1. Select the plate. **PEP Tools → Marker Cleanup** → **Channel swap** → preset *Green screen / warm markers*.
2. Refine the `MC_MarkerMask` roto around the markers and wipe the `MC_MatchScreen` grade to match the screen.

### Remove black/neutral markers
1. Select the plate. **Marker Cleanup** → **Patch fill**.
2. Tune the `MC_DarkKey` range to isolate the dark markers; raise **fill blur size** / **grow** until the holes fill with surrounding screen.

---

## License

GPL-3.0 (c) Pixel Eye Pictures. See `LICENSE`.

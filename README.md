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

---

## License

GPL-3.0 (c) Pixel Eye Pictures. See `LICENSE`.

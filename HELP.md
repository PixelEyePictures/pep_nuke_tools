# PEP Nuke Tools — Help

The same guidance is available inside Nuke (a **Help** tab on the gizmos, a
**Help** button on the panels). This page mirrors it so you can read it without
opening Nuke.

Install: add `gizmos/pep_tools` to your `NUKE_PATH` (see the README). Gizmos are
Tab‑createable; the Python tools live under the **PEP Tools** menu.

---

## CornerPin to Matrix  (gizmo `PEP_CornerPinMatrix`)

Turns a CornerPin's corners into a 4×4 matrix and pastes it into another node,
so a **Roto / RotoPaint** follows the pin (or a CornerPin reproduces it).

1. Get corner‑pin data (track it, or animate a `CornerPin2D`'s `to` corners).
2. Set / link the gizmo's `to` and `from` corners.
3. Select the **gizmo + your target** (Roto / RotoPaint / CornerPin2D).
4. On the **Matrix** tab press **Paste matrix into selected node**. Tick
   **bake** + set first/last for tracked (animated) pins.

- **invert** — flip the direction if the target moves the wrong way.
- **Targets:** CornerPin2D (image warp) and Roto/RotoPaint (shape follow).
  GridWarp/SplineWarp are freeform and can't take a global matrix.

## CornerPin to Matrix v2  (gizmo `PEP_CornerPinMatrix_v2`)

Everything above, plus:
- **target node** field (+ *Set from selected*) — write to a named node, no
  reliance on selection.
- **Live link into target** — expression‑links the target so it updates as the
  corners move (CornerPin2D targets only; Roto uses Paste).
- **swap rows/columns (transpose)** — only if a matrix pasted from another app
  comes in mirrored.
- Live **matrix** readout.

> The panel version (**PEP Tools → CornerPin to Matrix (panel)**) does the same
> without a node in the graph.

---

## Fringe Fix  (gizmo `PEP_FringeFix`)

Cleans coloured edge fringing, or realigns chromatic aberration.

- **Channel clamp (fringe)** — clamps the chosen **channel** to the average of
  the other two wherever it over‑shoots. Kills red / blue / magenta edge
  fringing. Pick the fringe channel (blue is most common) and dial **mix**.
- **Chroma shift (realign)** — scales one channel by a fraction of a pixel
  about centre to re‑register the channels. Set **channel** and **chroma scale**
  (e.g. `1.001` / `0.999`).

Apply only where needed: mask the node with a garbage matte.

---

## Marker Cleanup  (PEP Tools → Marker Cleanup)

Removes tracking markers by building the network for you.

**Channel swap (coloured markers)** — a coloured marker blows out one RGB
channel; copy a clean donor channel over it, then grade back to screen. Presets:

| Screen / marker | damaged → donor |
|---|---|
| Green / warm (orange, red, yellow) | red ← blue |
| Green / magenta | green ← blue |
| Blue / green | green ← blue (+ pre‑grade) |
| Blue / warm (orange, red) | red ← green (+ pre‑grade) |

After building, wipe **MC_MatchScreen** in the Viewer and paint the
**MC_MarkerMask** roto around the markers. **Compare combinations** builds a
contact sheet of every swap so you can pick the best.

**Patch fill (black / neutral markers)** — channel‑swap can't do black markers;
this luminance‑keys the dark markers, grows the matte, and fills with
surrounding screen. Tune **Fill blur size**, **Matte grow**, and the
**MC_DarkKey** range.

Caveats: blue + red is only partial with channel‑swap (use pre‑grade / grade
the blue back, or Patch fill); black / neutral markers → Patch fill only.

---

## Read Node Manager  (PEP Tools → Read Node Manager)

Manage every Read / ReadGeo from one window.

- **Scan for** Read (Images) / ReadGeo (3D); **Refresh List** to rescan.
- **Tick** rows (or **Check All / Uncheck All**) to batch‑select.
- **Disable / Enable Selected** — mute or wake the ticked nodes.
- **Search/Replace Paths** — relink the ticked nodes:
  - **Selected path → Find / Replace** — drop a row's path into a field.
  - **Preview affects** All rows or Selected (highlighted) rows only.
  - **Preview Find/Replace** updates the New paths; **Reset** reverts.
  - Or **double‑click a path cell** and edit it by hand.
  - **Apply to nodes** writes only the changed paths.

**Move a script to a new shot:** Check All → Search/Replace → Find `sh045`
Replace `sh052` (repeat for the version) → Apply. Match a distinctive token,
not a bare number.

---

## TagRename  (PEP Tools → TagRename)

Rename the actual **rendered files on disk** and relink the node — fix a typo,
missing dot, or wrong version without leaving Nuke or re‑rendering.

1. Select the Read/Write node(s). Single file, whole sequence, and multiple
   nodes (batch) are handled automatically.
2. Type **Find / Replace** (applied to the file name; folders untouched).
   Toggle **Case sensitive**.
3. Check the **Old → New** preview and file counts.
4. **Apply** renames every matching file on disk and updates the node path.

Safe: rename‑only (never deletes), never overwrites an existing file, and
reports missing / locked frames.

---

_Pixel Eye Pictures — GPL‑3.0._

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

---

## CornerPin to Matrix v3  (gizmo `PEP_CornerPinMatrix_v3`)

Everything in v2, plus **edge offsets**:
- **top / bottom / left / right** (pixels) — push each edge of the pinned quad
  out (+) or in (−) past the tracked corners for **overscan / edge bleed**,
  applied to the baked matrix. Leave at 0 for none.

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
- **Media** column flags each node's files on disk: **OK (n)**, **MISSING x/n**
  frames (orange), or **OFFLINE** (red) — instantly see what's broken in an
  inherited script.
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

## Rename & Relink  (PEP Tools → Rename & Relink)

Rename the actual **rendered files on disk** and relink the node — fix a typo,
wrong version, or name a shot without leaving Nuke or re‑rendering. Single file,
whole sequence, and multiple nodes (batch) are handled automatically.

1. Select the Read/Write node(s) → **Refresh from selection**.
2. Set the new name in any of these ways:
   - **New name** column — double‑click a row and type it (keep `####`).
   - **Name template** — one mask for all rows, e.g. `shot010_comp_v02.####.exr`.
   - **Find / Replace** (+ **Case sensitive**) — batch edit names.
3. **Frames:** All / Range (first–last) / Current — rename a subset.
4. **Renumber** (Start / Step) — recount frames into the new name, or leave off
   to keep the original frame numbers.
5. Check the **Old → New** preview and **#files**, then **Apply**.

Safe: rename‑only (never deletes), never overwrites, reports missing / locked
frames. A **partial** frame rename leaves the node on the old name (a sequence
can't have two names).

## TrackPin  (PEP Tools → TrackPin)

A tidy stabilize / match‑move CornerPin rig (builds a group).

1. Put a 4‑point track into the **to** corners — paste it, or set **source
   node** to a CornerPin exported from your Tracker and press **Fill corners
   from node**.
2. Set the **reference frame** (or **Set to current**).
3. **mode = Match Move** (a held still rides the track) or **Stabilize** (lock
   the plate to the reference frame). Press **Apply**.
4. **Reset** returns the corners to the raw track.

Extras: **keep edges** (don't crop the stabilized plate), **Bake to keyframes**
(freeze the corners so it renders without the live expressions), and **Send to
Matrix** (bake the pin's 4×4 onto a selected Roto / RotoPaint / CornerPin2D).
Round trip: Stabilize → paint on the locked frame → switch to Match Move → Apply.

---

## Clipping Degrain  (PEP Tools → Clipping Degrain)

Denoise cleanly against crushed blacks / blown whites (builds a group).

1. Turn on **Show clip** — pixels still clipped after the lift flag white.
2. Raise **Remove clip (blacks / whites)** until the white clears (you're
   lifting the signal off the clip point).
3. Turn off **Show clip**, press **Open denoiser controls**, set up your
   denoiser. Pick the base denoiser (Median / Nuke Denoise), or tick **Use Neat
   Video** if it's installed (auto‑detected, any version).

**Mode** protects Blacks, Whites, or Both. The pre‑ and post‑grade are exact
inverses, so with the denoiser idle the image is unchanged — the tool only ever
adds the denoise itself.

---

## Gradient  (PEP Tools → Gradient)

Multi‑stop background / gradient generator with shapes, depth fog and noise
break‑up (builds a group, input‑less unless you use Depth).

1. Set **number of stops** (1–8) and each stop's **colour** + **position**, or
   edit the **curve (freeform)** knob directly for an unlimited multi‑stop ramp.
2. Pick a **shape**: Linear (drag **RampFrom0 / Rampto1**), Radial / Box /
   Diamond (set **centre** + **radius**; tick **lock centre** so you don't nudge
   it), or **Depth**.
3. **Depth** mode: plug a depth pass into the input and set **depth near / far**
   — the stops become a depth fog.
4. **Break‑up**: raise **noise amount** to disturb the gradient (kills banding,
   makes fog patchy); **noise blur** softens the noise, **smooth** blurs the
   final result.
5. **Output mode**: *Generate* outputs the gradient itself; *Grade plate* lays
   the gradient over the image on the input as a graduated colour wash — choose a
   **blend** (over / multiply / screen / overlay / soft‑light / plus) and
   **opacity**. Handy for sky grads, day‑for‑night falloff and edge vignettes.

---

## Match Blacks  (PEP Tools → Match Blacks)

Match / neutralise / crush the low range only (builds a group).

1. Set **Pin Blacks** to the top of the range you want to affect.
2. Set **Source Color** (the cast you have) and **Target Color** (what you
   want) — use the colour knob's eyedropper on the viewer.
3. Or press **Neutralise** (kill the cast), **Zero blacks** (crush to black), or
   **Match to reference** (connect a reference plate to the **Reference** input;
   it samples both black levels and fills Source / Target).
4. **Softness** feathers the correction into the mids. **Clamp** holds the low
   end to the Target. Mask input + **mix** as usual.

## Spot Remover  (PEP Tools → Spot Remover)

Fast, smooth spot / marker fill (builds a group).

1. Feed the **plate** into input 1 and a **matte** over the spot into input 2
   (painted alpha or a white blob both work).
2. Raise **Fill Blur Size** until the hole fills from the surrounding pixels.
3. **Sample Size** = how far outside the spot to sample from; **Edge Blur** =
   softness on the matte edge; **Blur Angle** = directional bias; **mix** =
   blend against the original.
4. **Hold‑out mask (input 3):** connect a mask and set **mask mode** — *Limit
   fill to mask* (the fill only lands inside it) or *Protect* (keep the fill out
   of it, e.g. an actor). No mask connected = applies everywhere.
5. **Follow a track:** put a Tracker (match‑move) or a Transform exported from it
   in the **tracker** field (or *Set from selected*) and press **Link tracker** —
   the matte and the fill ride the track for the whole shot. *Unlink* resets it.

The surrounding pixels are premultiplied and spread inward with an exponential
blur, then keyed back over the spot. The same engine powers Marker Cleanup's
**Smooth fill** mode, which drives it from a keyed marker matte.

## Script Doctor  (PEP Tools → Script Doctor)

Rescue a `.nk` that won't open or crashes on load. It works **completely
offline** — it never opens the scene. It reads the script as **text** and writes
safe, openable copies next to it; the **original is never modified**.

1. Set **Script** to the crashing `.nk` — Browse, or **drag it onto the panel**.
   (You can also point it at a folder to batch a whole directory.)
2. Leave the **rescue steps** ticked (all on by default) or untick any you don't
   want, then press **Rescue**.
3. A folder `<script>_doctor` is created next to the original, containing the
   **report** (`…_doctor_report.txt`, read this first), an untouched
   **original copy**, one **rescued `.nk` per step**, a **paused launcher**
   (`open_paused_….bat`, opens Nuke with `--pause` so nothing evaluates), and any
   **autosaves/backups** found nearby.
4. Open the report and work **down the recovery order**. If Nuke **crashes the
   instant you open the scene** (before you can do anything), start with
   **`rescued_safe_mode.nk`** — it removes Viewers, strips callbacks, kills
   postage thumbnails and **neutralizes BlinkScript** all at once. If the scene
   has BlinkScript nodes, **`rescued_no_blink.nk`** is the targeted fix: a
   BlinkScript's kernel **compiles the moment the GUI opens it**, so a bad kernel
   crashes Nuke on load and *disabling the node does not help* (Nuke still builds
   it) — this turns them into NoOps. Then work through the paused launcher,
   no-Viewers, no-callbacks, disable-all, and so on; each rescued copy isolates
   one class of load crash (Viewer eval, callback, corrupt Roto, heavy node,
   BlinkScript compile, missing plugin, postage-stamp thumbnail, stereo/multi-
   Viewer, stray non-ASCII), with a bisect pass to narrow which half holds the
   culprit.

**Target specific node types.** Press **Analyze script** to list every node type
and its count (heavy and plugin types are pre-ticked). Tick what you suspect,
then **Disable ticked** or **Remove ticked** for a surgical rescue.

**Match nodes.** Already know the offender? In the **Match nodes** box, enter a
name (e.g. `Blur7`) or a label, choose **node name** or **any knob value**, and
**disable / disconnect / remove** just the matches (plain text or regex). Writes
one targeted copy and lists every node it touched.

**Crash log (optional).** Drop the crash log from the session that died onto the
panel (or into the **Crash log** field). Script Doctor scans it for the node it
crashed on and adds a targeted `rescued_from_crashlog.nk`. A dropped `.nk` sets
Script; any other file sets the Crash log.

**No install needed.** For a locked-down workstation, the standalone
[paste edition](docs/PEP_ScriptDoctor_paste.py) runs from Nuke's Script Editor
(or any Python 3) with the same engine — toggle the rescues at the top and run.

---

_Pixel Eye Pictures — GPL‑3.0._

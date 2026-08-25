# Changelog

## Unreleased
- **Spot Remover**: fast, smooth exponential-blur spot / marker fill (plate +
  matte inputs) with Fill Blur / Edge Blur / Sample Size / Blur Angle; reusable
  engine.
- **Marker Cleanup**: new **Smooth fill (Spot Remover)** mode — fills the keyed
  marker matte with the Spot Remover engine instead of a single blur.
- **TrackPin**: stabilize / match‑move CornerPin rig — fill corners from a
  Tracker's CornerPin, reference frame, Match Move / Stabilize, keep edges,
  bake to keyframes, and Send to Matrix.
- **Clipping Degrain**: denoise against crushed blacks / blown whites with a
  swappable, no‑lock‑in denoiser (Median / Nuke Denoise / Neat Video
  auto‑detected); Blacks / Whites / Both mode; lossless when idle.
- **Gradient**: multi‑stop background generator — up to 4 colour stops; Linear /
  Radial / Box / Diamond / Depth shapes; depth‑fog mode; noise break‑up with
  blur/smooth controls and a lockable centre handle.
- **Match Blacks**: match / neutralise / crush the low range only — Source→Target
  remap with Neutralise, Zero blacks, Match to reference, and Softness.
- Footer: only **GitHub** is a link now; "Pixel Eye Pictures" is plain text.
- Fix: CornerPin and Marker Cleanup panels import `QtCore` (footer alignment).

- **Rename & Relink** (was TagRename): name template, Find/Replace, per‑node
  editing, **frame scope** (all / range / current) and **renumber** (start/step);
  works on Read & Write; partial renames stay safe.
- **Read Node Manager**: **Media** column — OK / MISSING x/n / OFFLINE detection.
- Every panel tool now shows a **Pixel Eye Pictures | GitHub** footer.

## v1.0
- **CornerPin to Matrix** gizmo (`PEP_CornerPinMatrix`): convert a CornerPin's
  corners to a 4x4 matrix and paste into Roto / RotoPaint / CornerPin2D;
  static or baked over a frame range; invert option.
- **CornerPin to Matrix v2** gizmo (`PEP_CornerPinMatrix_v2`): adds a
  **transpose** toggle and a **live expression-link** for CornerPin2D targets.
- **CornerPin to Matrix (panel)**: dialog version of the tool.
- **Marker Cleanup**: tracking-marker removal network builder with two modes -
  **Channel swap** (coloured markers) and **Patch fill** (black / neutral
  markers: luminance-key -> grow -> surrounding-screen fill).
- **Read Node Manager** (`pep_read_manager`): list/enable/disable all Reads and
  batch-relink paths (find/replace with scope, or per-node edit).
- **TagRename** (`pep_tagrename`): rename rendered files on disk (single /
  sequence / batch) and relink the node; rename-only, previews, no overwrite.
- **Marker Cleanup**: "Compare combinations" button (contact sheet of every
  channel swap so you can pick the best).
- **Fringe Fix** gizmo (`PEP_FringeFix`): channel-clamp de-fringe + chroma-shift
  realign, per selectable channel, with a mix control.
- **Help** in every tool (Help tab on gizmos; Help button on the panels).
- v2 gizmo: explicit **target node** field + **Set from selected**.

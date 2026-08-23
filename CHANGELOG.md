# Changelog

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
- **Fringe Fix** gizmo (`PEP_FringeFix`): channel-clamp de-fringe + chroma-shift
  realign, per selectable channel, with a mix control.
- v2 gizmo: explicit **target node** field + **Set from selected**.

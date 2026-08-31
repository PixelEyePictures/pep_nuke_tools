"""PEP Nuke Tools - menu registration.

Auto-sourced by Nuke when this folder is on NUKE_PATH. Registers the
"PEP Tools" menu with the gizmos and Python tools in this package.
"""
import nuke

_m = nuke.menu("Nuke").addMenu("PEP Tools")
_m.addCommand("CornerPin to Matrix (gizmo)",
              "nuke.createNode('PEP_CornerPinMatrix')")
_m.addCommand("CornerPin to Matrix v2 (gizmo)",
              "nuke.createNode('PEP_CornerPinMatrix_v2')")
_m.addCommand("CornerPin to Matrix v3 (gizmo)",
              "nuke.createNode('PEP_CornerPinMatrix_v3')")
_m.addCommand("Fringe Fix (gizmo)",
              "nuke.createNode('PEP_FringeFix')")
_m.addCommand("CornerPin to Matrix (panel)",
              "import pep_cornerpin_matrix as pm; pm.launch_cornerpin_matrix()")
_m.addCommand("TrackPin (stabilize / match-move)",
              "import pep_trackpin as tp; tp.build_trackpin()")
_m.addCommand("Clipping Degrain",
              "import pep_clipping_degrain as cd; cd.build_clipping_degrain()")
_m.addCommand("Gradient (multi-stop / depth fog)",
              "import pep_gradient as pg; pg.build_gradient()")
_m.addCommand("Match Blacks",
              "import pep_match_blacks as mb; mb.build_match_blacks()")
_m.addCommand("Spot Remover",
              "import pep_spot_remover as sr; sr.build_spot_remover()")
_m.addCommand("Marker Cleanup",
              "import pep_marker_cleanup as mc; mc.launch_marker_cleanup()")
_m.addCommand("Read Node Manager",
              "import pep_read_manager as rm; rm.launch_read_manager()")
_m.addCommand("Rename & Relink (on disk)",
              "import pep_tagrename as tr; tr.launch_tagrename()")
_m.addCommand("Script Doctor (rescue a .nk)",
              "import pep_script_doctor_ui as sd; sd.launch()")

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
_m.addCommand("Fringe Fix (gizmo)",
              "nuke.createNode('PEP_FringeFix')")
_m.addCommand("CornerPin to Matrix (panel)",
              "import pep_cornerpin_matrix as pm; pm.launch_cornerpin_matrix()")
_m.addCommand("Marker Cleanup",
              "import pep_marker_cleanup as mc; mc.launch_marker_cleanup()")
_m.addCommand("Read Node Manager",
              "import pep_read_manager as rm; rm.launch_read_manager()")
_m.addCommand("TagRename (rename on disk)",
              "import pep_tagrename as tr; tr.launch_tagrename()")

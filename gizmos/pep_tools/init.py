"""PEP Nuke Tools - init.

Ensures this folder is importable so the gizmos' Python callbacks
(`import pep_cornerpin_matrix`, `import pep_marker_cleanup`) resolve.
When the folder is on NUKE_PATH this is already handled, but adding it
explicitly makes manual installs and non-standard setups robust.
"""
import os
import sys
import nuke

_here = os.path.dirname(os.path.realpath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
nuke.pluginAddPath(_here)

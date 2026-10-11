#!/usr/bin/env bash
# Install printlib's Python deps in Claude Code cloud sessions.
set -euo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"
python3 -c "import manifold3d, trimesh, shapely, networkx, matplotlib, yaml, HersheyFonts, astropy, pygeomag" 2>/dev/null && exit 0
pip install -q -r requirements.txt >/dev/null 2>&1 || pip install -q --break-system-packages -r requirements.txt

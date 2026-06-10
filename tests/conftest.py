import os
import sys

# Ensure the repo root is importable so `shared`, `agent`, `retrieval`,
# `mcp_server` packages resolve when running pytest from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

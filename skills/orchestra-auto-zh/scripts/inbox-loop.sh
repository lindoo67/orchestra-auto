#!/bin/bash
# Stable entry point; the implementation uses the standard library for file locking,
# atomic writes and child-process reaping.
set -euo pipefail
exec python3 "$(dirname "$0")/inbox-loop.py" "$@"

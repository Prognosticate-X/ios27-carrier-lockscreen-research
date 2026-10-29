#!/usr/bin/env bash
# Run the locally deployed REA CLI with the local Node, ps shim and Ghidra.
#
# The ps shim is required because the DSH workspace sandbox denies /bin/ps;
# REA's process-ownership cleanup needs a process table. Ghidra 12.1.x is used
# because Hopper launches require a macOS Automation grant that the sandbox
# cannot provide non-interactively.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REA_BIN="$ROOT/.tools/rea-cli/node_modules/.bin/rea"

if [[ ! -x "$REA_BIN" ]]; then
  echo "REA is not installed under .tools/rea-cli. See docs/EN/04_research_handoffs/2026-10-28_next-research-roadmap.md (Track 0/A)." >&2
  exit 1
fi

export PATH="$ROOT/.tools/bin:$ROOT/.tools/node/bin:$PATH"
export GHIDRA_INSTALL_DIR="${GHIDRA_INSTALL_DIR:-$ROOT/.tools/ghidra_12.1.4_PUBLIC}"

exec "$REA_BIN" "$@"

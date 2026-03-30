#!/usr/bin/env bash
# Run HackingTool from this repo with dev mode and a local virtualenv.
# Venv search order: venv-dillons-clapped → .venv → venv
# Safe when invoked via symlink (e.g. ~/.local/bin/hackingtool).
set -euo pipefail

if [[ -n "${HACKINGTOOL_ROOT:-}" ]]; then
  ROOT="$(cd "$HACKINGTOOL_ROOT" && pwd)"
else
  _SCRIPT_REAL="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${BASH_SOURCE[0]}")"
  ROOT="$(cd "$(dirname "$_SCRIPT_REAL")" && pwd)"
fi
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

ACTIVATE=""
for name in "venv-dillons-clapped" ".venv" "venv"; do
  if [[ -f "$ROOT/$name/bin/activate" ]]; then
    ACTIVATE="$ROOT/$name/bin/activate"
    break
  fi
done

if [[ -z "$ACTIVATE" ]]; then
  echo "[hackingtool-local] No virtualenv found. Create one, e.g.:" >&2
  echo "  cd \"$ROOT\" && python3 -m venv venv-dillons-clapped && source venv-dillons-clapped/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ACTIVATE"
export HACKINGTOOL_DEV="${HACKINGTOOL_DEV:-1}"
exec python3 "$ROOT/hackingtool.py" "$@"

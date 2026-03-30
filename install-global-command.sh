#!/usr/bin/env bash
# Same behavior as myenv/hackingtool/install-global-command.sh (kept in sync).
# Optional: HACKINGTOOL_GLOBAL_LAUNCH_ROOT=/path/to/other/checkout ./install-global-command.sh
set -euo pipefail
_SCRIPT_REAL="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "$_SCRIPT_REAL")" && pwd)"
REPO_WRAPPER="$ROOT/hackingtool-local.sh"
BIN="${HOME}/.local/bin"
SHARE_DIR="${HOME}/.local/share/hackingtool"
mkdir -p "$BIN" "$SHARE_DIR"
chmod +x "$REPO_WRAPPER"
cp -f "$REPO_WRAPPER" "$SHARE_DIR/hackingtool-local.sh"
chmod +x "$SHARE_DIR/hackingtool-local.sh"
SHARE_WRAPPER="$SHARE_DIR/hackingtool-local.sh"
WRAPPER="$BIN/hackingtool"
rm -f "$WRAPPER"
if [[ -n "${HACKINGTOOL_GLOBAL_LAUNCH_ROOT:-}" ]]; then
  CHECKOUT="$(cd "$HACKINGTOOL_GLOBAL_LAUNCH_ROOT" && pwd)"
  cat >"$WRAPPER" <<EOF
#!/usr/bin/env bash
export HACKINGTOOL_ROOT="$CHECKOUT"
exec bash "$SHARE_WRAPPER" "\$@"
EOF
  chmod +x "$WRAPPER"
  echo "Installed: $WRAPPER"
  echo "  HACKINGTOOL_ROOT=$CHECKOUT"
  echo "  launcher=$SHARE_WRAPPER (synced from $REPO_WRAPPER)"
else
  ln -sf "$REPO_WRAPPER" "$WRAPPER"
  echo "Installed: $WRAPPER -> $REPO_WRAPPER"
  echo "  (also mirrored to $SHARE_WRAPPER for optional remote-root installs)"
fi
echo "Ensure ~/.local/bin is on your PATH (add to ~/.bashrc if needed):"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""

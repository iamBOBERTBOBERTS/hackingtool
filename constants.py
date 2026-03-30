from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil as _shutil

# ── Repository ────────────────────────────────────────────────────────────────
REPO_OWNER   = "Z4nzu"
REPO_NAME    = "hackingtool"
REPO_URL     = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"
REPO_WEB_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"

# Directory containing this file (project / install root)
REPO_ROOT = Path(__file__).resolve().parent


def resolve_default_tools_dir() -> Path:
    """
    Default directory for git clones and tool installs.

    Priority:
      1. HACKINGTOOL_TOOLS_DIR — explicit path (any layout)
      2. HACKINGTOOL_DEV=1 — <repo>/tools when running from a source tree
      3. ~/.hackingtool/tools
    """
    explicit = os.environ.get("HACKINGTOOL_TOOLS_DIR", "").strip()
    if explicit:
        p = Path(explicit).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    if os.environ.get("HACKINGTOOL_DEV", "").lower() in ("1", "true", "yes"):
        if (REPO_ROOT / "hackingtool.py").exists():
            d = (REPO_ROOT / "tools").resolve()
            d.mkdir(parents=True, exist_ok=True)
            return d

    return Path.home() / f".{REPO_NAME}" / "tools"


# ── Versioning ────────────────────────────────────────────────────────────────
VERSION         = "2.0.0"
VERSION_DISPLAY = f"v{VERSION}"

# ── Python requirement ────────────────────────────────────────────────────────
MIN_PYTHON = (3, 10)

# ── User-scoped paths (cross-platform, always computed at runtime) ─────────────
# NEVER hardcode /home/username — use Path.home() so it works for any user,
# including root (/root), regular users (/home/alice), macOS (/Users/alice).
USER_CONFIG_DIR  = Path.home() / f".{REPO_NAME}"
# Fallback key when config has no tools_dir; production default is home-based.
USER_TOOLS_DIR   = USER_CONFIG_DIR / "tools"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.json"
USER_LOG_FILE    = USER_CONFIG_DIR / f"{REPO_NAME}.log"

# ── System install paths (set per OS) ─────────────────────────────────────────
_system = platform.system()

if _system == "Darwin":
    # macOS — Homebrew convention
    APP_INSTALL_DIR = Path("/usr/local/share") / REPO_NAME
    APP_BIN_PATH    = Path("/usr/local/bin")   / REPO_NAME
elif _system == "Linux":
    APP_INSTALL_DIR = Path("/usr/share") / REPO_NAME
    APP_BIN_PATH    = Path("/usr/bin")   / REPO_NAME
else:
    # Fallback (Windows, FreeBSD, etc.)
    APP_INSTALL_DIR = USER_CONFIG_DIR / "app"
    APP_BIN_PATH    = USER_CONFIG_DIR / "bin" / REPO_NAME

# ── UI theme ──────────────────────────────────────────────────────────────────
THEME_PRIMARY  = "bold magenta"
THEME_BORDER   = "bright_magenta"
THEME_SUCCESS  = "bold green"
THEME_ERROR    = "bold red"
THEME_WARNING  = "bold yellow"
THEME_DIM      = "dim white"
THEME_ARCHIVED = "dim yellow"
THEME_URL      = "underline bright_blue"
THEME_ACCENT   = "bold cyan"

# ── Default config values ──────────────────────────────────────────────────────
DEFAULT_CONFIG: dict = {
    "tools_dir":      str(resolve_default_tools_dir()),
    "version":        VERSION,
    "theme":          "magenta",
    "show_archived":  False,
    "sudo_binary":    "sudo",
    "go_bin_dir":     str(Path.home() / "go" / "bin"),
    "gem_bin_dir":    str(Path.home() / ".gem" / "ruby"),
}

# ── Privilege escalation ───────────────────────────────────────────────────────
# Prefer doas if present (OpenBSD/some Linux setups), else sudo
PRIV_CMD = "doas" if _shutil.which("doas") else "sudo"
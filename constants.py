"""Project-wide constants and path resolution helpers."""

from pathlib import Path
import platform
import shutil as _shutil
import os

# ── Repository ────────────────────────────────────────────────────────────────
REPO_OWNER   = "Z4nzu"
REPO_NAME    = "hackingtool"
REPO_URL     = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git"
REPO_WEB_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"

# ── Versioning ────────────────────────────────────────────────────────────────
VERSION         = "2.0.0"
VERSION_DISPLAY = f"v{VERSION}"

# ── Python requirement ────────────────────────────────────────────────────────
MIN_PYTHON = (3, 10)

# ── User-scoped paths (venv-contained when active) ────────────────────────────
# If running inside a venv, keep all app state inside that environment to avoid
# writing to the host user's home directory.
_VENV_PATH = os.environ.get("VIRTUAL_ENV", "").strip()
if _VENV_PATH:
    USER_CONFIG_DIR = Path(_VENV_PATH).resolve() / f".{REPO_NAME}"
else:
    USER_CONFIG_DIR = Path.home() / f".{REPO_NAME}"

USER_TOOLS_DIR   = USER_CONFIG_DIR / "tools"
USER_CONFIG_FILE = USER_CONFIG_DIR / "config.json"
USER_LOG_FILE    = USER_CONFIG_DIR / f"{REPO_NAME}.log"


def resolve_default_tools_dir() -> Path:
    """
    Resolve the default tools directory with explicit environment precedence:
    1) HACKINGTOOL_TOOLS_DIR
    2) HACKINGTOOL_DEV=1 -> repo-local state dir
    3) ~/.hackingtool/tools (or venv-contained equivalent)
    """
    env_tools_dir = os.environ.get("HACKINGTOOL_TOOLS_DIR", "").strip()
    if env_tools_dir:
        return Path(env_tools_dir).expanduser().resolve()

    dev_mode = os.environ.get("HACKINGTOOL_DEV", "").strip().lower() in {"1", "true", "yes", "on"}
    if dev_mode:
        repo_root = Path(__file__).resolve().parent
        return (repo_root / ".hackingtool" / "tools").resolve()

    return USER_TOOLS_DIR

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
    "privacy_mode":   True,
    "venv_contained": True,
    "sudo_binary":    "sudo",
    "go_bin_dir":     str(Path.home() / "go" / "bin"),
    "gem_bin_dir":    str(Path.home() / ".gem" / "ruby"),
}

# ── Privilege escalation ───────────────────────────────────────────────────────
# Prefer doas if present (OpenBSD/some Linux setups), else sudo
PRIV_CMD = "doas" if _shutil.which("doas") else "sudo"

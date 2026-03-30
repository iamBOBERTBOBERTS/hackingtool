"""Configuration helpers for hackingtool runtime settings."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from constants import USER_CONFIG_FILE, USER_TOOLS_DIR, DEFAULT_CONFIG, resolve_default_tools_dir

logger = logging.getLogger(__name__)


def load() -> dict[str, Any]:
    """Load config from disk, merging with defaults for any missing keys."""
    if USER_CONFIG_FILE.exists():
        try:
            on_disk = json.loads(USER_CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **on_disk}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Config file unreadable (%s), using defaults.", exc)
    return dict(DEFAULT_CONFIG)


def save(cfg: dict[str, Any]) -> None:
    """Write config to disk, creating parent directories if needed."""
    USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, sort_keys=True))


def get_tools_dir() -> Path:
    """
    Return the directory where external tools are stored.
    Creates it if it does not exist.
    Always an absolute path — never relies on process CWD.
    """
    cfg = load()
    configured = cfg.get("tools_dir", str(resolve_default_tools_dir()))
    tools_dir = Path(configured).expanduser().resolve()

    try:
        tools_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(tools_dir, os.W_OK | os.X_OK):
            raise PermissionError(f"insufficient permissions for {tools_dir}")
        return tools_dir
    except PermissionError as exc:
        fallback = Path(USER_TOOLS_DIR).expanduser().resolve()
        logger.warning("Tools directory not writable (%s). Falling back to %s", exc, fallback)
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_privacy_mode() -> bool:
    """Return whether privacy-safe output is enabled (default True)."""
    cfg = load()
    return bool(cfg.get("privacy_mode", True))


def get_sudo_cmd() -> str:
    """Return 'doas' if available, else 'sudo'. Never hardcode 'sudo'."""
    return "doas" if shutil.which("doas") else "sudo"

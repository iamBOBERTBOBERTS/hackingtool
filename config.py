import json
import logging
import os
from pathlib import Path
from typing import Any

from constants import USER_CONFIG_FILE, USER_TOOLS_DIR, DEFAULT_CONFIG, resolve_default_tools_dir

logger = logging.getLogger(__name__)


def load() -> dict[str, Any]:
    """Load config from disk, merging with defaults for any missing keys."""
    if USER_CONFIG_FILE.exists():
        try:
            on_disk = json.loads(USER_CONFIG_FILE.read_text())
            cfg: dict[str, Any] = {**DEFAULT_CONFIG, **on_disk}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Config file unreadable (%s), using defaults.", exc)
            cfg = dict(DEFAULT_CONFIG)
    else:
        cfg = dict(DEFAULT_CONFIG)

    # Session overrides — dev workflow / explicit path without editing config.json
    explicit = os.environ.get("HACKINGTOOL_TOOLS_DIR", "").strip()
    if explicit:
        cfg["tools_dir"] = str(Path(explicit).expanduser().resolve())
    elif os.environ.get("HACKINGTOOL_DEV", "").lower() in ("1", "true", "yes"):
        cfg["tools_dir"] = str(resolve_default_tools_dir())

    return cfg


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
    tools_dir = Path(cfg.get("tools_dir", str(USER_TOOLS_DIR))).expanduser().resolve()
    tools_dir.mkdir(parents=True, exist_ok=True)
    return tools_dir


def get_sudo_cmd() -> str:
    """Return 'doas' if available, else 'sudo'. Never hardcode 'sudo'."""
    import shutil
    return "doas" if shutil.which("doas") else "sudo"
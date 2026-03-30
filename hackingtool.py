#!/usr/bin/env python3
"""Interactive hackingtool launcher and category router."""

# flake8: noqa
# pylint: disable=too-many-lines,missing-module-docstring,missing-class-docstring,missing-function-docstring
# pylint: disable=wrong-import-position,import-outside-toplevel,line-too-long,broad-exception-caught
# pylint: disable=redefined-outer-name,reimported,unused-import

import sys

# ── Python version guard (must be before any other local import) ───────────────
if sys.version_info < (3, 10):
    print(
        f"[ERROR] Python 3.10 or newer is required.\n"
        f"You are running Python {sys.version_info.major}.{sys.version_info.minor}.\n"
        f"Upgrade with: sudo apt install python3.10"
    )
    sys.exit(1)


def _load_repo_dotenv() -> None:
    """Load KEY=value from repo-root .env if present (no python-dotenv dependency)."""
    import os
    from pathlib import Path

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if not key:
                continue
            val = val.strip().strip("'").strip('"')
            if key not in os.environ:
                os.environ[key] = val
    except OSError:
        pass


_load_repo_dotenv()

import os
import platform
import socket
import datetime
import random
import json
import re
import shutil
import subprocess
import webbrowser
from pathlib import Path
from itertools import zip_longest
from dataclasses import dataclass


def _is_truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def maybe_use_project_venv() -> bool:
    """
    In dev mode, auto-wire a repo-local venv so running without manual activation works.
    Search order: venv-dillons-clapped → .venv → venv.
    """
    if not _is_truthy_env("HACKINGTOOL_DEV"):
        return False

    if os.environ.get("VIRTUAL_ENV") or (sys.prefix != getattr(sys, "base_prefix", sys.prefix)):
        return True

    repo_root = Path(__file__).resolve().parent
    py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for name in ("venv-dillons-clapped", ".venv", "venv"):
        venv_dir = repo_root / name
        if not venv_dir.is_dir():
            continue
        site_pkgs = venv_dir / "lib" / py_tag / "site-packages"
        if not site_pkgs.is_dir():
            continue
        os.environ["VIRTUAL_ENV"] = str(venv_dir)
        os.environ["PATH"] = f"{venv_dir / 'bin'}:{os.environ.get('PATH', '')}"
        os.environ.pop("PYTHONHOME", None)
        site_path = str(site_pkgs)
        if site_path not in sys.path:
            sys.path.insert(0, site_path)
        return True

    print(
        "[WARN] HACKINGTOOL_DEV=1 but no usable repo venv was found "
        "(venv-dillons-clapped, .venv, or venv with site-packages). "
        "Continuing without auto-activation.",
        file=sys.stderr,
    )
    return False


maybe_use_project_venv()

from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box
from rich.rule import Rule

from core import HackingTool, HackingToolsCollection, clear_screen, console
from constants import VERSION_DISPLAY, REPO_WEB_URL
from config import get_tools_dir
from tools.anonsurf import AnonSurfTools
from tools.ddos import DDOSTools
from tools.exploit_frameworks import ExploitFrameworkTools
from tools.forensics import ForensicTools
from tools.information_gathering import InformationGatheringTools
from tools.other_tools import OtherTools
from tools.payload_creator import PayloadCreatorTools
from tools.phishing_attack import PhishingAttackTools
from tools.post_exploitation import PostExploitationTools
from tools.remote_administration import RemoteAdministrationTools
from tools.reverse_engineering import ReverseEngineeringTools
from tools.sql_injection import SqlInjectionTools
from tools.steganography import SteganographyTools
from tools.tool_manager import ToolManager
from tools.web_attack import WebAttackTools
from tools.wireless_attack import WirelessAttackTools
from tools.wordlist_generator import WordlistGeneratorTools
from tools.xss_attack import XSSAttackTools
from tools.active_directory import ActiveDirectoryTools
from tools.cloud_security import CloudSecurityTools
from tools.mobile_security import MobileSecurityTools


@dataclass
class SmartIntent:
    action: str
    query: str = ""
    confidence: float = 0.0
    reasoning: str = ""


class SmartInputEngine:
    """Optional local-LLM intent parser with deterministic fallback."""

    def __init__(self, model: str = "llama3.2:3b"):
        self.model = model

    @property
    def ollama_available(self) -> bool:
        return shutil.which("ollama") is not None

    def _model_installed(self) -> bool:
        if not self.ollama_available:
            return False
        try:
            result = subprocess.run(
                ["ollama", "list"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False
            return self.model in result.stdout
        except (OSError, subprocess.SubprocessError, TimeoutError):
            return False

    def status_line(self) -> str:
        if not self.ollama_available:
            return "local AI offline (install ollama for smart parsing)"
        if self._model_installed():
            return f"local AI online ({self.model})"
        return f"ollama detected, model missing ({self.model})"

    def set_model(self, model_name: str) -> None:
        self.model = model_name.strip()

    def install_hint(self) -> str:
        return (
            "Install: curl -fsSL https://ollama.com/install.sh | sh\n"
            f"Then: ollama pull {self.model}"
        )

    def interpret(self, raw_text: str) -> SmartIntent:
        text = (raw_text or "").strip()
        if not text:
            return SmartIntent(action="none", query="", confidence=0.0)

        if self.ollama_available and self._model_installed():
            llm_intent = self._interpret_with_llm(text)
            if llm_intent is not None:
                return llm_intent

        return self._interpret_with_rules(text)

    def _interpret_with_llm(self, text: str) -> SmartIntent | None:
        prompt = (
            "You are an intent classifier for a terminal cybersecurity tool. "
            "Return only compact JSON with keys: action, query, confidence, reasoning. "
            "Allowed action values: search, tag, recommend, open_help, none. "
            "If unsure, use none.\n\n"
            f"User input: {text}"
        )

        try:
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                check=False,
                capture_output=True,
                text=True,
                timeout=12,
            )
            if result.returncode != 0:
                return None

            payload = self._extract_json_object(result.stdout)
            if not payload:
                return None

            action = str(payload.get("action", "none")).strip().lower()
            query = str(payload.get("query", text)).strip()
            confidence = float(payload.get("confidence", 0.0))
            reasoning = str(payload.get("reasoning", "")).strip()

            if action not in {"search", "tag", "recommend", "open_help", "none"}:
                action = "none"

            return SmartIntent(
                action=action,
                query=query,
                confidence=max(0.0, min(confidence, 1.0)),
                reasoning=reasoning,
            )
        except (OSError, subprocess.SubprocessError, TimeoutError, ValueError, TypeError):
            return None

    @staticmethod
    def _extract_json_object(text: str) -> dict | None:
        if not text:
            return None
        text = text.strip()

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _interpret_with_rules(text: str) -> SmartIntent:
        lowered = text.lower()

        if any(k in lowered for k in ["help", "how to use", "commands", "?", "menu"]):
            return SmartIntent(
                action="open_help",
                query=text,
                confidence=0.85,
                reasoning="matched help keywords",
            )

        if any(k in lowered for k in ["tag", "filter", "osint", "wireless", "cloud", "mobile", "active directory"]):
            return SmartIntent(
                action="tag",
                query=text,
                confidence=0.72,
                reasoning="matched tag/filter terms",
            )

        if any(k in lowered for k in ["how do i", "i want to", "recommend", "best tool", "task", "need to"]):
            return SmartIntent(
                action="recommend",
                query=text,
                confidence=0.7,
                reasoning="matched recommendation-style phrasing",
            )

        if len(text.split()) >= 2:
            return SmartIntent(
                action="search",
                query=text,
                confidence=0.62,
                reasoning="default multi-word search fallback",
            )

        return SmartIntent(action="none", query=text, confidence=0.35, reasoning="insufficient signal")

# ── Tool registry ──────────────────────────────────────────────────────────────

# (full_title, icon, menu_label)
# menu_label is the concise name shown in the 2-column main menu grid.
# full_title is shown when entering the category.
tool_definitions = [
    ("Anonymously Hiding Tools",           "🛡 ", "Anonymously Hiding"),
    ("Information gathering tools",        "🔍",  "Information Gathering"),
    ("Wordlist Generator",                 "📚",  "Wordlist Generator"),
    ("Wireless attack tools",              "📶",  "Wireless Attack"),
    ("SQL Injection Tools",                "🧩",  "SQL Injection"),
    ("Phishing attack tools",              "🎣",  "Phishing Attack"),
    ("Web Attack tools",                   "🌐",  "Web Attack"),
    ("Post exploitation tools",            "🔧",  "Post Exploitation"),
    ("Forensic tools",                     "🕵 ", "Forensics"),
    ("Payload creation tools",             "📦",  "Payload Creation"),
    ("Exploit framework",                  "🧰",  "Exploit Framework"),
    ("Reverse engineering tools",          "🔁",  "Reverse Engineering"),
    ("DDOS Attack Tools",                  "⚡",  "DDOS Attack"),
    ("Remote Administrator Tools (RAT)",   "🖥 ", "Remote Admin (RAT)"),
    ("XSS Attack Tools",                   "💥",  "XSS Attack"),
    ("Steganography tools",                "🖼 ", "Steganography"),
    ("Active Directory Tools",             "🏢",  "Active Directory"),
    ("Cloud Security Tools",               "☁ ",  "Cloud Security"),
    ("Mobile Security Tools",              "📱",  "Mobile Security"),
    ("Other tools",                        "✨",  "Other Tools"),
    ("Update or Uninstall | Hackingtool",  "♻ ",  "Update / Uninstall"),
]

all_tools = [
    AnonSurfTools(),
    InformationGatheringTools(),
    WordlistGeneratorTools(),
    WirelessAttackTools(),
    SqlInjectionTools(),
    PhishingAttackTools(),
    WebAttackTools(),
    PostExploitationTools(),
    ForensicTools(),
    PayloadCreatorTools(),
    ExploitFrameworkTools(),
    ReverseEngineeringTools(),
    DDOSTools(),
    RemoteAdministrationTools(),
    XSSAttackTools(),
    SteganographyTools(),
    ActiveDirectoryTools(),
    CloudSecurityTools(),
    MobileSecurityTools(),
    OtherTools(),
    ToolManager(),
]

smart_engine = SmartInputEngine()

# Used by generate_readme.py
class AllTools(HackingToolsCollection):
    TITLE = "All tools"
    TOOLS = all_tools


# ── Help overlay ───────────────────────────────────────────────────────────────

def show_help():
    console.print(Panel(
        Text.assemble(
            ("  Main menu\n", "bold white"),
            ("  ─────────────────────────────────────\n", "dim"),
            ("  1–20   ", "bold cyan"), ("open a category\n", "white"),
            ("  21     ", "bold cyan"), ("Update / Uninstall hackingtool\n", "white"),
            ("  / or s ", "bold cyan"), ("search tools by name or keyword\n", "white"),
            ("  t      ", "bold cyan"), ("filter tools by tag (osint, web, c2, ...)\n", "white"),
            ("  r      ", "bold cyan"), ("recommend tools for a task\n", "white"),
            ("  ?      ", "bold cyan"), ("show this help\n", "white"),
            ("  q      ", "bold cyan"), ("quit hackingtool\n\n", "white"),
            ("  Inside a category\n", "bold white"),
            ("  ─────────────────────────────────────\n", "dim"),
            ("  1–N    ", "bold cyan"), ("select a tool\n", "white"),
            ("  99     ", "bold cyan"), ("back to main menu\n", "white"),
            ("  98     ", "bold cyan"), ("open project page (if available)\n\n", "white"),
            ("  Inside a tool\n", "bold white"),
            ("  ─────────────────────────────────────\n", "dim"),
            ("  1      ", "bold cyan"), ("install tool\n", "white"),
            ("  2      ", "bold cyan"), ("run tool\n", "white"),
            ("  99     ", "bold cyan"), ("back to category\n", "white"),
        ),
        title="[bold magenta] ? Quick Help [/bold magenta]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(0, 2),
    ))
    Prompt.ask("[dim]Press Enter to return[/dim]", default="")


# ── Header: ASCII art + live system info ──────────────────────────────────────

# Full "HACKING TOOL" block-letter art — 12 lines, split layout with stats
_BANNER_ART = [
    " ██╗  ██╗ █████╗  ██████╗██╗  ██╗██╗███╗   ██╗ ██████╗ ",
    " ██║  ██║██╔══██╗██╔════╝██║ ██╔╝██║████╗  ██║██╔════╝ ",
    " ███████║███████║██║     █████╔╝ ██║██╔██╗ ██║██║  ███╗",
    " ██╔══██║██╔══██║██║     ██╔═██╗ ██║██║╚██╗██║██║   ██║",
    " ██║  ██║██║  ██║╚██████╗██║  ██╗██║██║ ╚████║╚██████╔╝",
    " ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ",
    "        ████████╗ ██████╗  ██████╗ ██╗",
    "        ╚══██╔══╝██╔═══██╗██╔═══██╗██║",
    "           ██║   ██║   ██║██║   ██║██║",
    "           ██║   ██║   ██║██║   ██║██║",
    "           ██║   ╚██████╔╝╚██████╔╝███████╗",
    "           ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝",
]

_QUOTES = [
    '"The quieter you become, the more you can hear."',
    '"Offense informs defense."',
    '"There is no patch for human stupidity."',
    '"In God we trust. All others we monitor."',
    '"Hackers are the immune system of the internet."',
    '"Every system is hackable — know yours before others do."',
    '"Enumerate before you exploit."',
    '"A scope defines your playground."',
    '"The more you sweat in training, the less you bleed in battle."',
    '"Security is a process, not a product."',
]

_COSMIC_STRIP = " ✦  COSMIC MODE  ✦  smart terminal routing  ✦  natural-language commands  ✦ "


def _sys_info() -> dict:
    """Collect live system info for the header panel."""
    info: dict = {}

    # OS pretty name
    try:
        info["os"] = platform.freedesktop_os_release().get("PRETTY_NAME", "")
    except (AttributeError, OSError, KeyError):
        info["os"] = ""
    if not info["os"]:
        info["os"] = f"{platform.system()} {platform.release()}"

    info["kernel"] = platform.release()

    # Current user
    try:
        info["user"] = os.getlogin()
    except OSError:
        info["user"] = os.environ.get("USER", os.environ.get("LOGNAME", "root"))

    info["host"] = socket.gethostname()

    # Local IP — connect to a routable address without sending data
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        s.connect(("10.254.254.254", 1))
        info["ip"] = s.getsockname()[0]
        s.close()
    except OSError:
        info["ip"] = "127.0.0.1"

    info["time"] = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M")
    return info


def _build_header() -> Panel:
    info = _sys_info()

    # 12 stat lines paired with the 12 art lines
    stat_lines = [
        ("  os      ›  ", info["os"][:34]),
        ("  kernel  ›  ", info["kernel"][:34]),
        ("  user    ›  ", f"{info['user']} @ {info['host'][:20]}"),
        ("  ip      ›  ", info["ip"]),
        ("  tools   ›  ", f"{len(all_tools)} categories · 185+ modules"),
        ("  session ›  ", info["time"]),
        ("", ""),
        ("  python  ›  ", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
        ("  arch    ›  ", platform.machine()),
        ("  status  ›  ", "✔ READY"),
        ("", ""),
        ("", ""),
    ]

    grid = Table.grid(padding=0)
    grid.add_column("art", no_wrap=True)
    grid.add_column("sep", no_wrap=True)
    grid.add_column("lbl", no_wrap=True)
    grid.add_column("val", no_wrap=True)

    for art_line, (lbl_text, val_text) in zip(_BANNER_ART, stat_lines):
        grid.add_row(
            Text(art_line, style="bold bright_green"),
            Text("  │ ", style="dim green"),
            Text(lbl_text, style="dim green"),
            Text(val_text, style="bright_green"),
        )

    # Quote + warning below the split row
    quote = random.choice(_QUOTES)
    body = Table.grid(padding=(0, 0))
    body.add_column()
    body.add_row(grid)
    body.add_row(Text(""))
    body.add_row(Text(f"  {quote}", style="italic dim"))
    body.add_row(Text("  ⚠  For authorized security testing only",
                      style="bold dim red"))

    return Panel(
        body,
        title=f"[bold bright_magenta][ HackingTool {VERSION_DISPLAY} ][/bold bright_magenta]",
        title_align="left",
        subtitle=f"[dim][ {info['time']} ][/dim]",
        subtitle_align="right",
        border_style="bright_magenta",
        box=box.HEAVY,
        padding=(0, 1),
    )


# ── Main menu renderer ─────────────────────────────────────────────────────────

def build_menu():
    clear_screen()
    console.print(_build_header())
    console.print(Panel(
        f"[bold cyan]{_COSMIC_STRIP}[/bold cyan]",
        border_style="cyan",
        box=box.SIMPLE,
        padding=(0, 1),
    ))
    console.print(
        f"  [dim]AI:[/dim] [bold cyan]{smart_engine.status_line()}[/bold cyan]"
    )

    # ── 2-column category grid ──
    # Items 1-17 in two columns, item 18 (ToolManager) shown separately
    categories = tool_definitions[:-1]   # 17 items
    update_def = tool_definitions[-1]    # ToolManager

    mid = (len(categories) + 1) // 2    # 9  (left), 8 (right)
    left  = list(enumerate(categories[:mid],  start=1))
    right = list(enumerate(categories[mid:],  start=mid + 1))

    grid = Table.grid(padding=(0, 1), expand=True)
    grid.add_column("ln", justify="right", style="bold magenta", width=5)
    grid.add_column("li", width=3)
    grid.add_column("lt", style="magenta", ratio=1, no_wrap=True)
    grid.add_column("gap", width=3)
    grid.add_column("rn", justify="right", style="bold magenta", width=5)
    grid.add_column("ri", width=3)
    grid.add_column("rt", style="magenta", ratio=1, no_wrap=True)

    for (li, (_, lic, ll)), r in zip_longest(left, right, fillvalue=None):
        if r:
            ri, (_, ric, rl) = r
            grid.add_row(str(li), lic, ll, "", str(ri), ric, rl)
        else:
            grid.add_row(str(li), lic, ll, "", "", "", "")

    console.print(Panel(
        grid,
        title="[bold magenta] Select a Category [/bold magenta]",
        border_style="bright_magenta",
        box=box.ROUNDED,
        padding=(0, 1),
    ))

    # ── ToolManager row ──
    tm_num = len(categories) + 1
    console.print(
        f"  [bold magenta]  {tm_num}[/bold magenta]  {update_def[1]}  "
        f"[magenta]{update_def[2]}[/magenta]"
    )

    # ── Claude-style dual-line prompt area ──
    console.print(Rule(style="dim magenta"))
    console.print(
        "  [dim cyan]/[/dim cyan][dim]search[/dim]  "
        "[dim cyan]t[/dim cyan] [dim]tags[/dim]  "
        "[dim cyan]r[/dim cyan] [dim]recommend[/dim]  "
        "[dim cyan]ai[/dim cyan] [dim]local-llm[/dim]  "
        "[dim cyan]?[/dim cyan] [dim]help[/dim]  "
        "[dim cyan]q[/dim cyan] [dim]quit[/dim]"
    )
    console.print("  [dim]Tip: type plain language like 'find subdomains' or 'web vuln scan tools'[/dim]")


# ── Search ─────────────────────────────────────────────────────────────────────

def _collect_all_tools() -> list[tuple]:
    """Walk all collections and return (tool_instance, category_name) pairs."""
    results = []

    def _walk(items, parent_title=""):
        for item in items:
            if isinstance(item, HackingToolsCollection):
                _walk(item.TOOLS, item.TITLE)
            elif isinstance(item, HackingTool):
                results.append((item, parent_title))

    _walk(all_tools)
    return results


def _get_all_tags() -> dict[str, list[tuple]]:
    """Build tag → [(tool, category)] index from all tools."""
    _rules = {
        r'(osint|harvester|maigret|holehe|spiderfoot|sherlock|recon)': 'osint',
        r'(subdomain|subfinder|amass|sublist|subdomainfinder)': 'recon',
        r'(scanner|scan|nmap|masscan|rustscan|nikto|nuclei|trivy)': 'scanner',
        r'(brute|gobuster|ffuf|dirb|dirsearch|ferox|hashcat|john|kerbrute)': 'bruteforce',
        r'(web|http|proxy|zap|xss|sql|wafw00f|arjun|caido|mitmproxy)': 'web',
        r'(wireless|wifi|wlan|airgeddon|bettercap|wifite|fluxion|deauth)': 'wireless',
        r'(phish|social.media|evilginx|setoolkit|social.fish|social.engineer)': 'social-engineering',
        r'(c2|sliver|havoc|mythic|pwncat|reverse.shell|pyshell)': 'c2',
        r'(privesc|peass|linpeas|winpeas)': 'privesc',
        r'(tunnel|pivot|ligolo|chisel|proxy|anon)': 'network',
        r'(password|credential|hash|crack|secret|trufflehog|gitleaks)': 'credentials',
        r'(forensic|memory|volatility|binwalk|autopsy|wireshark|pspy)': 'forensics',
        r'(reverse.eng|ghidra|radare|jadx|androguard|apk)': 'reversing',
        r'(cloud|aws|azure|gcp|kubernetes|prowler|scout|pacu)': 'cloud',
        r'(mobile|android|ios|frida|mobsf|objection|droid)': 'mobile',
        r'(active.directory|bloodhound|netexec|impacket|responder|certipy|kerberos|winrm|smb|ldap)': 'active-directory',
        r'(ddos|dos|slowloris|goldeneye|ufonet)': 'ddos',
        r'(payload|msfvenom|fatrat|venom|stitch|enigma)': 'payload',
        r'(crawler|spider|katana|gospider)': 'crawler',
    }
    tag_index: dict[str, list[tuple]] = {}
    for tool, cat in _collect_all_tools():
        combined = f"{tool.TITLE} {tool.DESCRIPTION}".lower()
        # Manual tags first
        tool_tags = set(getattr(tool, "TAGS", []) or [])
        # Auto-derive tags from title/description
        for pattern, tag in _rules.items():
            if re.search(pattern, combined, re.IGNORECASE):
                tool_tags.add(tag)
        for t in tool_tags:
            tag_index.setdefault(t, []).append((tool, cat))
    return tag_index


def filter_by_tag():
    """Show available tags, user picks one, show matching tools."""
    tag_index = _get_all_tags()
    sorted_tags = sorted(tag_index.keys())

    # Show tags in a compact grid
    console.print(Panel(
        "  ".join(f"[bold cyan]{t}[/bold cyan]([dim]{len(tag_index[t])}[/dim])" for t in sorted_tags),
        title="[bold magenta] Available Tags [/bold magenta]",
        border_style="magenta", box=box.ROUNDED, padding=(0, 2),
    ))

    tag = Prompt.ask("[bold cyan]Enter tag[/bold cyan]", default="").strip().lower()
    if not tag or tag not in tag_index:
        if tag:
            console.print(f"[dim]Tag '{tag}' not found.[/dim]")
            Prompt.ask("[dim]Press Enter to return[/dim]", default="")
        return

    matches = tag_index[tag]
    table = Table(
        title=f"Tools tagged '{tag}'",
        box=box.SIMPLE_HEAD, show_lines=True,
    )
    table.add_column("No.", justify="center", style="bold cyan", width=5)
    table.add_column("", width=2)
    table.add_column("Tool", style="bold yellow", min_width=20)
    table.add_column("Category", style="magenta", min_width=15)

    for i, (tool, cat) in enumerate(matches, start=1):
        status = "[green]✔[/green]" if tool.is_installed else "[dim]✘[/dim]"
        table.add_row(str(i), status, tool.TITLE, cat)

    table.add_row("99", "", "Back to main menu", "")
    console.print(table)

    raw = Prompt.ask("[bold cyan]>[/bold cyan]", default="").strip()
    if not raw or raw == "99":
        return
    try:
        idx = int(raw)
    except ValueError:
        return
    if 1 <= idx <= len(matches):
        tool, cat = matches[idx - 1]
        tool.show_options()


_RECOMMENDATIONS = {
    "scan a network":           ["scanner", "port-scanner"],
    "find subdomains":          ["recon"],
    "scan for vulnerabilities": ["scanner", "web"],
    "crack passwords":          ["bruteforce", "credentials"],
    "find leaked secrets":      ["credentials"],
    "phishing campaign":        ["social-engineering"],
    "post exploitation":        ["c2", "privesc"],
    "pivot through network":    ["network"],
    "pentest active directory": ["active-directory"],
    "pentest web application":  ["web", "scanner"],
    "pentest cloud":            ["cloud"],
    "pentest mobile app":       ["mobile"],
    "reverse engineer binary":  ["reversing"],
    "capture wifi handshake":   ["wireless"],
    "intercept http traffic":   ["web", "network"],
    "forensic analysis":        ["forensics"],
    "ddos testing":             ["ddos"],
    "create payloads":          ["payload"],
    "find xss vulnerabilities": ["web"],
    "brute force directories":  ["bruteforce", "web"],
    "osint / recon a target":   ["osint", "recon"],
    "hide my identity":         ["network"],
}


def recommend_tools():
    """Show common tasks, user picks one, show matching tools."""
    table = Table(
        title="What do you want to do?",
        box=box.SIMPLE_HEAD,
    )
    table.add_column("No.", justify="center", style="bold cyan", width=5)
    table.add_column("Task", style="bold yellow")

    tasks = list(_RECOMMENDATIONS.keys())
    for i, task in enumerate(tasks, start=1):
        table.add_row(str(i), task.title())

    table.add_row("99", "Back to main menu")
    console.print(table)

    raw = Prompt.ask("[bold cyan]>[/bold cyan]", default="").strip()
    if not raw or raw == "99":
        return

    try:
        idx = int(raw)
    except ValueError:
        return

    if 1 <= idx <= len(tasks):
        task = tasks[idx - 1]
        _show_recommendations_for_task(task)


def _show_recommendations_for_task(task: str):
    tag_names = _RECOMMENDATIONS.get(task, [])
    tag_index = _get_all_tags()

    # Collect unique tools across all matching tags.
    seen = set()
    matches = []
    for tag in tag_names:
        for tool, cat in tag_index.get(tag, []):
            if id(tool) not in seen:
                seen.add(id(tool))
                matches.append((tool, cat))

    if not matches:
        console.print("[dim]No tools found for this task.[/dim]")
        Prompt.ask("[dim]Press Enter to return[/dim]", default="")
        return

    console.print(Panel(
        f"[bold]Recommended tools for: {task.title()}[/bold]",
        border_style="green", box=box.ROUNDED,
    ))

    rtable = Table(box=box.SIMPLE_HEAD, show_lines=True)
    rtable.add_column("No.", justify="center", style="bold cyan", width=5)
    rtable.add_column("", width=2)
    rtable.add_column("Tool", style="bold yellow", min_width=20)
    rtable.add_column("Category", style="magenta")

    for i, (tool, cat) in enumerate(matches, start=1):
        status = "[green]✔[/green]" if tool.is_installed else "[dim]✘[/dim]"
        rtable.add_row(str(i), status, tool.TITLE, cat)

    rtable.add_row("99", "", "Back", "")
    console.print(rtable)

    raw2 = Prompt.ask("[bold cyan]>[/bold cyan]", default="").strip()
    if raw2 and raw2 != "99":
        try:
            ridx = int(raw2)
            if 1 <= ridx <= len(matches):
                matches[ridx - 1][0].show_options()
        except ValueError:
            pass


def _recommend_task_from_text(user_text: str) -> str | None:
    if not user_text:
        return None

    words = set(w for w in user_text.lower().replace("/", " ").split() if len(w) > 2)
    best_task = None
    best_score = 0

    for task in _RECOMMENDATIONS:
        task_words = set(task.lower().replace("/", " ").split())
        score = len(words.intersection(task_words))
        if score > best_score:
            best_score = score
            best_task = task

    return best_task if best_score > 0 else None


def search_tools(query: str | None = None):
    """Search tools — accepts inline query or prompts for one."""
    if query is None:
        query = Prompt.ask("[bold cyan]/ Search[/bold cyan]", default="").strip().lower()
    else:
        query = query.lower()
    if not query:
        return

    all_tool_list = _collect_all_tools()

    # Match against title + description + tags
    matches = []
    for tool, category in all_tool_list:
        title = (tool.TITLE or "").lower()
        desc = (tool.DESCRIPTION or "").lower()
        tags = " ".join(getattr(tool, "TAGS", []) or []).lower()
        if query in title or query in desc or query in tags:
            matches.append((tool, category))

    if not matches:
        console.print(f"[dim]No tools found matching '{query}'[/dim]")
        Prompt.ask("[dim]Press Enter to return[/dim]", default="")
        return

    # Display results
    table = Table(
        title=f"Search results for '{query}'",
        box=box.SIMPLE_HEAD, show_lines=True,
    )
    table.add_column("No.", justify="center", style="bold cyan", width=5)
    table.add_column("Tool", style="bold yellow", min_width=20)
    table.add_column("Category", style="magenta", min_width=15)
    table.add_column("Description", style="white", overflow="fold")

    for i, (tool, cat) in enumerate(matches, start=1):
        desc = (tool.DESCRIPTION or "—").splitlines()[0]
        table.add_row(str(i), tool.TITLE, cat, desc)

    table.add_row("99", "Back to main menu", "", "")
    console.print(table)

    raw = Prompt.ask("[bold cyan]>[/bold cyan]", default="").strip().lower()
    if not raw or raw == "99":
        return

    try:
        idx = int(raw)
    except ValueError:
        return

    if 1 <= idx <= len(matches):
        tool, cat = matches[idx - 1]
        console.print(Panel(
            f"[bold magenta]{tool.TITLE}[/bold magenta]  [dim]({cat})[/dim]",
            border_style="magenta", box=box.ROUNDED,
        ))
        tool.show_options()


def _show_ai_panel():
    console.print(Panel(
        "\n".join([
            f"[bold cyan]Status:[/bold cyan] {smart_engine.status_line()}",
            f"[bold cyan]Model:[/bold cyan] {smart_engine.model}",
            "[dim]Commands: ai, ai status, ai model <name>, ai pull[/dim]",
            f"[dim]{smart_engine.install_hint()}[/dim]",
        ]),
        title="[bold magenta] Local AI Assistant [/bold magenta]",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    ))


def _handle_ai_command(raw_lower: str) -> bool:
    if raw_lower in ("ai", "ai status"):
        _show_ai_panel()
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return True

    if raw_lower.startswith("ai model "):
        model = raw_lower.replace("ai model ", "", 1).strip()
        if model:
            smart_engine.set_model(model)
            console.print(f"[green]Model set to:[/green] [bold]{smart_engine.model}[/bold]")
        else:
            console.print("[red]Provide a model name, e.g. ai model llama3.2:3b[/red]")
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return True

    if raw_lower == "ai pull":
        if not smart_engine.ollama_available:
            console.print("[red]ollama is not installed.[/red]")
            console.print(f"[dim]{smart_engine.install_hint()}[/dim]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return True

        console.print(f"[cyan]Pulling model {smart_engine.model} ...[/cyan]")
        os.system(f"ollama pull {smart_engine.model}")
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return True

    return False


def _handle_smart_text(raw: str) -> bool:
    intent = smart_engine.interpret(raw)
    if intent.action == "none":
        return False

    if intent.action == "open_help":
        show_help()
        return True

    if intent.action == "recommend":
        task = _recommend_task_from_text(intent.query)
        if task:
            console.print(f"[dim]AI route:[/dim] [cyan]recommendation[/cyan] -> [bold]{task}[/bold]")
            _show_recommendations_for_task(task)
            return True
        recommend_tools()
        return True

    if intent.action in ("search", "tag"):
        console.print(f"[dim]AI route:[/dim] [cyan]search[/cyan] -> [bold]{intent.query}[/bold]")
        search_tools(query=intent.query)
        return True

    return False


# ── Main interaction loop ──────────────────────────────────────────────────────

def interact_menu():
    while True:
        try:
            build_menu()
            raw = Prompt.ask(
                "[bold magenta]╰─>[/bold magenta]", default=""
            ).strip()

            if not raw:
                continue

            raw_lower = raw.lower()

            if raw_lower in ("?", "help"):
                show_help()
                continue

            if raw_lower.startswith("ai") and _handle_ai_command(raw_lower):
                continue

            if raw.startswith("/"):
                # Inline search: /subdomain → search immediately
                query = raw[1:].strip()
                search_tools(query=query if query else None)
                continue

            if raw_lower in ("s", "search"):
                search_tools()
                continue

            if raw_lower in ("t", "tag", "tags", "filter"):
                filter_by_tag()
                continue

            if raw_lower in ("r", "rec", "recommend"):
                recommend_tools()
                continue

            if raw_lower in ("q", "quit", "exit"):
                console.print(Panel(
                    "[bold white on magenta]  Goodbye — Come Back Safely  [/bold white on magenta]",
                    box=box.HEAVY, border_style="magenta",
                ))
                break

            # Natural language input routed through local LLM (if configured)
            # with deterministic fallback rules.
            if _handle_smart_text(raw):
                continue

            try:
                choice = int(raw_lower)
            except ValueError:
                console.print("[red]⚠  Invalid input — enter a number, /query to search, or q to quit.[/red]")
                Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
                continue

            if 1 <= choice <= len(all_tools):
                title, icon, _ = tool_definitions[choice - 1]
                console.print(Panel(
                    f"[bold magenta]{icon}  {title}[/bold magenta]",
                    border_style="magenta", box=box.ROUNDED,
                ))
                try:
                    all_tools[choice - 1].show_options()
                except (RuntimeError, OSError, ValueError) as e:
                    console.print(Panel(
                        f"[red]Error while opening {title}[/red]\n{e}",
                        border_style="red",
                    ))
                    Prompt.ask("[dim]Press Enter to return to main menu[/dim]", default="")
            else:
                console.print(f"[red]⚠  Choose 1–{len(all_tools)}, ? for help, or q to quit.[/red]")
                Prompt.ask("[dim]Press Enter to continue[/dim]", default="")

        except KeyboardInterrupt:
            console.print("\n[bold red]Interrupted — exiting[/bold red]")
            break


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    try:
        from os_detect import CURRENT_OS

        maybe_use_project_venv()

        if not (os.environ.get("VIRTUAL_ENV") or (sys.prefix != getattr(sys, "base_prefix", sys.prefix))):
            console.print(Panel(
                "[bold red]Venv containment is required.[/bold red]\n"
                "This build is locked to a Python virtual environment to avoid writing to your host system.\n\n"
                "Create and activate one, then run again:\n"
                "[bold cyan]python3 -m venv venv-dillons-clapped[/bold cyan]\n"
                "[bold cyan]source venv-dillons-clapped/bin/activate[/bold cyan]\n"
                "[bold cyan]pip install -r requirements.txt[/bold cyan]\n"
                "[bold cyan]./hackingtool-local.sh[/bold cyan]  [dim](or HACKINGTOOL_DEV=1 python3 hackingtool.py)[/dim]",
                border_style="red",
                box=box.DOUBLE,
            ))
            return

        if CURRENT_OS.system == "windows":
            console.print(Panel("[bold red]Please run this tool on Linux or macOS.[/bold red]"))
            if Confirm.ask("Open guidance link in your browser?", default=True):
                webbrowser.open_new_tab(f"{REPO_WEB_URL}#windows")
            return

        if CURRENT_OS.system not in ("linux", "macos"):
            console.print(f"[yellow]Unsupported OS: {CURRENT_OS.system}. Proceeding anyway...[/yellow]")

        get_tools_dir()   # ensures ~/.hackingtool/tools/ exists
        interact_menu()

    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting...[/bold red]")


if __name__ == "__main__":
    main()

"""Settings (config.yaml), secrets (environment) and the small state file."""
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
STATE_FILE = Path(os.environ.get("STATE_FILE", ROOT / "state" / "state.json"))


def load_env_file():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def secret(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Missing secret {name} (see .env.example)")
    return value


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "") not in ("", "0")


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def load_state() -> dict:
    state = {"niche": "", "history": [], "auto": {}, "offset": 0, "paused": False}
    if STATE_FILE.exists():
        state.update(json.loads(STATE_FILE.read_text()))
    return state


def save_state(state: dict):
    state["history"] = state["history"][-60:]
    state["auto"] = dict(sorted(state["auto"].items())[-7:])
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")

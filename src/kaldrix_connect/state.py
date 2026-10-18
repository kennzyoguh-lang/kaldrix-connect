"""What the connector keeps on this computer: the agent's own signing key, and the permissions it has been given.

A permission is not a secret: on its own it is useless, because only the matching private key can use it. The private key never leaves
this file. Where the file lives: `~/.kaldrix/connector.json` (set `KALDRIX_HOME` to put it somewhere else).
"""

import json
import os
import tempfile
from pathlib import Path

from . import proof


def home() -> Path:
    return Path(os.environ.get("KALDRIX_HOME") or (Path.home() / ".kaldrix"))


def _path() -> Path:
    return home() / "connector.json"


def load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("permissions", [])
    return data


def save(data: dict) -> None:
    home().mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(home()), prefix=".connector-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        try:
            os.chmod(tmp, 0o600)  # best effort: Windows does not honour it
        except OSError:
            pass
        os.replace(tmp, _path())
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def agent_seed() -> str:
    """The agent's private seed, made on first use and kept in the file."""
    data = load()
    if "agent_seed_hex" not in data:
        data["agent_seed_hex"] = proof.new_seed_hex()
        save(data)
    return data["agent_seed_hex"]


def agent_key():
    return proof.key_from_seed(agent_seed())


def add_permission(token: dict) -> None:
    data = load()
    data["permissions"] = [t for t in data["permissions"] if t.get("id") != token["id"]] + [token]
    save(data)


def permissions() -> list:
    return load()["permissions"]

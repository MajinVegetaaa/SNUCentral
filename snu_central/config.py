"""Load config.yaml and sources.yaml (NFR-4.4)."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_yaml(name: str) -> dict:
    with open(PROJECT_ROOT / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> dict:
    return _load_yaml("config.yaml")


def load_sources() -> dict:
    return _load_yaml("sources.yaml")


def project_path(cfg: dict, key: str) -> Path:
    """Absolute path for an entry under `paths:` in config.yaml."""
    return PROJECT_ROOT / cfg["paths"][key]

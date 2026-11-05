"""Configuration lue depuis l'environnement (voir .env.example).

Aucun secret n'est nécessaire au fonctionnement local : l'application
n'appelle aucun service externe.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    db_path: Path
    cors_origins: list[str] = field(default_factory=list)
    max_file_bytes: int = 2_000_000
    max_rows: int = 10_000
    max_field_chars: int = 20_000
    demo_enabled: bool = True
    demo_dir: Path = ROOT_DIR / "demo"
    frontend_dist: Path = ROOT_DIR / "frontend" / "dist"
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Relu à chaque appel pour que les tests puissent modifier l'environnement."""
    env = os.environ.get
    return Settings(
        db_path=Path(env("COMMERCEOPS_DB", "./catalog.db")),
        cors_origins=_list(env("COMMERCEOPS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")),
        max_file_bytes=int(env("COMMERCEOPS_MAX_FILE_BYTES", "2000000")),
        max_rows=int(env("COMMERCEOPS_MAX_ROWS", "10000")),
        demo_enabled=_bool(env("COMMERCEOPS_DEMO_ENABLED", "true")),
        demo_dir=Path(env("COMMERCEOPS_DEMO_DIR", str(ROOT_DIR / "demo"))),
        frontend_dist=Path(env("COMMERCEOPS_FRONTEND_DIST", str(ROOT_DIR / "frontend" / "dist"))),
        log_level=env("COMMERCEOPS_LOG_LEVEL", "INFO").upper(),
    )

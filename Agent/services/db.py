"""Local MySQL helpers for PharmTwinAI desktop app."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=True)
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip().strip('"').strip("'")


_load_dotenv()


def _cfg() -> dict[str, Any]:
    return {
        "host": os.getenv("PHARMTWIN_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("PHARMTWIN_DB_PORT", "3306")),
        "user": os.getenv("PHARMTWIN_DB_USER", "root"),
        "password": os.getenv("PHARMTWIN_DB_PASSWORD", ""),
        "database": os.getenv("PHARMTWIN_DB_NAME", "pharmtwinai"),
    }


def set_password(password: str, persist: bool = True) -> None:
    """Set MySQL password in-process and optionally write/update .env."""
    os.environ["PHARMTWIN_DB_PASSWORD"] = password
    if not persist:
        return
    env_path = _ROOT / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        example = _ROOT / ".env.example"
        if example.exists():
            lines = example.read_text(encoding="utf-8").splitlines()
        else:
            lines = [
                "PHARMTWIN_DB_HOST=127.0.0.1",
                "PHARMTWIN_DB_PORT=3306",
                "PHARMTWIN_DB_USER=root",
                "PHARMTWIN_DB_PASSWORD=",
                "PHARMTWIN_DB_NAME=pharmtwinai",
            ]
    found = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith("PHARMTWIN_DB_PASSWORD="):
            out.append(f"PHARMTWIN_DB_PASSWORD={password}")
            found = True
        elif "REPLACE_WITH_YOUR_MYSQL_ROOT_PASSWORD" in line:
            out.append(f"PHARMTWIN_DB_PASSWORD={password}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"PHARMTWIN_DB_PASSWORD={password}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def get_connection():
    import pymysql

    c = _cfg()
    return pymysql.connect(
        host=c["host"],
        user=c["user"],
        password=c["password"],
        database=c["database"],
        port=c["port"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def probe_database(database_optional: bool = False) -> tuple[bool, str]:
    """
    Probe MySQL. If database_optional=True, connect without selecting DB
    (useful before first --apply-schema seed).
    """
    c = _cfg()
    try:
        import pymysql

        kwargs = {
            "host": c["host"],
            "user": c["user"],
            "password": c["password"],
            "port": c["port"],
            "connect_timeout": 3,
        }
        if not database_optional:
            kwargs["database"] = c["database"]
        conn = pymysql.connect(**kwargs)
        conn.close()
        target = c["database"] if not database_optional else "(server)"
        pwd = "yes" if c["password"] else "NO"
        return True, f"{c['user']}@{c['host']}:{c['port']}/{target} (password:{pwd})"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def get_meta() -> dict[str, str]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT meta_key, meta_value FROM app_meta")
            rows = cur.fetchall()
        return {r["meta_key"]: r["meta_value"] for r in rows}
    finally:
        conn.close()

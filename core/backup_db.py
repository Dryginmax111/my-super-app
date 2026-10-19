#!/usr/bin/env python3
"""backup_db.py — консистентный бэкап SQLite-БД через sqlite3.backup().

Использование:
    python backup_db.py                 # стандартный бэкап
    python backup_db.py --db путь.db    # явный путь
    python backup_db.py --keep 50       # хранить N последних (по умолчанию 30)
    python backup_db.py --quiet         # без вывода (для cron/START.bat)

Бэкапы: backups/db/db_YYYYMMDD_HHMMSS_ffffff.db рядом с БД.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
KEEP_DEFAULT = 30


def _load_db_path(cli):
    if cli:
        return cli
    cfg = BASE / 'config.json'
    if not cfg.exists():
        return None
    try:
        return json.loads(cfg.read_text(encoding='utf-8')).get('db_path')
    except Exception:
        return None


def _backup_dir_for(db_path: Path) -> Path:
    d = db_path.parent / 'backups' / 'db'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp() -> str:
    # PATCH: микросекунды — исключаем коллизию при параллельных запусках
    return datetime.now().strftime('%Y%m%d_%H%M%S_%f')


def cleanup_old(bdir: Path, keep: int, quiet: bool, protect: Path | None = None):
    """Удаляет старые бэкапы, оставляя `keep` свежих.

    protect — путь, который нельзя удалять (свежесозданный бэкап),
              даже если он попал за границу `keep` (актуально при keep=0).
    """
    files = sorted(bdir.glob('db_*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
    if keep < 0:
        keep = 0
    to_delete = files[keep:] if keep else files[:]
    for old in to_delete:
        if protect and old.resolve() == protect.resolve():
            continue
        try:
            old.unlink()
            if not quiet:
                print(f'  удалён старый: {old.name}')
        except Exception as e:
            if not quiet:
                print(f'  ! не удалось удалить {old.name}: {e}')


def do_backup(db_path: str, keep: int, quiet: bool) -> int:
    src = Path(db_path)
    if not src.is_absolute():
        src = BASE / src
    if not src.exists():
        if not quiet:
            print(f'! БД не найдена: {src}')
        return 1

    bdir = _backup_dir_for(src)
    ts = _stamp()
    dst = bdir / f'db_{ts}.db'

    src_conn = None
    dst_conn = None
    try:
        src_conn = sqlite3.connect(str(src), timeout=30.0)
        dst_conn = sqlite3.connect(str(dst))
        with dst_conn:
            src_conn.backup(dst_conn)
    except Exception as e:
        if not quiet:
            print(f'! Ошибка бэкапа: {e}')
        try:
            if dst.exists():
                dst.unlink()
        except Exception:
            pass
        return 2
    finally:
        # PATCH: закрываем оба соединения даже при ошибке
        try:
            if dst_conn:
                dst_conn.close()
        except Exception:
            pass
        try:
            if src_conn:
                src_conn.close()
        except Exception:
            pass

    size = dst.stat().st_size
    # PATCH: свежесозданный файл защищён от удаления даже при --keep 0
    cleanup_old(bdir, keep, quiet, protect=dst)
    if not quiet:
        print(f'  ✓ Бэкап: {dst}  ({size:,} байт)'.replace(',', ' '))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='Консистентный бэкап SQLite-БД.')
    ap.add_argument('--db', default=None)
    ap.add_argument('--keep', type=int, default=KEEP_DEFAULT)
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    db = _load_db_path(args.db)
    if not db:
        if not args.quiet:
            print('! Не указан --db и не найден config.json')
        return 1
    return do_backup(db, args.keep, args.quiet)


if __name__ == '__main__':
    sys.exit(main())


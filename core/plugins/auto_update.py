#!/usr/bin/env python3
"""
auto_update.py — обновление проекта из сетевой папки.

Проверяет наличие манифеста в сетевой шаре, сравнивает с локальным
журналом применения (.patches_applied.json), докачивает и применяет
недостающие патчи через patcher.py в правильном порядке.

Использование:
    python auto_update.py                   # обновить если есть что
    python auto_update.py --dry             # показать, что будет сделано
    python auto_update.py --force           # применять даже при ошибках sha256
    python auto_update.py --share PATH      # явный путь к шаре
    python auto_update.py --quiet           # минимальный вывод

Коды возврата:
    0 — успех (обновления нет или успешно применены)
    1 — ошибка (патч не применился, sha256 mismatch и т.п.)
    2 — сеть недоступна, обновление пропущено
    3 — конфиг не найден или некорректен

Формат manifest.json (пример):
    {
      "version": "2026-10-15-01",
      "created": "2026-10-15 10:00:00",
      "min_client_version": null,
      "patches": [
        {"id": "63-fix", "file": "063-fix.json", "sha256": "abc..."},
        {"id": "64-db", "file": "064-db.json", "sha256": "def...",
         "requires": ["63-fix"]}
      ]
    }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = BASE_DIR / 'config.json'
JOURNAL_PATH = BASE_DIR / '.patches_applied.json'
PATCHER_PATH = BASE_DIR / 'patcher.py'
PATCH_RUNS_DIR = BASE_DIR / 'patch_runs'
NET_LOG_DIR = PATCH_RUNS_DIR / 'network'


def _log(msg, quiet=False, level='info'):
    if quiet and level == 'info':
        return
    prefix = {'info': '  ', 'ok': ' ✓', 'warn': ' ⚠', 'err': ' ✗'}.get(level, '  ')
    print(f'{prefix} {msg}')


def _load_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'! config.json не читается: {e}')
        return None


def _load_journal():
    if not JOURNAL_PATH.exists():
        return {}
    try:
        return json.loads(JOURNAL_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _manifest_path(share_dir: Path) -> Path:
    return share_dir / 'manifest.json'


def _read_manifest(share_dir: Path):
    mp = _manifest_path(share_dir)
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'! manifest.json не читается: {e}')
        return None


def _parse_manifest_order(manifest):
    """Возвращает список патчей в порядке манифеста.
    Проверяет, что requires указывают на уже виденные патчи."""
    patches = manifest.get('patches') or []
    seen = set()
    out = []
    for p in patches:
        pid = p.get('id') or p.get('file')
        if not pid:
            continue
        reqs = p.get('requires') or []
        missing = [r for r in reqs if r not in seen]
        if missing:
            raise ValueError(
                f'Патч "{pid}" требует {missing}, но они идут после него в манифесте. '
                'Переупорядочьте манифест.'
            )
        out.append(p)
        seen.add(pid)
    return out


def _stage_patches(share_dir: Path, patches, stage_dir: Path, force: bool, quiet: bool):
    """Копирует патчи из шары в локальную staging-папку с проверкой sha256.
    Возвращает (ok, list_of_copied_ids)."""
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for p in patches:
        pid = p.get('id') or p.get('file')
        fname = p.get('file')
        if not fname:
            _log(f'{pid}: нет поля "file" — пропуск', quiet, 'warn')
            continue
        src = share_dir / fname
        if not src.exists():
            _log(f'{pid}: файл не найден: {fname}', quiet, 'err')
            return False, copied
        expected = (p.get('sha256') or '').lower()
        if expected:
            got = _sha256(src)
            if got != expected:
                msg = f'{pid}: sha256 mismatch (ожидалось {expected[:12]}…, получено {got[:12]}…)'
                if not force:
                    _log(msg, quiet, 'err')
                    return False, copied
                _log(msg + ' — игнорируем (--force)', quiet, 'warn')
        dst = stage_dir / fname
        shutil.copy2(src, dst)
        copied.append(pid)
    return True, copied


def _run_patcher(stage_dir: Path, log_path: Path, quiet: bool) -> int:
    """Вызывает patcher.py с указанной папкой."""
    if not PATCHER_PATH.exists():
        _log(f'patcher.py не найден: {PATCHER_PATH}', quiet, 'err')
        return 1
    cmd = [sys.executable, str(PATCHER_PATH), str(stage_dir)]
    _log(f'вызов: {" ".join(cmd)}', quiet)
    try:
        with log_path.open('w', encoding='utf-8') as logf:
            proc = subprocess.run(
                cmd, cwd=str(BASE_DIR), stdout=logf,
                stderr=subprocess.STDOUT, text=True,
            )
        return proc.returncode
    except Exception as e:
        _log(f'patcher.py не запустился: {e}', quiet, 'err')
        return 1


def _prune_old_runs(keep=20):
    if not NET_LOG_DIR.exists():
        return
    files = sorted(NET_LOG_DIR.glob('network_update_*.log'),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except Exception:
            pass


def _run(share_dir, dry=False, force=False, quiet=False):
    if not PATCHER_PATH.exists():
        _log(f'patcher.py не найден рядом с auto_update.py', quiet, 'err')
        return 3

    if not share_dir.exists():
        _log(f'сетевая папка недоступна: {share_dir}', quiet, 'warn')
        return 2

    manifest = _read_manifest(share_dir)
    if not manifest:
        _log(f'manifest.json не найден в {share_dir}', quiet, 'warn')
        return 2

    _log(f'манифест: {manifest.get("version") or "?"} '
         f'от {manifest.get("created") or "?"}', quiet)

    try:
        ordered = _parse_manifest_order(manifest)
    except ValueError as e:
        _log(str(e), quiet, 'err')
        return 1

    if not ordered:
        _log('в манифесте нет патчей', quiet, 'warn')
        return 0

    journal = _load_journal()
    applied_ids = set(journal.keys())

    # Сравниваем по id, а если id нет — по имени файла без расширения
    pending = []
    for p in ordered:
        pid = p.get('id') or Path(p.get('file', '')).stem
        if pid in applied_ids:
            continue
        pending.append(p)

    if not pending:
        _log(f'все патчи уже применены ({len(applied_ids)} в журнале)', quiet)
        return 0

    _log(f'к применению: {len(pending)} патч(ей)', quiet)
    for p in pending:
        pid = p.get('id') or Path(p.get('file', '')).stem
        reqs = p.get('requires') or []
        suffix = f' (requires: {", ".join(reqs)})' if reqs else ''
        _log(f'  · {pid}{suffix}', quiet)

    if dry:
        _log('dry-run: изменения не вносились', quiet, 'warn')
        return 0

    PATCH_RUNS_DIR.mkdir(exist_ok=True)
    NET_LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = NET_LOG_DIR / f'network_update_{ts}.log'
    stage_dir = NET_LOG_DIR / f'stage_{ts}'

    # Пишем шапку в лог
    try:
        with log_path.open('w', encoding='utf-8') as f:
            f.write(f'=== Network update {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n')
            f.write(f'share: {share_dir}\n')
            f.write(f'manifest version: {manifest.get("version")}\n')
            f.write(f'patches to apply: {[p.get("id") or p.get("file") for p in pending]}\n\n')
    except Exception as e:
        _log(f'лог не создался: {e}', quiet, 'err')
        return 1

    ok, copied = _stage_patches(share_dir, pending, stage_dir, force, quiet)
    if not ok:
        _log(f'staging не удался, применение прервано', quiet, 'err')
        _log(f'лог: {log_path}', quiet, 'err')
        return 1

    _log(f'скопировано патчей: {len(copied)}', quiet, 'ok')

    rc = _run_patcher(stage_dir, log_path, quiet)
    if rc != 0:
        _log(f'patcher.py вернул код {rc}, обновление НЕ применено полностью', quiet, 'err')
        _log(f'лог: {log_path}', quiet, 'err')
        return 1

    _log(f'обновление применено, лог: {log_path}', quiet, 'ok')

    try:
        shutil.rmtree(stage_dir, ignore_errors=True)
    except Exception:
        pass
    _prune_old_runs(keep=20)

    return 0


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Обновление проекта из сетевой папки.'
    )
    ap.add_argument('--dry', action='store_true', help='только показать план')
    ap.add_argument('--force', action='store_true', help='игнорировать sha256 mismatch')
    ap.add_argument('--share', default=None, help='путь к сетевой папке (иначе из config.json)')
    ap.add_argument('--quiet', action='store_true', help='минимум вывода')
    args = ap.parse_args()

    cfg = _load_config()
    if cfg is None:
        print('! config.json не найден рядом с auto_update.py')
        return 3

    net_cfg = cfg.get('net_update') or {}
    enabled = net_cfg.get('enabled', True)
    share = args.share or net_cfg.get('share_path') or ''

    if not enabled and not args.share:
        _log('обновление из сети отключено (net_update.enabled=false)', args.quiet, 'warn')
        return 0

    if not share:
        _log('net_update.share_path не задан в config.json', args.quiet, 'warn')
        return 3

    share_dir = Path(share)

    t0 = time.monotonic()
    rc = _run(share_dir, dry=args.dry, force=args.force, quiet=args.quiet)
    dt = time.monotonic() - t0
    _log(f'завершено за {dt:.2f}s, код {rc}', args.quiet)
    return rc


if __name__ == '__main__':
    sys.exit(main())


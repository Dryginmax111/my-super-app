"""
Плагин: автоматически менять статус «зависших» задач.

Раз в сутки (по таймеру):
  • Активная задача с просрочкой ≥7 рабочих дней и без отметок ≥5 рабочих дней
    → 'paused'.
  • Активная задача с просрочкой ≥30 рабочих дней и без отметок ≥14 рабочих дней
    → 'blocked'.

Не трогает:
  • периодические задачи (тег pereodic);
  • задачи, у которых статус уже изменён (race-protection через
    WHERE status='active' в UPDATE).

Логирование: изменения пишутся в audit_log ПОСЛЕ COMMIT, чтобы не держать
блокировку БД. Если БД занята — повтор с задержкой.
"""
import json
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

__version__ = '1.2'
__description__ = 'Автозакрытие/приостановка зависших задач'

CFG_PATH = Path(__file__).parent / 'auto_close_overdue.json'

DEFAULT_CFG = {
    'enabled': True,
    'check_interval_hours': 24,
    'first_run_after_seconds': 60,
    'pause_after_days_overdue': 7,
    'pause_if_no_log_days': 5,
    'block_after_days_overdue': 30,
    'block_if_no_log_days': 14,
}


def _load_cfg():
    if not CFG_PATH.exists():
        CFG_PATH.write_text(json.dumps(DEFAULT_CFG, ensure_ascii=False, indent=2),
                            encoding='utf-8')
        return dict(DEFAULT_CFG)
    try:
        data = json.loads(CFG_PATH.read_text(encoding='utf-8'))
        out = dict(DEFAULT_CFG)
        out.update(data or {})
        return out
    except Exception:
        return dict(DEFAULT_CFG)


def _log_audit(db, kind, entity, entity_id, details):
    payload = json.dumps(details, ensure_ascii=False)[:2000]
    row = (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           None, 'plugin:auto_close_overdue', kind, entity, str(entity_id),
           payload)
    for attempt in range(10):
        try:
            if hasattr(db, 'audit_append'):
                db.audit_append(row)
            else:
                db.exec(
                    'INSERT INTO audit_log '
                    '(ts, user_id, username, kind, entity, entity_id, details) '
                    'VALUES (?,?,?,?,?,?,?)',
                    row,
                )
            return
        except Exception as e:
            if 'locked' in str(e).lower() and attempt < 9:
                time.sleep(1.0)
                continue
            print(f'[auto_close_overdue] audit failed ({attempt+1}/10): {e}')
            return


def _working_days_since(d1_iso, d2_iso):
    try:
        d1 = datetime.strptime(d1_iso, '%Y-%m-%d').date()
        d2 = datetime.strptime(d2_iso, '%Y-%m-%d').date()
    except Exception:
        return 0
    if d2 <= d1:
        return 0
    cnt = 0
    cur = d1 + timedelta(days=1)
    while cur <= d2:
        if cur.weekday() < 5:
            cnt += 1
        cur += timedelta(days=1)
    return cnt


def _run_once(db):
    today = date.today().strftime('%Y-%m-%d')
    cfg = _load_cfg()
    if not cfg.get('enabled', True):
        return

    pause_dl = int(cfg.get('pause_after_days_overdue', 7))
    pause_log = int(cfg.get('pause_if_no_log_days', 5))
    block_dl = int(cfg.get('block_after_days_overdue', 30))
    block_log = int(cfg.get('block_if_no_log_days', 14))

    # Берём только активные просроченные, исключая периодические задачи
    tasks = db.query(
        "SELECT id, name, status, deadline FROM tasks "
        "WHERE status='active' AND deadline != '' AND deadline < ? "
        "AND id NOT IN (SELECT task_id FROM task_tags WHERE tag='pereodic')",
        (today,),
    )
    if not tasks:
        return

    # Оптимизация: последняя дата отметки одним SQL-запросом
    rows = db.query(
        'SELECT task_id, MAX(date) AS last_date FROM work_logs GROUP BY task_id'
    )
    last_by_task = {}
    for r in rows:
        tid = r.get('task_id')
        dk = r.get('last_date') or ''
        if tid and dk:
            last_by_task[tid] = dk

    changes = []
    for t in tasks:
        tid = t['id']
        dl = t['deadline']
        days_ov = _working_days_since(dl, today)
        last_log = last_by_task.get(tid, '')
        days_no_log = _working_days_since(last_log, today) if last_log else 999

        new_status = None
        if days_ov >= block_dl and days_no_log >= block_log:
            new_status = 'blocked'
        elif days_ov >= pause_dl and days_no_log >= pause_log:
            new_status = 'paused'

        if new_status:
            changes.append({
                'id': tid,
                'name': t.get('name', ''),
                'new_status': new_status,
                'days_overdue_workdays': days_ov,
                'days_without_log_workdays': days_no_log,
                'applied': False,
            })

    if not changes:
        return

    # Применяем одной короткой транзакцией.
    # WHERE status='active' защищает от гонки: если пользователь уже
    # изменил статус параллельно, UPDATE не сработает, и мы не перезапишем.
    try:
        with db.transaction() as tx:
            for ch in changes:
                cur = tx.exec(
                    "UPDATE tasks SET status=? WHERE id=? AND status='active'",
                    (ch['new_status'], ch['id']),
                )
                ch['applied'] = (cur.rowcount or 0) > 0
    except Exception as e:
        print(f'[auto_close_overdue] update failed: {e}')
        return

    # Логируем ПОСЛЕ COMMIT — чтобы не держать блокировку.
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    changed_pause = changed_block = 0
    for ch in changes:
        if not ch['applied']:
            continue
        if ch['new_status'] == 'blocked':
            changed_block += 1
        else:
            changed_pause += 1
        _log_audit(db, 'update', 'task', ch['id'], {
            'action': 'auto_status_change',
            'from': 'active',
            'to': ch['new_status'],
            'days_overdue_workdays': ch['days_overdue_workdays'],
            'days_without_log_workdays': ch['days_without_log_workdays'],
            'at': now_str,
        })

    if changed_pause or changed_block:
        print(f'[auto_close_overdue] pause={changed_pause} block={changed_block}')


def _worker(db, stop_event, initial_delay):
    stop_event.wait(initial_delay)
    while not stop_event.is_set():
        try:
            _run_once(db)
        except Exception as e:
            print(f'[auto_close_overdue] loop error: {e}')
        cfg = _load_cfg()
        interval = max(1, int(cfg.get('check_interval_hours', 24))) * 3600
        stop_event.wait(interval)


_STOP = threading.Event()


def register(app, db, hooks):
    cfg = _load_cfg()
    print(f'[auto_close_overdue] v{__version__} · {__description__}')
    print(f'[auto_close_overdue] enabled={cfg.get("enabled")} '
          f'interval={cfg.get("check_interval_hours")}h')

    def on_startup(**ctx):
        if not cfg.get('enabled', True):
            return
        delay = max(5, int(cfg.get('first_run_after_seconds', 60)))
        t = threading.Thread(
            target=_worker, args=(db, _STOP, delay),
            name='auto_close_overdue', daemon=True,
        )
        t.start()

    def on_shutdown(**ctx):
        _STOP.set()

    hooks.on('on_startup', on_startup)
    hooks.on('on_shutdown', on_shutdown)


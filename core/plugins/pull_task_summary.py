"""plugins/pull_task_summary.py — Миграция: свод по задачам из work_logs.

При первом запуске добавляет в tasks колонки-агрегаты и разово
наполняет их по существующим записям. В дальнейшем поддерживает
актуальность — при каждом сохранении отметки пересчитывает свод
по её задаче.

Флаг в settings (task_summary_v1_done) защищает от повторной миграции.
Все операции идемпотентны: ALTER TABLE ADD COLUMN пропускается, если
колонка уже есть.
"""
__version__ = '1.0'
__description__ = 'Свод по задачам из work_logs: миграция + поддержка актуальности'

MIGRATION_KEY = 'task_summary_v1_done'

NEW_COLUMNS = [
    ('first_log_date', 'TEXT DEFAULT ""'),
    ('last_log_date', 'TEXT DEFAULT ""'),
    ('logs_count', 'INTEGER DEFAULT 0'),
    ('hours_total', 'REAL DEFAULT 0'),
    ('comments_count', 'INTEGER DEFAULT 0'),
    ('links_count', 'INTEGER DEFAULT 0'),
    ('employees_count', 'INTEGER DEFAULT 0'),
]


def _ensure_columns(db):
    try:
        cols = [r.get('name') for r in db.query('PRAGMA table_info(tasks)')]
    except Exception as e:
        print(f'[task_summary] PRAGMA failed: {e}')
        return False
    added = 0
    for name, spec in NEW_COLUMNS:
        if name in cols:
            continue
        try:
            db.exec(f'ALTER TABLE tasks ADD COLUMN {name} {spec}')
            added += 1
        except Exception as e:
            print(f'[task_summary] ADD COLUMN {name} failed: {e}')
    if added:
        print(f'[task_summary] добавлено колонок: {added}')
    return True


def _agg_sql():
    return (
        'SELECT task_id,'
        ' MIN(date) AS first_date,'
        ' MAX(date) AS last_date,'
        ' COUNT(*) AS logs_count,'
        ' SUM(hours) AS hours_total,'
        ' SUM(CASE WHEN comment IS NOT NULL AND comment != \'\' THEN 1 ELSE 0 END) AS comments_count,'
        ' SUM(CASE WHEN link IS NOT NULL AND link != \'\' THEN 1 ELSE 0 END) AS links_count,'
        ' COUNT(DISTINCT employee_id) AS emps'
        ' FROM work_logs'
        ' WHERE task_id != \'\''
    )


def _update_task_from_row(tx, row):
    h = round((row.get('hours_total') or 0) * 4) / 4
    tx.exec(
        'UPDATE tasks SET first_log_date=?, last_log_date=?, logs_count=?, '
        'hours_total=?, comments_count=?, links_count=?, employees_count=? '
        'WHERE id=?',
        (row.get('first_date') or '',
         row.get('last_date') or '',
         int(row.get('logs_count') or 0),
         h,
         int(row.get('comments_count') or 0),
         int(row.get('links_count') or 0),
         int(row.get('emps') or 0),
         row.get('task_id')),
    )


def _recompute_all(db):
    try:
        rows = db.query(_agg_sql() + ' GROUP BY task_id')
    except Exception as e:
        print(f'[task_summary] aggregate failed: {e}')
        return 0
    n = 0
    try:
        with db.transaction() as tx:
            for r in rows:
                _update_task_from_row(tx, r)
                n += 1
    except Exception as e:
        print(f'[task_summary] update failed: {e}')
        return 0
    return n


def _recompute_one(db, task_id):
    if not task_id:
        return
    try:
        r = db.query_one(_agg_sql() + ' AND task_id=? GROUP BY task_id', (task_id,))
        if not r:
            return
        with db.transaction() as tx:
            _update_task_from_row(tx, r)
    except Exception as e:
        print(f'[task_summary] recompute_one ({task_id}) failed: {e}')


def _run_migration(db):
    if not _ensure_columns(db):
        return
    n = _recompute_all(db)
    try:
        db.set_setting(MIGRATION_KEY, 'done')
    except Exception as e:
        print(f'[task_summary] settings write failed: {e}')
    print(f'[task_summary] миграция завершена, обработано задач: {n}')


def register(app, db, hooks):
    print('[task_summary] v' + __version__ + ' · ' + __description__)

    def on_startup(**ctx):
        try:
            if db.get_setting(MIGRATION_KEY, '') == 'done':
                print('[task_summary] миграция уже выполнена ранее')
                return
        except Exception:
            pass
        try:
            _run_migration(db)
        except Exception as e:
            print(f'[task_summary] migration failed: {e}')

    def on_log_save(user=None, log_id=None, created=False, **ctx):
        try:
            row = db.query_one('SELECT task_id FROM work_logs WHERE id=?', (log_id,))
            if row and row.get('task_id'):
                _recompute_one(db, row['task_id'])
        except Exception as e:
            print(f'[task_summary] on_log_save failed: {e}')

    hooks.on('on_startup', on_startup)
    hooks.on('on_log_save', on_log_save)

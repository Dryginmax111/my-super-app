"""plugins/backfill_task_deps.py — Миграция: подтягиваем отделы у задач.

Для каждой задачи:
  • если отделы уже заданы в task_departments — не трогаем;
  • иначе смотрим назначенных сотрудников и собираем уникальные
    отделы их отделов; каждый добавляется один раз (INSERT OR IGNORE).

Флаг settings.task_auto_deps_v1_done защищает от повторной миграции.
Даже без флага миграция безопасна: дубликаты не создаются.
"""
__version__ = '1.0'
__description__ = 'Backfill: подтянуть отделы задач из отделов сотрудников'

MIGRATION_KEY = 'task_auto_deps_v1_done'


def _run_migration(db):
    # 1. Карта: сотрудник -> department_id
    try:
        emp_rows = db.query('SELECT id, department_id FROM employees')
    except Exception as e:
        print(f'[backfill_deps] employees query failed: {e}')
        return 0
    emp_dept = {}
    for r in emp_rows:
        did = (r.get('department_id') or '').strip()
        if did:
            emp_dept[r['id']] = did

    # 2. Задачи, у которых уже есть отделы
    try:
        dep_rows = db.query('SELECT DISTINCT task_id FROM task_departments')
    except Exception as e:
        print(f'[backfill_deps] task_departments query failed: {e}')
        return 0
    tasks_with_deps = set((r.get('task_id') or '') for r in dep_rows)

    # 3. Все задачи
    try:
        tasks = db.query('SELECT id FROM tasks')
    except Exception as e:
        print(f'[backfill_deps] tasks query failed: {e}')
        return 0

    candidates = [t['id'] for t in tasks if t['id'] not in tasks_with_deps]
    if not candidates:
        print('[backfill_deps] все задачи уже имеют отделы — нечего делать')
        return 0

    # 4. Назначения
    try:
        assigns = db.query('SELECT task_id, employee_id FROM task_assignees')
    except Exception as e:
        print(f'[backfill_deps] assignees query failed: {e}')
        return 0
    assign_by_task = {}
    for a in assigns:
        assign_by_task.setdefault(a['task_id'], []).append(a['employee_id'])

    # 5. Валидные отделы
    try:
        valid_depts = set(r['id'] for r in db.query('SELECT id FROM departments'))
    except Exception:
        valid_depts = set()

    # 6. Считаем, что и куда добавить
    added = 0
    touched_tasks = 0
    changes = []  # (task_id, dept_id)
    for tid in candidates:
        emps = assign_by_task.get(tid) or []
        deps = set()
        for eid in emps:
            did = emp_dept.get(eid)
            if did and did in valid_depts:
                deps.add(did)
        if not deps:
            continue
        touched_tasks += 1
        for did in deps:
            changes.append((tid, did))

    if not changes:
        print('[backfill_deps] не найдено задач для обновления')
        return 0

    try:
        with db.transaction() as tx:
            for tid, did in changes:
                tx.exec(
                    'INSERT OR IGNORE INTO task_departments (task_id, department_id) '
                    'VALUES (?,?)', (tid, did))
                added += 1
    except Exception as e:
        print(f'[backfill_deps] insert failed: {e}')
        return 0

    print(f'[backfill_deps] обработано задач: {touched_tasks}, связей добавлено: {added}')
    return touched_tasks


def register(app, db, hooks):
    print(f'[backfill_deps] v{__version__} · {__description__}')

    def on_startup(**ctx):
        try:
            if db.get_setting(MIGRATION_KEY, '') == 'done':
                print('[backfill_deps] миграция уже выполнена ранее')
                return
        except Exception:
            pass
        try:
            n = _run_migration(db)
            if n is not None:
                db.set_setting(MIGRATION_KEY, 'done')
        except Exception as e:
            print(f'[backfill_deps] migration failed: {e}')

    hooks.on('on_startup', on_startup)

"""SQLite-слой. Оптимизирован для размещения на сетевой шаре (SMB / UNC).

Особенности:
  * thread-local соединение (одно на поток, живёт весь процесс);
  * journal_mode=PERSIST (не удаляет -journal после каждой транзакции);
  * короткий TTL-кеш load_all() (1.5 сек) с инвалидацией при записи;
  * экспоненциальный backoff на SQLITE_BUSY / 'database is locked';
  * транзакции на отдельном соединении — не задевают thread-local.
"""
import copy
import json
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

SCHEMA_PATH = Path(__file__).parent / 'schema.sql'

# === Этапы задачи (фича "этапы") =========================================
# Фиксированный порядок 8 этапов. Хранится ТОЛЬКО дата начала каждого этапа
# (колонка stage_<key>_start в tasks). Конец этапа вычисляется на лету:
# день начала следующего непустого этапа - 1; у последнего этапа конец = deadline.
TASK_STAGE_ORDER = [
    'подготовка', 'проверка_нжя', 'проверка_соглЦА', 'ос_проф',
    'реализация_возражения', 'реализация_согласования', 'запас', 'оценка_тб',
]
# Человекочитаемые подписи для UI
TASK_STAGE_LABELS = {
    'подготовка': 'Подготовка',
    'проверка_нжя': 'Проверка НЖЯ',
    'проверка_соглЦА': 'Проверка согл. ЦА',
    'ос_проф': 'ОС проф.',
    'реализация_возражения': 'Реализация возражения',
    'реализация_согласования': 'Реализация согласования',
    'запас': 'Запас',
    'оценка_тб': 'Оценка ТБ',
}
# Коэффициенты нагрузки на этап (пока все = 1.0, потом скорректируем)
TASK_STAGE_WEIGHTS = {k: 1.0 for k in TASK_STAGE_ORDER}
# Цвета этапов для диаграммы Ганта (единый источник правды)
TASK_STAGE_COLORS = {
    'подготовка': '#5dade2',
    'проверка_нжя': '#48c9b0',
    'проверка_соглЦА': '#58d68d',
    'ос_проф': '#f4d03f',
    'реализация_возражения': '#eb984e',
    'реализация_согласования': '#e59866',
    'запас': '#af7ac5',
    'оценка_тб': '#ec7063',
}
# Допустимые типы задач
TASK_TYPES = ['розничная', 'корпоративная']
# Имена колонок дат начала этапов в таблице tasks
TASK_STAGE_COLS = ['stage_%s_start' % k for k in TASK_STAGE_ORDER]
# =========================================================================


def _compute_task_stages(task):
    """Собирает список этапов задачи с вычисленными концами.

    Вход: dict задачи (строка из tasks с колонками stage_<key>_start).
    Выход: список dict в порядке TASK_STAGE_ORDER:
        {key, label, weight, color, start, end}
    start/end — строки 'YYYY-MM-DD' или '' если не определено.
    Правило конца: начало следующего НЕПУСТОГО этапа - 1 день.
    Для последнего непустого этапа конец = deadline задачи (если задан).
    Код не падает при пустых/кривых датах.
    """
    deadline = str(task.get('deadline') or '').strip()
    # Собираем (индекс, ключ, старт) только по заполненным этапам, в порядке.
    starts = []
    for idx, key in enumerate(TASK_STAGE_ORDER):
        sd = str(task.get('stage_%s_start' % key) or '').strip()
        starts.append(sd)

    def _minus_one_day(ds):
        try:
            d = datetime.strptime(ds, '%Y-%m-%d').date() - timedelta(days=1)
            return d.strftime('%Y-%m-%d')
        except Exception:
            return ''

    # Индексы непустых этапов
    filled = [i for i, sd in enumerate(starts) if sd]
    out = []
    for idx, key in enumerate(TASK_STAGE_ORDER):
        sd = starts[idx]
        end = ''
        if sd:
            # ищем следующий заполненный этап
            nxt = next((j for j in filled if j > idx), None)
            if nxt is not None:
                end = _minus_one_day(starts[nxt])
            else:
                # последний заполненный — конец = deadline
                end = deadline
        out.append({
            'key': key,
            'label': TASK_STAGE_LABELS.get(key, key),
            'weight': TASK_STAGE_WEIGHTS.get(key, 1.0),
            'color': TASK_STAGE_COLORS.get(key, '#888888'),
            'start': sd,
            'end': end,
        })
    return out


CACHE_TTL_SEC = 1.5
BUSY_RETRIES = 6
BUSY_BASE_SLEEP = 0.1


class TrackerDB:
    def __init__(self, path):
        self.path = str(path)
        p = Path(self.path)
        parent = p.parent
        if not parent.exists():
            raise RuntimeError(f'Папка для БД не найдена: {parent}')
        self._local = threading.local()
        self._cache_lock = threading.RLock()
        self._cache = None
        self._cache_ts = 0.0
        self._init_schema()

    # ---------------- соединения ----------------
    def _make_conn(self):
        c = sqlite3.connect(
            self.path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=PERSIST')
        c.execute('PRAGMA synchronous=NORMAL')
        c.execute('PRAGMA busy_timeout=30000')
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA cache_size=-16000')
        return c

    def _conn(self):
        c = getattr(self._local, 'conn', None)
        if c is None:
            c = self._make_conn()
            self._local.conn = c
        return c

    def _reset_conn(self):
        c = getattr(self._local, 'conn', None)
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
            self._local.conn = None

    # ---------------- инициализация ----------------
    def _init_schema(self):
        # PATCH v1.0.6: понятная ошибка, если schema.sql отсутствует
        if not SCHEMA_PATH.exists():
            raise RuntimeError(
                f'Файл схемы не найден: {SCHEMA_PATH}. Положите schema.sql рядом с db.py.'
            )
        try:
            sql = SCHEMA_PATH.read_text(encoding='utf-8')
        except Exception as e:
            raise RuntimeError(f'Не удалось прочитать схему {SCHEMA_PATH}: {e}')
        c = self._make_conn()
        try:
            c.executescript(sql)
        finally:
            c.close()

    # ---------------- backoff ----------------
    def _run_with_backoff(self, fn):
        last_exc = None
        for attempt in range(BUSY_RETRIES):
            try:
                return fn()
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if 'locked' in msg or 'busy' in msg:
                    last_exc = e
                    self._reset_conn()
                    sleep = BUSY_BASE_SLEEP * (2 ** attempt)
                    time.sleep(min(sleep, 3.0))
                    continue
                raise
        raise last_exc if last_exc else RuntimeError('SQLite busy')

    # ---------------- кеш ----------------
    def _invalidate_cache(self):
        with self._cache_lock:
            self._cache = None
            self._cache_ts = 0.0

    def _cache_valid(self):
        if self._cache is None:
            return False
        return (time.monotonic() - self._cache_ts) < CACHE_TTL_SEC

    # ---------------- public api ----------------
    def exec(self, sql, params=()):
        def _do():
            c = self._conn()
            cur = c.execute(sql, params)
            return cur.lastrowid
        rowid = self._run_with_backoff(_do)
        self._invalidate_cache()
        return rowid

    def query(self, sql, params=()):
        def _do():
            c = self._conn()
            return [dict(r) for r in c.execute(sql, params).fetchall()]
        return self._run_with_backoff(_do)

    def query_one(self, sql, params=()):
        def _do():
            c = self._conn()
            r = c.execute(sql, params).fetchone()
            return dict(r) if r else None
        return self._run_with_backoff(_do)

    def transaction(self):
        return _Tx(self)

    # ---------------- full load ----------------
    def load_all(self, since=None):
        """Возвращает полный слепок данных.

        since — опционально: 'YYYY-MM-DD', фильтр логов `date >= since`.
        Если since указан — кэш не используется (иначе можно отдать лишнее).
        """
        if since is None:
            with self._cache_lock:
                if self._cache_valid():
                    return copy.deepcopy(self._cache)
            data = self._load_all_uncached()
            with self._cache_lock:
                self._cache = data
                self._cache_ts = time.monotonic()
            return copy.deepcopy(data)
        # filtered: без кэша
        return self._load_all_uncached(since=since)

    def _load_all_uncached(self, since=None):
        departments = self.query('SELECT * FROM departments ORDER BY name')
        teams = self.query('SELECT * FROM teams ORDER BY name')
        members = self.query('SELECT team_id, employee_id FROM team_members')
        members_by_team = {}
        for m in members:
            members_by_team.setdefault(m['team_id'], []).append(m['employee_id'])
        for t in teams:
            t['member_ids'] = members_by_team.get(t['id'], [])

        employees = self.query('SELECT * FROM employees ORDER BY name')
        vacs = self.query('SELECT * FROM employee_vacations ORDER BY date_from')
        vac_by_emp = {}
        for v in vacs:
            vac_by_emp.setdefault(v['employee_id'], []).append({
                'id': v.get('id'),   # PATCH v1.0.6: id для удаления по реальному ключу
                'from': v['date_from'],
                'to': v['date_to'],
                'type': v['vtype'] or 'vacation',
                'comment': v['comment'] or '',
            })
        dept_name = {d['id']: d['name'] for d in departments}
        for e in employees:
            e['vacations'] = vac_by_emp.get(e['id'], [])
            e['department'] = dept_name.get(e.get('department_id', ''), '')
            e['fired'] = bool(e.get('fired'))

        # Кастомный порядок сотрудников: по команде, потом остальные.
        # Оптимизация: один проход через dict вместо N*M.
        employees_by_id = {e['id']: e for e in employees}
        placed = set()
        order = {}
        idx = 0
        for t in teams:
            mgr = t.get('manager_id')
            if mgr and mgr not in placed and mgr in employees_by_id:
                order[mgr] = idx; idx += 1; placed.add(mgr)
            tm_ids = [m for m in (t.get('member_ids') or []) 
                      if m in employees_by_id and m not in placed]
            tm = [employees_by_id[m] for m in tm_ids]
            tm.sort(key=lambda e: (e.get('name') or '').lower())
            for e in tm:
                order[e['id']] = idx; idx += 1; placed.add(e['id'])
        rest = [e for e in employees if e['id'] not in placed]
        rest.sort(key=lambda e: (e.get('name') or '').lower())
        for e in rest:
            order[e['id']] = idx; idx += 1
        employees.sort(key=lambda e: order.get(e['id'], 999999))

        tasks = self.query('SELECT * FROM tasks ORDER BY name')
        tags = self.query('SELECT task_id, tag FROM task_tags')
        tag_map = {}
        for t in tags:
            tag_map.setdefault(t['task_id'], []).append(t['tag'])
        assigns = self.query('SELECT task_id, employee_id FROM task_assignees')
        asg_map = {}
        for a in assigns:
            asg_map.setdefault(a['task_id'], []).append(a['employee_id'])
        tdep = self.query('SELECT task_id, department_id FROM task_departments')
        tdep_map = {}
        for td in tdep:
            tdep_map.setdefault(td['task_id'], []).append(td['department_id'])
        for t in tasks:
            t['tags'] = tag_map.get(t['id'], [])
            t['assignees'] = asg_map.get(t['id'], [])
            t['department_ids'] = tdep_map.get(t['id'], [])
            # PATCH v1.0.19: links_json -> список {url, description}
            try:
                _lks = json.loads(t.get('links_json') or '[]')
                if not isinstance(_lks, list):
                    _lks = []
            except Exception:
                _lks = []
            t['links'] = _lks
            # PATCH v1.0.32: orders_json -> список {description, value}
            try:
                _ords = json.loads(t.get('orders_json') or '[]')
                if not isinstance(_ords, list):
                    _ords = []
            except Exception:
                _ords = []
            t['orders'] = _ords
            # PATCH v1.0.4: extra_meta -> список {line, added_by, added_at}
            try:
                _em = json.loads(t.get('extra_meta') or '[]')
                if not isinstance(_em, list):
                    _em = []
            except Exception:
                _em = []
            t['extra_meta'] = _em
            # Этапы: собираем производный объект stages из колонок stage_*_start.
            # Конец этапа = начало следующего НЕПУСТОГО этапа - 1 день;
            # у последнего заполненного этапа конец = deadline задачи (если задан).
            t['stages'] = _compute_task_stages(t)

        if since:
            logs = self.query(
                'SELECT * FROM work_logs WHERE date >= ? ORDER BY date, id',
                (since,))
        else:
            logs = self.query('SELECT * FROM work_logs ORDER BY date, id')
        for l in logs:
            l['hours'] = float(l.get('hours') or 0)
            # PATCH v1.0.4: распаковка JSON multi-полей в логах
            for _k in ('extra_data_json', 'orders_json', 'links_json'):
                _field = _k.replace('_json', '')
                try:
                    _v = json.loads(l.get(_k) or '[]')
                    l[_field] = _v if isinstance(_v, list) else []
                except Exception:
                    l[_field] = []

        holidays = {h['date']: h['name'] for h in self.query('SELECT * FROM holidays')}

        return {
            'departments': departments,
            'teams': teams,
            'employees': employees,
            'tasks': tasks,
            'log': logs,
            'holidays': holidays,
        }

    # ---------------- employees ----------------
    def upsert_employee(self, emp_id, name, color, role, department_id, fired, fired_date, hired_date=''):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row = self.query_one('SELECT id FROM employees WHERE id=?', (emp_id,))
        hired_date = hired_date or ''
        if row:
            self.exec(
                'UPDATE employees SET name=?, color=?, role=?, department_id=?, '
                'fired=?, fired_date=?, hired_date=? WHERE id=?',
                (name, color, role, department_id, 1 if fired else 0, fired_date,
                 hired_date, emp_id))
            return False
        self.exec(
            'INSERT INTO employees (id,name,color,role,department_id,fired,fired_date,hired_date,created_at) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (emp_id, name, color, role, department_id, 1 if fired else 0, fired_date,
             hired_date, now))
        return True

    def delete_employee(self, emp_id, drop_logs=False):
        """Удаляет сотрудника.

        drop_logs=False (по умолчанию) — историю отметок сохраняем.
        drop_logs=True  — удаляем и отметки (только для admin-операций).
        """
        with self.transaction() as tx:
            tx.exec('DELETE FROM team_members WHERE employee_id=?', (emp_id,))
            tx.exec('UPDATE teams SET manager_id="" WHERE manager_id=?', (emp_id,))
            tx.exec('DELETE FROM task_assignees WHERE employee_id=?', (emp_id,))
            tx.exec('DELETE FROM employee_vacations WHERE employee_id=?', (emp_id,))
            if drop_logs:
                tx.exec('DELETE FROM work_logs WHERE employee_id=?', (emp_id,))
            tx.exec('DELETE FROM employees WHERE id=?', (emp_id,))

    def add_vacation(self, emp_id, dfrom, dto, vtype, comment):
        self.exec(
            'INSERT INTO employee_vacations (employee_id,date_from,date_to,vtype,comment) '
            'VALUES (?,?,?,?,?)',
            (emp_id, dfrom, dto, vtype, comment))

    def delete_vacation(self, emp_id, idx):
        rows = self.query(
            'SELECT id FROM employee_vacations WHERE employee_id=? ORDER BY date_from, id',
            (emp_id,))
        if idx < 0 or idx >= len(rows):
            return False
        self.exec('DELETE FROM employee_vacations WHERE id=?', (rows[idx]['id'],))
        return True

    def delete_vacation_by_id(self, vac_id):
        """Удаление по реальному ID — надёжнее, чем по индексу."""
        self.exec('DELETE FROM employee_vacations WHERE id=?', (vac_id,))
        return True

    def employee_has_overlapping_vacation(self, emp_id, dfrom, dto):
        r = self.query_one(
            'SELECT id FROM employee_vacations WHERE employee_id=? '
            'AND NOT (date_to < ? OR date_from > ?) LIMIT 1',
            (emp_id, dfrom, dto))
        return r is not None

    # ---------------- departments ----------------
    def upsert_department(self, dep_id, name, color, head_employee_id=''):
        row = self.query_one('SELECT id FROM departments WHERE id=?', (dep_id,))
        if row:
            try:
                self.exec('UPDATE departments SET name=?, color=?, head_employee_id=? WHERE id=?',
                          (name, color, head_employee_id, dep_id))
            except sqlite3.OperationalError:
                self.exec('UPDATE departments SET name=?, color=? WHERE id=?',
                          (name, color, dep_id))
            return False
        try:
            self.exec('INSERT INTO departments (id,name,color,head_employee_id) VALUES (?,?,?,?)',
                      (dep_id, name, color, head_employee_id))
        except sqlite3.OperationalError:
            self.exec('INSERT INTO departments (id,name,color) VALUES (?,?,?)',
                      (dep_id, name, color))
        return True

    def delete_department(self, dep_id):
        with self.transaction() as tx:
            tx.exec('UPDATE employees SET department_id="" WHERE department_id=?', (dep_id,))
            tx.exec('DELETE FROM task_departments WHERE department_id=?', (dep_id,))
            tx.exec('UPDATE teams SET department_id="" WHERE department_id=?', (dep_id,))
            tx.exec('DELETE FROM departments WHERE id=?', (dep_id,))

    # ---------------- teams ----------------
    def upsert_team(self, team_id, name, department_id, manager_id, member_ids):
        row = self.query_one('SELECT id FROM teams WHERE id=?', (team_id,))
        with self.transaction() as tx:
            if row:
                tx.exec('UPDATE teams SET name=?, department_id=?, manager_id=? WHERE id=?',
                        (name, department_id, manager_id, team_id))
                created = False
            else:
                tx.exec('INSERT INTO teams (id,name,department_id,manager_id) VALUES (?,?,?,?)',
                        (team_id, name, department_id, manager_id))
                created = True
            tx.exec('DELETE FROM team_members WHERE team_id=?', (team_id,))
            seen = set()
            for m in member_ids:
                if m and m not in seen:
                    seen.add(m)
                    tx.exec('INSERT OR IGNORE INTO team_members (team_id,employee_id) VALUES (?,?)',
                            (team_id, m))
        return created

    def delete_team(self, team_id):
        with self.transaction() as tx:
            tx.exec('DELETE FROM team_members WHERE team_id=?', (team_id,))
            tx.exec('DELETE FROM teams WHERE id=?', (team_id,))

    # ---------------- tasks ----------------
    def upsert_task(self, task_id, payload):
        row = self.query_one('SELECT id FROM tasks WHERE id=?', (task_id,))
        # Этапы задачи: payload['stages'] = {stage_key: 'YYYY-MM-DD'|''}
        _stages = payload.get('stages') or {}
        if not isinstance(_stages, dict):
            _stages = {}
        _stage_vals = [str(_stages.get(_k) or '').strip() for _k in TASK_STAGE_ORDER]
        _task_type = str(payload.get('task_type') or '').strip()
        if _task_type not in TASK_TYPES:
            _task_type = ''
        _pocket = str(payload.get('pocket') or '').strip()
        with self.transaction() as tx:
            if row:
                _links_json = json.dumps(payload.get('links') or [], ensure_ascii=False)
                _orders_json = json.dumps(payload.get('orders') or [], ensure_ascii=False)
                _stage_set = ', '.join('%s=?' % c for c in TASK_STAGE_COLS)
                tx.exec(
                    'UPDATE tasks SET name=?, icon=?, description=?, status=?, start_date=?, '
                    'deadline=?, completed_at=?, folder=?, order_ref=?, is_urgent=?, links_json=?, orders_json=?, '
                    'task_type=?, pocket=?, ' + _stage_set + ' WHERE id=?',
                    (payload['name'], payload['icon'], payload['description'], payload['status'],
                     payload['start_date'], payload['deadline'], payload['completed_at'],
                     payload['folder'], payload['order_ref'],
                     1 if payload.get('is_urgent') else 0, _links_json, _orders_json,
                     _task_type, _pocket, *_stage_vals, task_id))
                created = False
            else:
                _links_json = json.dumps(payload.get('links') or [], ensure_ascii=False)
                _orders_json = json.dumps(payload.get('orders') or [], ensure_ascii=False)
                _stage_cols_sql = ','.join(TASK_STAGE_COLS)
                _stage_ph = ','.join('?' for _ in TASK_STAGE_COLS)
                tx.exec(
                    'INSERT INTO tasks (id,name,icon,description,status,start_date,deadline,'
                    'completed_at,folder,order_ref,is_urgent,links_json,orders_json,'
                    'task_type,pocket,' + _stage_cols_sql + ',created_at) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,' + _stage_ph + ',?)',
                    (task_id, payload['name'], payload['icon'], payload['description'],
                     payload['status'], payload['start_date'], payload['deadline'],
                     payload['completed_at'], payload['folder'], payload['order_ref'],
                     1 if payload.get('is_urgent') else 0, _links_json, _orders_json,
                     _task_type, _pocket, *_stage_vals,
                     payload['created_at']))
                created = True
            tx.exec('DELETE FROM task_tags WHERE task_id=?', (task_id,))
            for tag in payload['tags']:
                tx.exec('INSERT OR IGNORE INTO task_tags (task_id,tag) VALUES (?,?)', (task_id, tag))
            tx.exec('DELETE FROM task_assignees WHERE task_id=?', (task_id,))
            for a in payload['assignees']:
                tx.exec('INSERT OR IGNORE INTO task_assignees (task_id,employee_id) VALUES (?,?)',
                        (task_id, a))
            tx.exec('DELETE FROM task_departments WHERE task_id=?', (task_id,))
            for d in payload['department_ids']:
                tx.exec('INSERT OR IGNORE INTO task_departments (task_id,department_id) VALUES (?,?)',
                        (task_id, d))
        return created

    def delete_task(self, task_id, drop_logs=False):
        """Удаляет задачу.

        drop_logs=False (по умолчанию) — логи остаются (их удаляет вызывающий код).
        drop_logs=True  — удаляем и логи в одной транзакции.
        """
        with self.transaction() as tx:
            tx.exec('DELETE FROM task_tags WHERE task_id=?', (task_id,))
            tx.exec('DELETE FROM task_assignees WHERE task_id=?', (task_id,))
            tx.exec('DELETE FROM task_departments WHERE task_id=?', (task_id,))
            if drop_logs:
                tx.exec('DELETE FROM work_logs WHERE task_id=?', (task_id,))
            tx.exec('DELETE FROM tasks WHERE id=?', (task_id,))

    # ---------------- logs ----------------
    def upsert_log(self, log_id, payload):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # PATCH v1.0.4: JSON multi-поля
        _edj = payload.get('extra_data_json') or '[]'
        _odj = payload.get('orders_json') or '[]'
        _lnj = payload.get('links_json') or '[]'
        if log_id:
            self.exec(
                'UPDATE work_logs SET employee_id=?, task_id=?, date=?, hours=?, comment=?, '
                'status=?, link=?, extra_data_json=?, orders_json=?, links_json=?, updated_at=? WHERE id=?',
                (payload['employee_id'], payload['task_id'], payload['date'], payload['hours'],
                 payload['comment'], payload['status'], payload['link'],
                 _edj, _odj, _lnj, now, log_id))
            return False
        new_id = self.exec(
            'INSERT INTO work_logs (employee_id,task_id,date,hours,comment,status,link,'
            'extra_data_json,orders_json,links_json,created_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (payload['employee_id'], payload['task_id'], payload['date'], payload['hours'],
             payload['comment'], payload['status'], payload['link'],
             _edj, _odj, _lnj, now))
        return new_id

    def delete_log(self, log_id):
        self.exec('DELETE FROM work_logs WHERE id=?', (log_id,))

    def copy_day_logs(self, src, dst, emp_filter):
        rows = self.query(
            'SELECT * FROM work_logs WHERE date=?' + (' AND employee_id=?' if emp_filter else ''),
            (src, emp_filter) if emp_filter else (src,))
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.transaction() as tx:
            for r in rows:
                tx.exec(
                    'INSERT INTO work_logs (employee_id,task_id,date,hours,comment,status,link,created_at) '
                    'VALUES (?,?,?,?,?,?,?,?)',
                    (r['employee_id'], r['task_id'], dst, r['hours'], r['comment'],
                     r['status'], r['link'], now))
        return len(rows)

    def clear_day_logs(self, dk, emp_filter):
        if emp_filter:
            cur = self.query('SELECT COUNT(*) as n FROM work_logs WHERE date=? AND employee_id=?',
                             (dk, emp_filter))
            self.exec('DELETE FROM work_logs WHERE date=? AND employee_id=?', (dk, emp_filter))
        else:
            cur = self.query('SELECT COUNT(*) as n FROM work_logs WHERE date=?', (dk,))
            self.exec('DELETE FROM work_logs WHERE date=?', (dk,))
        return cur[0]['n'] if cur else 0

    # ---------------- holidays ----------------
    def set_holiday(self, dk, name):
        self.exec('INSERT OR REPLACE INTO holidays (date,name) VALUES (?,?)', (dk, name))

    def delete_holiday(self, dk):
        self.exec('DELETE FROM holidays WHERE date=?', (dk,))

    # ---------------- settings ----------------
    def get_setting(self, key, default=None):
        r = self.query_one('SELECT value FROM settings WHERE key=?', (key,))
        return r['value'] if r else default

    def set_setting(self, key, value):
        # PATCH: корректная обработка None -> пустая строка
        if value is None:
            value = ''
        self.exec('INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)', (key, str(value)))

    # ---------------- users ----------------
    def users_list(self):
        return self.query(
            'SELECT id, username, role, display_name, employee_id, is_active, '
            'created_at, last_login FROM users ORDER BY username')

    def user_get_by_name(self, username):
        return self.query_one('SELECT * FROM users WHERE username=?', (username,))

    def user_get(self, uid):
        return self.query_one('SELECT * FROM users WHERE id=?', (uid,))

    def user_create(self, username, pwd_hash, role, display_name, employee_id):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # PATCH: литерал "" -> параметр '' (единый стиль, легче читать)
        return self.exec(
            'INSERT INTO users (username,kody_hash,role,display_name,employee_id,is_active,'
            'created_at,last_login) VALUES (?,?,?,?,?,1,?,?)',
            (username, pwd_hash, role, display_name, employee_id, now, ''))

    def user_update(self, uid, role, display_name, employee_id, is_active, pwd_hash=None):
        if pwd_hash:
            self.exec(
                'UPDATE users SET role=?, display_name=?, employee_id=?, is_active=?, '
                'kody_hash=? WHERE id=?',
                (role, display_name, employee_id, 1 if is_active else 0, pwd_hash, uid))
        else:
            self.exec(
                'UPDATE users SET role=?, display_name=?, employee_id=?, is_active=? WHERE id=?',
                (role, display_name, employee_id, 1 if is_active else 0, uid))

    def user_delete(self, uid):
        with self.transaction() as tx:
            tx.exec('DELETE FROM user_permissions WHERE user_id=?', (uid,))
            tx.exec('DELETE FROM users WHERE id=?', (uid,))

    def user_set_last_login(self, uid):
        self.exec('UPDATE users SET last_login=? WHERE id=?',
                  (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), uid))

    def user_permissions(self, uid):
        return {r['perm_key']: bool(r['allowed'])
                for r in self.query('SELECT perm_key, allowed FROM user_permissions WHERE user_id=?', (uid,))}

    def user_permissions_set(self, uid, perms):
        with self.transaction() as tx:
            tx.exec('DELETE FROM user_permissions WHERE user_id=?', (uid,))
            for k, v in perms.items():
                tx.exec('INSERT INTO user_permissions (user_id,perm_key,allowed) VALUES (?,?,?)',
                        (uid, k, 1 if v else 0))


class _Tx:
    """Транзакция на отдельном соединении."""
    def __init__(self, db):
        self.db = db
        self.c = None

    def __enter__(self):
        self.c = self.db._make_conn()
        try:
            self.c.execute('BEGIN IMMEDIATE')
        except Exception:
            # PATCH: не оставляем висящее соединение при ошибке BEGIN
            try:
                self.c.close()
            except Exception:
                pass
            self.c = None
            raise
        return self

    def exec(self, sql, params=()):
        return self.c.execute(sql, params)

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                try:
                    self.c.execute('ROLLBACK')
                except Exception:
                    pass
            else:
                self.c.execute('COMMIT')
        finally:
            try:
                self.c.close()
            except Exception:
                pass
            self.db._invalidate_cache()
        return False


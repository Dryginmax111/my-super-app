# -*- coding: utf-8 -*-
"""Сборка патча 1.0.11 (v1.0.11b): экспорт + фикс дубля эндпоинта + уведомления по вертикали."""
import json

PATH = '/workspace/core/tracker_patches_new/1.0.11.json'
d = json.load(open(PATH, encoding='utf-8'))
ops = d['operations']

app_op = ops[2]
c = app_op['content']
assert c.lstrip().startswith("@app.route('/api/tracker/export/debtors')"), c[:60]

# ============================================================
# 1) Guard-прелюдия к вставке в app.py: автозачистка остатков 1.0.10
#    (иначе Flask падает: "overwriting an existing endpoint function:
#     api_calendar_export_excel")
# ============================================================
GUARD = '''    # PATCH v1.0.11b: защита от дубликата эндпоинта. Если 1.0.10 был применён
    # ранее и его вставка осталась в app.py (неполный откат), Flask падает на
    # старте: "View function mapping is overwriting an existing endpoint
    # function: api_calendar_export_excel". Перед регистрацией новых роутов
    # вычищаем старые дублирующие определения прямо из исходника app.py.
    try:
        import os as _os_xe, re as _re_xe
        _app_py_xe = _os_xe.path.join(_os_xe.path.dirname(_os_xe.path.abspath(__file__)), 'app.py')
        if _os_xe.path.exists(_app_py_xe):
            with open(_app_py_xe, 'r', encoding='utf-8') as _f_xe:
                _src_xe = _f_xe.read()
            _defs_xe = list(_re_xe.finditer(
                r"def\\s+(?:api_calendar_export_excel|api_export_debtors)\\s*\\(", _src_xe))
            # дубль = больше одного def или def раньше эталонной позиции (~строка 2048)
            _need_clean_xe = len(_defs_xe) > 1 or (
                _defs_xe and _src_xe.count('\\n', 0, _defs_xe[0].start()) < 2047)
            if _need_clean_xe:
                print('[INIT] v1.0.11b: найдены остатки экспорта 1.0.10 — удаляю дубликаты из app.py')
                _lines_xe = _src_xe.split('\\n')

                def _find_def_lines(lines, name):
                    out = []
                    for i, ln in enumerate(lines):
                        if _re_xe.match(r"\\s*def\\s+" + name + r"\\s*\\(", ln):
                            out.append(i)
                    return out

                def _block_bounds(lines, di):
                    # конец блока: следующая строка нулевой индентации
                    end = len(lines) - 1
                    for j in range(di + 1, len(lines)):
                        s = lines[j]
                        if s.strip() and not s.startswith((' ', '\\t')):
                            end = j - 1
                            break
                    # начало: поднимаемся над def через декораторы @...
                    start = di - 1
                    while start >= 0:
                        prev = lines[start]
                        if prev.strip().startswith('@'):
                            start -= 1
                            continue
                        if not prev.strip():
                            start -= 1
                            continue
                        break
                    return start + 1, end

                removed_xe = 0
                for _nm in ('api_calendar_export_excel', 'api_export_debtors'):
                    while True:
                        _dl = _find_def_lines(_lines_xe, _nm)
                        if len(_dl) <= 1:
                            break
                        # оставляем самый нижний def (наш, из этой вставки),
                        # остальные блоки удаляем снизу вверх
                        _kill = _dl[:-1]
                        for _di in sorted(_kill, reverse=True):
                            _s, _e = _block_bounds(_lines_xe, _di)
                            del _lines_xe[_s:_e + 1]
                            removed_xe += 1
                if removed_xe:
                    with open(_app_py_xe, 'w', encoding='utf-8') as _f_xe:
                        _f_xe.write('\\n'.join(_lines_xe))
                    print(f'[INIT] v1.0.11b: удалено дублирующих блоков: {removed_xe}')
    except Exception as _e_xe:
        print(f'[INIT] v1.0.11b export-dedup failed: {_e_xe}')

'''

# ============================================================
# 2) Хелперы уведомлений о создании задач (дописываются в конец вставки)
# ============================================================
HELPERS = '''
    def _users_by_employee_ids(db, eids):
        """employee_id -> id активного пользователя."""
        out = {}
        try:
            for eid in set(e for e in (eids or []) if e):
                row = db.query_one(
                    'SELECT id FROM users WHERE employee_id=? AND is_active=1 LIMIT 1', (eid,))
                if row:
                    out[eid] = row['id']
        except Exception as e:
            print(f'[notify] _users_by_employee_ids failed: {e}')
        return out

    def _vertical_user_ids(db, employee_ids):
        """«Вертикаль» для набора сотрудников: руководители их команд
        (teams.manager_id) и начальники их отделов (departments.head_employee_id).
        Админы сюда НЕ включаются: если действие выполнял руководитель/админ,
        рассылка всем админам только множит однотипные уведомления."""
        uids = set()
        try:
            emps = [e for e in (employee_ids or []) if e]
            if not emps:
                return []
            ph = ','.join('?' * len(emps))
            dept_ids = set()
            for r in db.query(
                    f'SELECT DISTINCT department_id AS did FROM employees WHERE id IN ({ph})', tuple(emps)):
                if r.get('did'):
                    dept_ids.add(r['did'])
            mgr_eids = set()
            # руководители команд, где состоят эти сотрудники
            for r in db.query(
                    f'SELECT DISTINCT t.manager_id AS mid FROM teams t '
                    f'JOIN team_members tm ON tm.team_id = t.id '
                    f'WHERE tm.employee_id IN ({ph})', tuple(emps)):
                if r.get('mid'):
                    mgr_eids.add(r['mid'])
            # если сотрудник сам руководитель — его подчинённые не «вертикаль»,
            # но его собственный начальник отдела добавится ниже через dept_ids
            head_eids = set()
            if dept_ids:
                dp = ','.join('?' * len(dept_ids))
                for r in db.query(
                        f'SELECT head_employee_id AS hid FROM departments WHERE id IN ({dp})',
                        tuple(dept_ids)):
                    if r.get('hid'):
                        head_eids.add(r['hid'])
            umap = _users_by_employee_ids(db, list(mgr_eids | head_eids))
            uids.update(umap.values())
        except Exception as e:
            print(f'[notify] _vertical_user_ids failed: {e}')
        return list(uids)

    def _is_manager_user(db, user):
        """True, если пользователь — админ, руководитель команды или начальник отдела."""
        try:
            if (user or {}).get('role') == 'admin':
                return True
            _ue = ((user or {}).get('employee_id') or '').strip()
            if not _ue:
                return False
            if db.query_one('SELECT 1 FROM teams WHERE manager_id=? LIMIT 1', (_ue,)):
                return True
            if db.query_one("SELECT 1 FROM departments WHERE head_employee_id=? AND head_employee_id!=\\'\\' LIMIT 1", (_ue,)):
                return True
        except Exception:
            pass
        return False

    def _notify_task_created(db, task_id, from_user):
        """Уведомление «создана новая задача» по вертикали исполнителей задачи.
        Правило распределения: создатель (рядовой сотрудник или руководитель)
        сам НЕ получает уведомление; получают руководители команд исполнителей
        и начальники отделов. Если у задачи нет исполнителей — уведомляется
        вертикаль создателя, а для рядового сотрудника — ещё и админы."""
        try:
            from_uid = (from_user or {}).get('id')
            t = db.query_one('SELECT name, icon FROM tasks WHERE id=?', (task_id,))
            if not t:
                return
            assignees = [r.get('employee_id') or '' for r in
                         db.query('SELECT employee_id FROM task_assignees WHERE task_id=?', (task_id,))]
            assignees = [a for a in assignees if a]
            recipients = set()
            actor_is_manager = _is_manager_user(db, from_user)
            if assignees:
                recipients.update(_vertical_user_ids(db, assignees))
            else:
                recipients.update(_vertical_user_ids(db, [(from_user or {}).get('employee_id') or '']))
                if not actor_is_manager:
                    for u in db.query("SELECT id FROM users WHERE role='admin' AND is_active=1"):
                        recipients.add(u['id'])
            if from_uid is not None:
                recipients.discard(from_uid)
            if not recipients:
                return
            who = ''
            try:
                _e = db.query_one('SELECT name FROM employees WHERE id=?',
                                  (((from_user or {}).get('employee_id') or ''),))
                who = (_e or {}).get('name', '')
            except Exception:
                pass
            if not who:
                who = (from_user or {}).get('username', '')
            icon = t.get('icon') or '📋'
            msg = f'{icon} Новая задача: {t.get("name", task_id)} · создал(а) {who}'
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with db.transaction() as tx:
                for uid in recipients:
                    tx.exec(
                        'INSERT INTO notifications (ts, to_user_id, from_user_id, from_username, kind, task_id, employee_id, message) '
                        'VALUES (?,?,?,?,?,?,?,?)',
                        (now, uid, from_uid, (from_user or {}).get('username', ''),
                         'task_created', task_id, (from_user or {}).get('employee_id') or '', msg),
                    )
        except Exception as e:
            print(f'[notify] task_created failed: {e}')

'''

app_op['content'] = GUARD + c + HELPERS

# ============================================================
# 3) Операция: хук уведомления о создании задачи в api_task_save
# ============================================================
hook_op = {
    'type': 'regex',
    'path': 'app.py',
    'pattern': "(        try:\\n            app\\.config\\['PLUGIN_REGISTRY'\\]\\.emit\\('on_task_save', user=u,\\n                                                task_id=task_id, created=created\\)\\n        except Exception:\\n            pass\\n)(        return jsonify\\(\\{'success': True, 'id': task_id, 'created': created\\}\\))",
    'content': "\\1        # PATCH v1.0.11b: уведомление по вертикали о новой задаче\\n        if created:\\n            try:\\n                _notify_task_created(db, task_id, u)\\n            except Exception as _e:\\n                print(f'[notify] task_created hook failed: {_e}')\\n\\2",
    'optional': False,
}

# ============================================================
# 4) Операция: колокол различает kind=task_created (иконка 🆕)
# ============================================================
bell_find = "'<span class=\"trk-bell-ico\">✅</span>'"
bell_repl = "'<span class=\"trk-bell-ico\">' + (it.kind === 'task_created' ? '🆕' : '✅') + '</span>'"
bell_op = {'type': 'replace', 'path': 'static/tracker.js', 'find': bell_find, 'content': bell_repl}

# ============================================================
# 5) Операция: зачистить возможную leftover-кнопку экспорта из 1.0.10
# ============================================================
html_rm_op = {
    'type': 'regex',
    'path': 'templates/tracker.html',
    'pattern': '[ \\t]*<button[^>]*id="calExportExcelBtn"[^>]*>[^<]*</button>\\n?',
    'content': '',
    'optional': True,
}

# пересобираем список операций: UI → JS → app.py вставка → хук → колокол → зачистка
ui_ops = [o for o in ops if o['path'] == 'templates/tracker.html' and o['type'] == 'insert']
js_ops = [o for o in ops if o['path'] == 'static/tracker.js' and o['type'] == 'insert']
d['operations'] = ui_ops + js_ops + [app_op, hook_op, bell_op, html_rm_op]
d['description'] = (
    'Экспорт выпадающим списком: календарь + кто не заполнил отчёт. Заменяет 1.0.10. '
    'v1.0.11b: фикс краша сервера из-за дубля эндпоинта api_calendar_export_excel '
    '(остатки неприменённого/некорректно откаченного 1.0.10 — автозачистка при старте); '
    'уведомления о СОЗДАНИИ задач по вертикали (рук. команды + начальник отдела), '
    'колокол различает 🆕/✅.'
)

json.dump(d, open(PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('OK:', [(o['type'], o['path']) for o in d['operations']])

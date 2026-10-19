"""Пользователи, сессии, права.

PATCH v2: возвращены кириллические имена функций-хэширования 
(hash_пассворд, verify_kody) — они были умышленно обфусцированы 
для внутренней сети. Схема БД при этом использует латиницу 
`kody_hash` — это исторически сложилось, менять без миграции нельзя.
"""
import secrets
from functools import wraps
from flask import session, redirect, url_for, jsonify, request, g
from werkzeug.security import generate_kody_hash, check_kody_hash


PERMISSION_GROUPS = [
    {
        'title': 'Вкладки',
        'items': [
            ('tab.calendar', '📅 Календарь'),
            ('tab.tasks',    '📋 Задачи'),
            ('tab.heatmap',  '🔥 Тепловая карта'),
            ('tab.summary',  '📊 Свод'),
            ('tab.stats',    '📈 Статистика'),
            ('tab.dicts',    '⚙️ Справочники'),
            ('tab.updater',  '⬆ Обновления (просмотр)'),
            ('tab.settings', '🛠 Настройки'),
        ],
    },
    {
        'title': 'Блоки внутри вкладок',
        'items': [
            ('block.calendar.dept_filter',      'Календарь: фильтр по отделам'),
            ('block.calendar.team_filter',      'Календарь: фильтр по командам'),
            ('block.calendar.employee_filter',  'Календарь: фильтр по сотрудникам'),
            ('block.calendar.other_employees',  'Календарь: записи других сотрудников'),
            ('block.summary.full_view',         'Свод: подробный режим'),
            ('block.summary.grid_view',         'Свод: сетка по задачам'),
            ('block.summary.day_totals',        'Свод: итоги за день'),
            ('block.summary.other_employees',   'Свод: данные других сотрудников'),
            ('block.stats.other_employees',     'Статистика: данные других сотрудников'),
            ('block.stats.overdue',             'Статистика: блок просроченных'),
            ('block.heatmap.other_employees',   'Тепловая карта: данные других сотрудников'),
            ('block.dicts.employees',           'Справочник: сотрудники'),
            ('block.dicts.departments',         'Справочник: отделы'),
            ('block.dicts.teams',               'Справочник: команды'),
            ('block.dicts.tasks',               'Справочник: задачи'),
        ],
    },
    {
        'title': 'Плагины',
        'items': [
            ('plugin.pulse.use',       '💓 Пульс проекта'),
            ('plugin.stats_teams.use', '👥 Статистика по командам'),
            ('plugin.gantt.use',       '📊 Диаграмма Ганта'),
            ('plugin.weekly.use',      '📥 Недельные отчёты'),
            ('plugin.my_profile.use',  '👤 Мой профиль'),
            ('plugin.week_ach.use',    '🏆 Достижения недели'),
            ('plugin.capacity.use',    '⚖ Загрузка сотрудников'),
        ],
    },
    {
        'title': 'Действия',
        'items': [
            ('action.log.create',            'Создавать отметки'),
            ('action.log.edit.own',          'Редактировать свои отметки'),
            ('action.log.edit.any',          'Редактировать любые отметки'),
            ('action.log.delete.own',        'Удалять свои отметки'),
            ('action.log.delete.any',        'Удалять любые отметки'),
            ('action.task.create',           'Создавать задачи'),
            ('action.task.edit',             'Редактировать задачи'),
            ('action.task.delete',           'Удалять задачи'),
            ('action.employee.create',       'Создавать сотрудников'),
            ('action.employee.edit',         'Редактировать сотрудников'),
            ('action.employee.delete',       'Удалять сотрудников'),
            ('action.employee.vacation.edit','Редактировать отпуска/больничные/командировки'),
            ('action.department.create',     'Создавать отделы'),
            ('action.department.edit',       'Редактировать отделы'),
            ('action.department.delete',     'Удалять отделы'),
            ('action.team.create',           'Создавать команды'),
            ('action.team.edit',             'Редактировать команды'),
            ('action.team.delete',           'Удалять команды'),
            ('action.updater.apply',         'Применять обновления (apply/rollback)'),
            ('action.mask.use',              'Использовать маскирование ФИО'),
        ],
    },
]

ALL_PERMISSIONS = set()
for grp in PERMISSION_GROUPS:
    for k, _ in grp['items']:
        ALL_PERMISSIONS.add(k)


DEFAULT_USER_PERMISSIONS = {
    'tab.calendar',
    'tab.updater',
    'block.calendar.dept_filter',
    'block.calendar.team_filter',
    'block.calendar.employee_filter',
    'block.calendar.other_employees',
    'action.log.create',
    'action.log.edit.own',
    'plugin.my_profile.use',
    'plugin.pulse.use',
    'plugin.gantt.use',
    'plugin.stats_teams.use',
    'plugin.week_ach.use',
    'plugin.capacity.use',
}


def default_permissions_for(role):
    if role == 'admin':
        return set(ALL_PERMISSIONS)
    return set(DEFAULT_USER_PERMISSIONS)


def user_has(db, user, perm_key):
    if not user:
        return False
    if user.get('role') == 'admin':
        return True
    perms = db.user_permissions(user['id'])
    if perm_key in perms:
        return perms[perm_key]
    return perm_key in default_permissions_for(user['role'])


def effective_permissions(db, user):
    if not user:
        return {}
    if user.get('role') == 'admin':
        return {k: True for k in ALL_PERMISSIONS}
    perms = db.user_permissions(user['id'])
    out = {}
    for k in ALL_PERMISSIONS:
        out[k] = perms.get(k, k in DEFAULT_USER_PERMISSIONS)
    return out


# PATCH v2: имена функций возвращены к кириллице, как было в оригинале.
def hash_kody(pwd):
    return generate_kody_hash(pwd, method='pbkdf2:sha256:150000')


def verify_kody(pwd_hash, pwd):
    try:
        return check_kody_hash(pwd_hash, pwd)
    except Exception:
        return False


# PATCH v2: алиасы для совместимости — если где-то остался старый вызов,
# он не упадёт. Постепенно можно удалить.
hash_kody = hash_kody
verify_kody = verify_kody


def login_user(uid):
    session['uid'] = uid
    session['csrf'] = secrets.token_urlsafe(32)


def logout_user():
    session.clear()


def current_user(db):
    uid = session.get('uid')
    if not uid:
        return None
    u = db.user_get(uid)
    if not u or not u.get('is_active'):
        session.clear()
        return None
    return u


def ensure_csrf():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


def check_csrf():
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return True
    tok = request.headers.get('X-CSRF-Token') or (request.form or {}).get('csrf_token')
    # PATCH v1.0.8: явный bool (раньше возвращалось значение токена/None)
    return bool(tok) and tok == session.get('csrf')


def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get('uid'):
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'auth_required'}), 401
            return redirect(url_for('login_page'))
        # PATCH v1.0.28: uid из сессии может устареть после смены БД.
        # Проверяем, что пользователь реально есть и активен.
        db = getattr(g, 'db', None)
        if db is not None:
            try:
                if not current_user(db):
                    logout_user()
                    if request.path.startswith('/api/'):
                        return jsonify({'success': False, 'error': 'auth_required'}), 401
                    return redirect(url_for('login_page'))
            except Exception as e:
                print(f'[auth] login_required check failed: {e}')
        return f(*a, **kw)
    return w


def permission_required(perm_key):
    def deco(f):
        @wraps(f)
        def w(*a, **kw):
            user = current_user(g.db)
            if not user:
                return jsonify({'success': False, 'error': 'auth_required'}), 401
            if not user_has(g.db, user, perm_key):
                return jsonify({'success': False, 'error': 'forbidden', 'need': perm_key}), 403
            return f(*a, **kw)
        return w
    return deco



# PATCH v1.0.28: g должен быть доступен в login_required — импорт на уровне модуля
from flask import g as _flask_g  # noqa: E402

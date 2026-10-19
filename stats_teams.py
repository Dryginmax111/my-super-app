# PATCH 1.0.5: флаг «не учитывать отметки на будущее»
_STATS_IGNORE_FUTURE = True

"""plugins/stats_teams.py — Статистика: Отделы (верхний уровень) + Команды (как раньше)."""

__version__ = '4.0'
__description__ = 'Статистика: KPI отделов + команд, radar, лидерборд, тренды, топ-сотрудники'

from datetime import date, datetime, timedelta
from flask import request, jsonify, Response, redirect


# ============================================================
# Утилиты
# ============================================================
def _parse_iso(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None


def _iso(d):
    return d.strftime('%Y-%m-%d')


def _period_from_args():
    preset = (request.args.get('preset') or 'month').strip().lower()
    today = date.today()
    if preset == 'week':
        monday = today - timedelta(days=today.weekday())
        return monday, today, 'week'
    if preset == 'month':
        return today.replace(day=1), today, 'month'
    if preset == 'prev_month':
        first_cur = today.replace(day=1)
        last_prev = first_cur - timedelta(days=1)
        return last_prev.replace(day=1), last_prev, 'prev_month'
    if preset == 'quarter':
        m = (today.month - 1) // 3 * 3 + 1
        return today.replace(month=m, day=1), today, 'quarter'
    d1 = _parse_iso(request.args.get('from') or '')
    d2 = _parse_iso(request.args.get('to') or '')
    if d1 and d2 and d1 <= d2:
        return d1, d2, 'custom'
    return today.replace(day=1), today, 'month'


def _prev_period(d1, d2):
    span = (d2 - d1).days + 1
    return d1 - timedelta(days=span), d1 - timedelta(days=1)


def _workdays_between(d1, d2):
    n = 0
    cur = d1
    while cur <= d2:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


def _emp_stats(data, emp_ids, d1, d2):
    today = _iso(date.today())
    logs = data.get('log', [])
    all_assignees = {}
    for t in data.get('tasks', []):
        for a in (t.get('assignees') or []):
            all_assignees.setdefault(a, []).append(t)

    # PATCH v1.0.5: предвычисляем last_done по (employee, task) за один проход.
    # Раньше был O(E*T*N) — теперь O(N + E*T).
    last_done_map = {}
    for l in logs:
        if l.get('status') != 'done':
            continue
        eid = l.get('employee_id')
        tid = l.get('task_id')
        d = l.get('date') or ''
        if not eid or not tid or not d:
            continue
        key = (eid, tid)
        cur = last_done_map.get(key)
        if not cur or d > cur:
            last_done_map[key] = d

    per = {}
    for eid in emp_ids:
        per[eid] = {'hours': 0.0, 'tasks_done': 0, 'logs_count': 0,
                    'active_days': set(), 'overdue_tasks': [], 'done_task_ids': set()}

    for l in logs:
        ld = l.get('date') or ''
        if ld < _iso(d1) or ld > _iso(d2):
            continue
        if _STATS_IGNORE_FUTURE and ld > today:
            continue
        eid = l.get('employee_id')
        if eid not in per:
            continue
        per[eid]['logs_count'] += 1
        try:
            h = float(l.get('hours') or 0)
        except Exception:
            h = 0
        per[eid]['hours'] += h
        per[eid]['active_days'].add(ld)
        tid = l.get('task_id')
        if tid and l.get('status') == 'done':
            per[eid]['done_task_ids'].add(tid)

    for eid, st in per.items():
        st['hours'] = round(st['hours'] * 4) / 4
        st['tasks_done'] = len(st['done_task_ids'])
        st['active_days'] = len(st['active_days'])
        overdue = []
        for t in all_assignees.get(eid, []):
            if t.get('status') not in ('active', 'paused'):
                continue
            dl = t.get('deadline') or ''
            if not dl or dl >= today:
                continue
            if last_done_map.get((eid, t['id'])):
                continue
            overdue.append(t)
        st['overdue_tasks'] = overdue
        st['overdue_count'] = len(overdue)

    return per


def _compute_extras(data, emp_ids, d1, d2):
    from datetime import datetime as _dt
    tasks = {t['id']: t for t in data.get('tasks', [])}
    logs = data.get('log', [])
    start_iso = _iso(d1)
    end_iso = _iso(d2)

    on_time = 0
    late = 0
    cycles = []

    for l in logs:
        if l.get('employee_id') not in emp_ids:
            continue
        if l.get('status') != 'done':
            continue
        ld = l.get('date') or ''
        if ld < start_iso or ld > end_iso:
            continue
        if _STATS_IGNORE_FUTURE and ld > _iso(date.today()):
            continue
        t = tasks.get(l.get('task_id'))
        if not t:
            continue
        dl = t.get('deadline') or ''
        if dl:
            if ld <= dl:
                on_time += 1
            else:
                late += 1
        fdate = None
        for l2 in logs:
            if l2.get('task_id') != l.get('task_id'):
                continue
            if l2.get('employee_id') not in emp_ids:
                continue
            d = l2.get('date') or ''
            if not fdate or d < fdate:
                fdate = d
        if fdate and ld >= fdate:
            try:
                delta = (_dt.strptime(ld, '%Y-%m-%d') - _dt.strptime(fdate, '%Y-%m-%d')).days
                cycles.append(delta)
            except Exception:
                pass

    total_done = on_time + late
    on_time_pct = round(100 * on_time / total_done) if total_done else 0
    cycle_avg = round(sum(cycles) / len(cycles), 1) if cycles else 0

    trend = []
    end = d2
    for w in range(4):
        w_end = end - timedelta(days=7 * w)
        w_start = w_end - timedelta(days=6)
        if w_start < d1 - timedelta(days=90):
            break
        hours = 0.0
        for l in logs:
            if l.get('employee_id') not in emp_ids:
                continue
            ld = l.get('date') or ''
            if _iso(w_start) <= ld <= _iso(w_end):
                try:
                    hours += float(l.get('hours') or 0)
                except Exception:
                    pass
        trend.append({'from': _iso(w_start), 'to': _iso(w_end), 'hours': round(hours * 4) / 4})
    trend.reverse()

    return {'on_time_pct': on_time_pct, 'cycle_avg_days': cycle_avg, 'trend': trend}


def _aggregate(data, name, emp_ids, d1, d2, prev=None, extra=None):
    """Универсальный агрегатор для команды и отдела."""
    per = _emp_stats(data, emp_ids, d1, d2)
    wd = _workdays_between(d1, d2)
    total_hours = 0.0
    total_done = 0
    total_overdue = 0
    active = 0
    for st in per.values():
        total_hours += st['hours']
        total_done += st['tasks_done']
        total_overdue += st['overdue_count']
        if st['hours'] > 0:
            active += 1
    total_hours = round(total_hours * 4) / 4
    possible_hours = wd * 8 * len(emp_ids)
    coverage = round(100 * total_hours / possible_hours) if possible_hours else 0
    avg_per_emp = round(total_hours / len(emp_ids) * 4) / 4 if emp_ids else 0

    def meta(eid):
        e = next((x for x in data.get('employees', []) if x['id'] == eid), None)
        return {'id': eid, 'name': (e.get('name') if e else eid), 'color': (e.get('color') if e else '#888')}

    ranking_hours = sorted([dict(meta(eid), hours=st['hours']) for eid, st in per.items()], key=lambda x: -x['hours'])[:3]
    ranking_done = sorted([dict(meta(eid), tasks_done=st['tasks_done']) for eid, st in per.items() if st['tasks_done'] > 0], key=lambda x: -x['tasks_done'])[:3]
    ranking_coverage = sorted([dict(meta(eid), coverage=round(100 * st['active_days'] / wd) if wd else 0) for eid, st in per.items()], key=lambda x: -x['coverage'])[:3]

    extras = _compute_extras(data, emp_ids, d1, d2)

    def _delta(cur, prv):
        try:
            cur = float(cur); prv = float(prv)
            if prv == 0:
                return {'abs': round(cur, 2), 'pct': 0 if cur == 0 else 100}
            return {'abs': round(cur - prv, 2), 'pct': round(100 * (cur - prv) / prv)}
        except Exception:
            return {'abs': 0, 'pct': 0}

    deltas = {}
    if prev:
        deltas = {
            'hours': _delta(total_hours, prev.get('total_hours', 0)),
            'done': _delta(total_done, prev.get('total_done', 0)),
            'coverage': _delta(coverage, prev.get('coverage', 0)),
            'overdue': _delta(total_overdue, prev.get('total_overdue', 0)),
        }

    result = {
        'name': name,
        'members_count': len(emp_ids),
        'active_members': active,
        'total_hours': total_hours,
        'total_done': total_done,
        'total_overdue': total_overdue,
        'coverage': coverage,
        'possible_hours': possible_hours,
        'avg_per_emp': avg_per_emp,
        'workdays': wd,
        'top_hours': ranking_hours,
        'top_done': ranking_done,
        'top_coverage': ranking_coverage,
        'extras': extras,
        'deltas': deltas,
        'overdue_tasks': [{'id': t['id'], 'name': t.get('name', ''), 'icon': t.get('icon', '📋'), 'deadline': t.get('deadline', '')} for t in sum([st['overdue_tasks'] for st in per.values()], [])][:10],
    }
    if extra:
        result.update(extra)
    return result


# ============================================================
# JS — кнопка в шапку
# ============================================================
_JS = r'''
(function(){
'use strict';
function register(){
    if (typeof window.__trkRegisterPlugin !== 'function') {
        setTimeout(register, 200);
        return;
    }
    window.__trkRegisterPlugin({
        id: 'stats_teams',
        icon: '👥',
        name: 'Статистика по командам',
        url: '/plugins/stats_teams/',
        perm: 'plugin.stats_teams.use'
    });
}
register();
})();
'''


# ============================================================
# HTML
# ============================================================
def _page_html():
    return r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Статистика по командам</title>
<script src="/static/plugin_theme.js"></script>
<script src="/static/plugin_mask.js"></script>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 0; padding: 16px; font-size: 14px; background: var(--pg-bg, #0f0f0f); background-attachment: fixed; color: var(--pg-text, #e8e8e8); min-height: 100vh; }
.w { max-width: 1800px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }
.head { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; padding: 14px 18px; background: var(--pg-card-bg, #1a1a1a); border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22)); border-radius: 14px; }
.head h1 { margin: 0; font-size: 1.2rem; font-weight: 800; color: var(--pg-accent, #f5d76e); }
.back { color: var(--pg-desc, #c8c8c8); text-decoration: none; padding: 6px 14px; border: 1px solid var(--pg-card-border); border-radius: 20px; font-size: 0.85rem; }
.back:hover { background: var(--pg-accent-bg); color: var(--pg-accent); }
.presets { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
.presets button { padding: 6px 14px; border-radius: 8px; background: transparent; border: 1px solid var(--pg-card-border); color: var(--pg-desc); font-size: 0.82rem; font-weight: 700; cursor: pointer; font-family: inherit; }
.presets button:hover { color: var(--pg-accent); border-color: var(--pg-accent); }
.presets button.active { background: var(--pg-accent-bg); border-color: var(--pg-accent); color: var(--pg-accent); }
.period { padding: 6px 8px; border-radius: 8px; border: 1px solid var(--pg-input-border); background: var(--pg-input-bg); color: var(--pg-text); font-family: inherit; font-size: 0.8rem; }

.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.kpi { padding: 14px 16px; background: var(--pg-card-bg); border: 1px solid var(--pg-card-border); border-radius: 12px; }
.kpi .v { font-size: 1.5rem; font-weight: 800; line-height: 1.05; color: var(--pg-accent); }
.kpi .l { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.8px; color: var(--pg-meta); font-weight: 700; margin-top: 4px; }
.kpi.danger .v { color: var(--pg-err, #ec7063); }
.kpi.warn .v { color: var(--pg-warn, #f7dc6f); }
.kpi.ok .v { color: var(--pg-ok, #58d68d); }
.kpi.info .v { color: var(--pg-info, #6dc2f0); }

.section-h { display: flex; align-items: center; gap: 10px; padding: 10px 16px; background: var(--pg-card-bg); border: 1px solid var(--pg-card-border); border-radius: 12px; font-size: 0.9rem; font-weight: 800; color: var(--pg-text); }
.section-h .icon { font-size: 1.15rem; }
.section-h .cnt { margin-left: auto; font-size: 0.7rem; padding: 2px 10px; border-radius: 10px; background: var(--pg-accent-bg); color: var(--pg-accent); font-weight: 700; }
.section-h select { padding: 5px 10px; border-radius: 8px; border: 1px solid var(--pg-input-border); background: var(--pg-input-bg); color: var(--pg-text); font-family: inherit; font-size: 0.8rem; }

/* ОТДЕЛЫ — карточки */
.depts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
.dept-card { padding: 16px 18px; background: var(--pg-card-bg); border: 1px solid var(--pg-card-border); border-radius: 14px; position: relative; display: flex; flex-direction: column; gap: 12px; cursor: pointer; transition: border-color .15s, transform .15s, box-shadow .15s; }
.dept-card:hover { border-color: var(--pg-accent); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.25); }
.dept-card.is-filtered { border-color: var(--pg-accent); box-shadow: 0 0 0 2px var(--pg-accent-bg); }
.dept-card::before { content: ''; position: absolute; left: 0; top: 20px; bottom: 20px; width: 5px; border-radius: 0 5px 5px 0; background: var(--dept-color, var(--pg-accent)); }
.dept-head { display: flex; align-items: baseline; gap: 8px; padding-left: 10px; flex-wrap: wrap; }
.dept-name { font-size: 1.05rem; font-weight: 800; color: var(--pg-text); }
.dept-mgr { font-size: 0.72rem; color: var(--pg-meta); margin-left: auto; }
.dept-mgr b { color: var(--pg-desc); }
.dept-kpi { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding-left: 10px; }
.kpi-cell { text-align: center; padding: 8px 4px; background: var(--pg-inner-bg); border-radius: 10px; }
.kpi-v { font-size: 1.05rem; font-weight: 800; color: var(--pg-accent); }
.kpi-l { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--pg-meta); margin-top: 2px; font-weight: 700; }
.cover-bar { height: 6px; background: rgba(128,128,128,0.16); border-radius: 3px; overflow: hidden; margin: 0 10px; }
.cover-fill { height: 100%; border-radius: 3px; }
.cover-fill.ok { background: linear-gradient(90deg, #58d68d, #239b56); }
.cover-fill.warn { background: linear-gradient(90deg, #f7dc6f, #d4ac0d); }
.cover-fill.err { background: linear-gradient(90deg, #ec7063, #b03a2e); }
.cover-info { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--pg-meta); padding: 0 10px; }

/* КОМАНДЫ — карточки как раньше */
.teams-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }
.team-card { padding: 16px 18px; background: var(--pg-card-bg); border: 1px solid var(--pg-card-border); border-radius: 14px; position: relative; display: flex; flex-direction: column; gap: 12px; }
.team-card::before { content: ''; position: absolute; left: 0; top: 20px; bottom: 20px; width: 4px; background: linear-gradient(180deg, var(--pg-accent), var(--pg-accent-2)); border-radius: 0 4px 4px 0; }
.team-head { display: flex; align-items: baseline; gap: 8px; padding-left: 8px; flex-wrap: wrap; }
.team-name { font-size: 1rem; font-weight: 800; color: var(--pg-text); }
.team-mgr { font-size: 0.72rem; color: var(--pg-meta); margin-left: auto; }
.team-kpi { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding-left: 8px; }
.rank-block { padding: 8px 10px; background: var(--pg-inner-bg); border-radius: 10px; }
.rank-title { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.6px; color: var(--pg-meta); font-weight: 800; margin-bottom: 6px; }
.rank-row { display: grid; grid-template-columns: 22px 26px 1fr auto; gap: 8px; align-items: center; padding: 4px 0; }
.rank-medal { font-size: 0.95rem; text-align: center; }
.rank-avatar { width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: 800; font-size: 0.6rem; text-shadow: 0 1px 3px rgba(0,0,0,0.4); }
.rank-name { font-size: 0.82rem; color: var(--pg-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-val { font-size: 0.75rem; font-weight: 800; color: var(--pg-accent); padding: 1px 8px; border-radius: 8px; background: var(--pg-accent-bg); }
.ov-tasks { padding: 8px 10px; background: rgba(231,76,60,0.08); border-left: 3px solid var(--pg-err, #ec7063); border-radius: 8px; }
.ov-tasks .ot-title { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.6px; color: var(--pg-err, #ec7063); font-weight: 800; margin-bottom: 4px; }
.ov-tasks .ot-row { font-size: 0.78rem; color: var(--pg-desc); padding: 2px 0; display: flex; gap: 6px; }
.ov-tasks .ot-dl { color: var(--pg-meta); font-size: 0.7rem; margin-left: auto; }

/* Графики */
.charts-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 1100px) { .charts-2col { grid-template-columns: 1fr; } }
.chart-block { padding: 14px 16px; background: var(--pg-card-bg); border: 1px solid var(--pg-card-border); border-radius: 14px; }
.chart-title { font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.7px; color: var(--pg-accent); margin-bottom: 12px; }
.chart-wrap svg { display: block; width: 100%; height: auto; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; font-size: 0.72rem; color: var(--pg-meta); }

.leaderboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }
.lb-block { padding: 12px 14px; background: var(--pg-inner-bg); border-radius: 12px; }
.lb-title { font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: var(--pg-meta); margin-bottom: 8px; }
.lb-row { display: grid; grid-template-columns: 28px 1fr auto; gap: 8px; align-items: center; padding: 5px 0; font-size: 0.82rem; }
.lb-medal { font-size: 1rem; text-align: center; }
.lb-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.lb-val { font-weight: 800; font-size: 0.75rem; padding: 2px 10px; border-radius: 8px; background: var(--pg-accent-bg); color: var(--pg-accent); white-space: nowrap; }
.lb-val.err { background: rgba(231,76,60,0.18); color: var(--pg-err, #ec7063); }
.lb-val.ok { background: rgba(46,204,113,0.18); color: var(--pg-ok, #58d68d); }

/* Таблица */
.card { padding: 16px 18px; background: var(--pg-card-bg); border: 1px solid var(--pg-card-border); border-radius: 14px; }
.card-title { display: flex; align-items: center; gap: 8px; font-size: 0.78rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; color: var(--pg-accent); margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px dashed var(--pg-card-border-soft); }
table.cmp { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
table.cmp th, table.cmp td { padding: 8px 10px; border-bottom: 1px solid var(--pg-card-border-soft); }
table.cmp th { text-align: left; font-size: 0.68rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: var(--pg-meta); white-space: nowrap; }
table.cmp th.num, table.cmp td.num { text-align: right; }
table.cmp tbody tr:hover td { background: var(--pg-inner-bg); }
table.cmp td.num { font-weight: 700; }
table.cmp td.best { color: var(--pg-ok, #58d68d); }
table.cmp td.worst { color: var(--pg-err, #ec7063); }
table.cmp .delta-up { color: var(--pg-ok, #58d68d); }
table.cmp .delta-down { color: var(--pg-err, #ec7063); }
.tm-cell { display: flex; align-items: center; gap: 8px; }
.tm-dot { width: 10px; height: 10px; border-radius: 50%; background: linear-gradient(135deg, var(--pg-accent), var(--pg-accent-2)); }
.dept-chip { display: inline-block; font-size: 0.65rem; padding: 1px 7px; border-radius: 6px; background: var(--pg-inner-bg); color: var(--pg-meta); font-weight: 700; margin-left: 6px; }

.empty, .loading { text-align: center; padding: 40px; color: var(--pg-meta); font-style: italic; }
@media (max-width: 700px) { .head { padding: 12px 14px; } .head h1 { font-size: 1rem; } .dept-kpi, .team-kpi { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<div class="w">

    <div class="head">
        <a class="back" href="/">← К трекеру</a>
        <h1>📊 Статистика</h1>
        <div class="presets">
            <button data-preset="week">Неделя</button>
            <button data-preset="month" class="active">Месяц</button>
            <button data-preset="prev_month">Прошлый месяц</button>
            <button data-preset="quarter">Квартал</button>
        </div>
        <input type="date" id="stFrom" class="period">
        <input type="date" id="stTo" class="period">
        <button class="period" id="stApply">✓</button>
    </div>

    <div class="kpis" id="kpis"></div>

    <!-- ВЕРХНИЙ УРОВЕНЬ: ОТДЕЛЫ -->
    <div class="section-h">
        <span class="icon">🏢</span><span>Отделы</span>
        <span class="cnt" id="deptsCount">0</span>
    </div>

    <div class="charts-2col">
        <div class="chart-block">
            <div class="chart-title">⏱ Часы по отделам</div>
            <div class="chart-wrap" id="chartDeptHours"></div>
        </div>
        <div class="chart-block">
            <div class="chart-title">📅 Покрытие отделов, %</div>
            <div class="chart-wrap" id="chartDeptCoverage"></div>
        </div>
    </div>

    <div class="depts-grid" id="deptsGrid"><div class="loading">Загрузка…</div></div>

    <div class="card">
        <div class="card-title"><span>📋</span><span>Сводная таблица отделов</span></div>
        <div id="deptTable"><div class="empty">Загрузка…</div></div>
    </div>

    <!-- НИЖНИЙ УРОВЕНЬ: КОМАНДЫ (как было в v2) -->
    <div class="section-h">
        <span class="icon">👥</span><span>Команды</span>
        <select id="teamDeptFilter"><option value="">Все отделы</option></select>
        <span class="cnt" id="teamsCount">0</span>
    </div>

    <div class="charts-2col">
        <div class="chart-block">
            <div class="chart-title">🎯 Многомерное сравнение команд</div>
            <div class="chart-wrap" id="chartRadar"></div>
            <div class="chart-legend" id="radarLegend"></div>
        </div>
        <div class="chart-block">
            <div class="chart-title">🏆 Лидеры среди команд</div>
            <div class="leaderboard" id="leaderboard"></div>
        </div>
    </div>

    <div class="charts-2col">
        <div class="chart-block"><div class="chart-title">⏱ Часы за период</div><div class="chart-wrap" id="chartHours"></div></div>
        <div class="chart-block"><div class="chart-title">📅 Покрытие, %</div><div class="chart-wrap" id="chartCoverage"></div></div>
        <div class="chart-block"><div class="chart-title">✅ Закрыто задач</div><div class="chart-wrap" id="chartDone"></div></div>
        <div class="chart-block"><div class="chart-title">⚠ Просрочено задач</div><div class="chart-wrap" id="chartOverdue"></div></div>
    </div>

    <div class="card">
        <div class="card-title"><span>📋</span><span>Сводная таблица команд</span></div>
        <div id="compareTable"><div class="empty">Загрузка…</div></div>
    </div>

    <div class="section-h">
        <span class="icon">🔎</span><span>Детали по командам</span>
        <span class="cnt" id="teamsDetailsCount">0</span>
    </div>

    <div class="teams-grid" id="teamsGrid"><div class="loading">Загрузка…</div></div>

</div>

<script>
(function(){
'use strict';

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function initials(n){var p=String(n||'').trim().split(/\s+/);if(!p.length)return'?';if(p.length===1)return p[0].slice(0,2).toUpperCase();return (p[0][0]+(p[1][0]||'')).toUpperCase();}
function fmtH(h){h=Number(h)||0;if(h===Math.floor(h))return h+' ч';return h.toFixed(2).replace(/0+$/,'').replace(/\.$/,'')+' ч';}
function fmtI(n){return (Number(n)||0).toLocaleString('ru-RU');}
function fmtPct(n){return (Number(n)||0)+'%';}
function coverCls(n){n=Number(n)||0;if(n>=70)return'ok';if(n>=40)return'warn';return'err';}
function fmtDate(iso){if(!iso)return'';var p=iso.split('-');if(p.length!==3)return iso;return p[2]+'.'+p[1]+'.'+p[0];}

var state = { preset:'month', from:'', to:'', deptFilter:'' };
var DATA = null;

function renderKpis(s){
    var el = document.getElementById('kpis');
    var cards = [
        { v: fmtI(s.depts_count), l: 'Отделов', cls: '' },
        { v: fmtI(s.teams_count), l: 'Команд', cls: '' },
        { v: fmtH(s.hours_total), l: 'Часов всего', cls: '' },
        { v: fmtI(s.tasks_done), l: 'Задач закрыто', cls: 'ok' },
        { v: fmtI(s.tasks_overdue), l: 'Просрочено', cls: 'danger' },
        { v: fmtPct(s.coverage), l: 'Покрытие', cls: s.coverage >= 70 ? 'ok' : (s.coverage >= 40 ? 'warn' : 'danger') },
        { v: fmtI(s.active_employees)+' / '+fmtI(s.employees_total), l: 'Активных / Всего', cls: 'info' }
    ];
    el.innerHTML = cards.map(function(c){ return '<div class="kpi '+c.cls+'"><div class="v">'+c.v+'</div><div class="l">'+c.l+'</div></div>'; }).join('');
}

/* Bar chart */
function renderBars(elId, items, opts) {
    var el = document.getElementById(elId);
    if (!el) return;
    if (!items || !items.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    opts = opts || {};
    var maxV = Math.max.apply(null, items.map(function(x){return x.value;}).concat([1]));
    var colorFn = opts.colorFn || function(){ return '#f5d76e'; };
    var fmtFn = opts.fmtFn || function(v){ return v; };
    var rowsH = 30;
    var W = 560, H = items.length * rowsH + 6;
    var padL = 170, padR = 100, padT = 4;
    var innerW = W - padL - padR;
    var html = '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" style="max-height:'+Math.max(160,H)+'px;">';
    items.forEach(function(it, i){
        var bw = Math.max(2, (it.value / maxV) * innerW);
        var y = padT + i * rowsH;
        var color = colorFn(it);
        var nameShort = it.name.length > 26 ? it.name.slice(0, 24) + '…' : it.name;
        html += '<text x="'+(padL-8)+'" y="'+(y+rowsH*0.6)+'" font-size="11" fill="var(--pg-text)" text-anchor="end">'+esc(nameShort)+'</text>';
        html += '<rect x="'+padL+'" y="'+(y+5)+'" width="'+bw+'" height="'+(rowsH-12)+'" fill="'+color+'" rx="3" opacity="0.85"><title>'+esc(it.name)+': '+esc(fmtFn(it.value))+'</title></rect>';
        html += '<text x="'+(padL+bw+6)+'" y="'+(y+rowsH*0.6)+'" font-size="11" font-weight="700" fill="var(--pg-accent)">'+esc(fmtFn(it.value))+'</text>';
    });
    html += '</svg>';
    el.innerHTML = html;
}

/* Radar */
function renderRadar(elId, legendId, teams, axes) {
    var el = document.getElementById(elId);
    var legend = document.getElementById(legendId);
    if (!el) return;
    if (!teams || teams.length < 2) { el.innerHTML = '<div class="empty">Нужно ≥ 2 команды</div>'; if (legend) legend.innerHTML = ''; return; }
    var W = 560, H = 420;
    var cx = W/2, cy = H/2 + 10, R = 145;
    var n = axes.length;
    var norm = {};
    axes.forEach(function(ax){
        var vals = teams.map(function(t){ return Number(ax.get(t)) || 0; });
        norm[ax.key] = { min: Math.min.apply(null, vals), max: Math.max.apply(null, vals), invert: !!ax.invert };
    });
    function point(i, t) {
        var ax = axes[i];
        var v = Number(ax.get(t)) || 0;
        var r = norm[ax.key];
        var pct = (r.max === r.min) ? 1 : (v - r.min) / (r.max - r.min);
        if (r.invert) pct = 1 - pct;
        var rr = 12 + pct * (R - 12);
        var ang = -Math.PI/2 + (i * 2 * Math.PI / n);
        return { x: cx + rr*Math.cos(ang), y: cy + rr*Math.sin(ang) };
    }
    var html = '<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet">';
    [0.25, 0.5, 0.75, 1].forEach(function(s){
        var r = 12 + s * (R - 12);
        var pts = [];
        for (var i = 0; i < n; i++) {
            var ang = -Math.PI/2 + (i * 2 * Math.PI / n);
            pts.push((cx + r*Math.cos(ang)).toFixed(1) + ',' + (cy + r*Math.sin(ang)).toFixed(1));
        }
        html += '<polygon points="'+pts.join(' ')+'" fill="none" stroke="rgba(128,128,128,0.20)" stroke-width="1"/>';
    });
    axes.forEach(function(ax, i){
        var ang = -Math.PI/2 + (i * 2 * Math.PI / n);
        html += '<line x1="'+cx+'" y1="'+cy+'" x2="'+(cx + R*Math.cos(ang)).toFixed(1)+'" y2="'+(cy + R*Math.sin(ang)).toFixed(1)+'" stroke="rgba(128,128,128,0.20)"/>';
        var lx = cx + (R + 24) * Math.cos(ang);
        var ly = cy + (R + 24) * Math.sin(ang);
        var anchor = 'middle';
        if (Math.cos(ang) > 0.3) anchor = 'start';
        else if (Math.cos(ang) < -0.3) anchor = 'end';
        html += '<text x="'+lx.toFixed(1)+'" y="'+(ly+4).toFixed(1)+'" font-size="11" font-weight="700" fill="var(--pg-meta)" text-anchor="'+anchor+'">'+esc(ax.label)+'</text>';
    });
    var palette = ['#f5d76e', '#5dade2', '#58d68d', '#ec7063', '#9b59b6', '#f39c12', '#1abc9c', '#e91e63', '#00bcd4', '#8bc34a', '#607d8b', '#ff5722'];
    teams.forEach(function(t, ti){
        var color = palette[ti % palette.length];
        var pts = axes.map(function(_, i){ return point(i, t); });
        var path = pts.map(function(p){ return p.x.toFixed(1) + ',' + p.y.toFixed(1); }).join(' ');
        html += '<polygon points="'+path+'" fill="'+color+'" fill-opacity="0.14" stroke="'+color+'" stroke-width="2" stroke-linejoin="round"/>';
        pts.forEach(function(p, i){
            html += '<circle cx="'+p.x.toFixed(1)+'" cy="'+p.y.toFixed(1)+'" r="3" fill="'+color+'"><title>'+esc(t.name)+' · '+esc(axes[i].label)+': '+esc(axes[i].fmt(axes[i].get(t)))+'</title></circle>';
        });
    });
    html += '</svg>';
    el.innerHTML = html;
    if (legend) {
        legend.innerHTML = teams.map(function(t, ti){
            var color = palette[ti % palette.length];
            return '<span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:12px;height:12px;border-radius:3px;background:'+color+';"></span>'+esc(t.name)+'</span>';
        }).join('');
    }
}

/* Leaderboard (по командам) */
function renderLeaderboard(teams){
    var el = document.getElementById('leaderboard');
    if (!el) return;
    if (!teams || !teams.length) { el.innerHTML = '<div class="empty">Нет команд</div>'; return; }
    function topBy(fn, fmt, cls) {
        return teams.slice().sort(function(a, b){ return fn(b) - fn(a); }).slice(0, 3).map(function(t, i){
            var medal = i === 0 ? '🥇' : (i === 1 ? '🥈' : '🥉');
            return '<div class="lb-row"><span class="lb-medal">'+medal+'</span><span class="lb-name">'+esc(t.name)+'</span><span class="lb-val '+(cls||'')+'">'+fmt(fn(t))+'</span></div>';
        }).join('');
    }
    function bottomBy(fn, fmt, cls) {
        return teams.slice().sort(function(a, b){ return fn(a) - fn(b); }).slice(0, 3).map(function(t, i){
            return '<div class="lb-row"><span class="lb-medal">'+(i+1)+'</span><span class="lb-name">'+esc(t.name)+'</span><span class="lb-val '+(cls||'err')+'">'+fmt(fn(t))+'</span></div>';
        }).join('');
    }
    el.innerHTML = ''
        + '<div class="lb-block"><div class="lb-title">🏆 Больше всего часов</div>'+topBy(function(t){return t.total_hours;}, fmtH)+'</div>'
        + '<div class="lb-block"><div class="lb-title">✅ Больше всего закрыто</div>'+topBy(function(t){return t.total_done;}, function(v){return fmtI(v)+' шт';}, 'ok')+'</div>'
        + '<div class="lb-block"><div class="lb-title">📅 Лучшее покрытие</div>'+topBy(function(t){return t.coverage;}, fmtPct, 'ok')+'</div>'
        + '<div class="lb-block"><div class="lb-title">⚠ Меньше просрочек</div>'+bottomBy(function(t){return t.total_overdue;}, function(v){return fmtI(v);}, 'ok')+'</div>';
}

/* Сводная таблица — универсальная */
function renderCompareTable(elId, rows, opts) {
    var el = document.getElementById(elId);
    if (!el) return;
    if (!rows || !rows.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    opts = opts || {};
    var showDept = !!opts.showDept;
    function best(fn, invert) { var vals = rows.map(function(r){ return fn(r) || 0; }); return invert ? Math.min.apply(null, vals) : Math.max.apply(null, vals); }
    var bH = best(function(r){return r.total_hours;});
    var bD = best(function(r){return r.total_done;});
    var bC = best(function(r){return r.coverage;});
    var wC = best(function(r){return r.coverage;}, true);
    var bO = best(function(r){return (r.extras||{}).on_time_pct || 0;});
    var minOv = best(function(r){return r.total_overdue;}, true);
    var maxOv = best(function(r){return r.total_overdue;});
    var html = '<table class="cmp"><thead><tr><th>Название</th>';
    if (showDept) html += '<th>Отдел</th>';
    html += '<th class="num">Часов</th><th class="num">Закрыто</th><th class="num">Покрытие</th><th class="num">В срок</th><th class="num">Просроч.</th><th class="num">Актив.</th><th class="num">Δ часов</th></tr></thead><tbody>';
    rows.forEach(function(r){
        var d = r.deltas || {};
        var dHtml = '<td class="num">';
        if (d.hours) {
            var s = d.hours.pct >= 0 ? '+' : '';
            dHtml += '<span class="' + (d.hours.pct >= 0 ? 'delta-up' : 'delta-down') + '">'+s+fmtPct(d.hours.pct)+'</span>';
        } else dHtml += '<span style="opacity:0.4;">—</span>';
        dHtml += '</td>';
        var ex = r.extras || {};
        html += '<tr><td><div class="tm-cell"><span class="tm-dot"></span><span>'+esc(r.name)+'</span></div></td>';
        if (showDept) html += '<td>' + (r.department_name ? '<span class="dept-chip">'+esc(r.department_name)+'</span>' : '<span style="opacity:0.4;">—</span>') + '</td>';
        html += '<td class="num '+(r.total_hours===bH?'best':'')+'">'+fmtH(r.total_hours)+'</td>'
             + '<td class="num '+(r.total_done===bD?'best':'')+'">'+fmtI(r.total_done)+'</td>'
             + '<td class="num '+(r.coverage===bC?'best':(r.coverage===wC?'worst':''))+'">'+fmtPct(r.coverage)+'</td>'
             + '<td class="num '+((ex.on_time_pct||0)===bO?'best':'')+'">'+fmtPct(ex.on_time_pct||0)+'</td>'
             + '<td class="num '+(r.total_overdue===minOv?'best':(r.total_overdue===maxOv?'worst':''))+'">'+fmtI(r.total_overdue)+'</td>'
             + '<td class="num">'+fmtI(r.active_members)+'/'+fmtI(r.members_count)+'</td>'
             + dHtml + '</tr>';
    });
    html += '</tbody></table>';
    el.innerHTML = html;
}

/* Карточки отделов */
function renderDeptCard(d){
    var color = d.department_color || '#f5d76e';
    var cls = coverCls(d.coverage);
    var isFiltered = state.deptFilter === d.department_id ? ' is-filtered' : '';
    var mgr = d.manager_id ? 'Рук.: <b>'+esc(d.manager_id)+'</b>' : '';
    var teamsChips = (d.teams || []).map(function(t){
        return '<span class="team-chip" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:8px;background:var(--pg-accent-bg);color:var(--pg-accent);font-size:0.72rem;font-weight:700;">'+esc(t.name)+' <span style="color:var(--pg-meta);font-weight:500;">'+fmtH(t.total_hours)+'</span></span>';
    }).join('');
    var html = '<div class="dept-card'+isFiltered+'" style="--dept-color:'+esc(color)+';" data-dept-id="'+esc(d.department_id)+'">'
        + '<div class="dept-head"><div class="dept-name">'+esc(d.name)+'</div>'+(mgr?'<div class="dept-mgr">'+mgr+'</div>':'')+'</div>'
        + '<div class="dept-kpi">'
        + '<div class="kpi-cell"><div class="kpi-v">'+fmtH(d.total_hours)+'</div><div class="kpi-l">Часов</div></div>'
        + '<div class="kpi-cell"><div class="kpi-v">'+fmtI(d.total_done)+'</div><div class="kpi-l">Закрыто</div></div>'
        + '<div class="kpi-cell"><div class="kpi-v" style="color:'+(d.total_overdue?'#ec7063':'#f5d76e')+';">'+fmtI(d.total_overdue)+'</div><div class="kpi-l">Просроч.</div></div>'
        + '</div>'
        + '<div class="cover-bar"><div class="cover-fill '+cls+'" style="width:'+Math.min(d.coverage,100)+'%;"></div></div>'
        + '<div class="cover-info"><span>Покрытие '+fmtPct(d.coverage)+'</span><span>'+fmtH(d.total_hours)+' / '+fmtH(d.possible_hours)+'</span></div>'
        + '<div class="cover-info"><span>Активных: '+fmtI(d.active_members)+' / '+fmtI(d.members_count)+'</span><span>Ср.: '+fmtH(d.avg_per_emp)+'</span></div>'
        + (teamsChips?'<div style="display:flex;flex-wrap:wrap;gap:4px;padding:8px 10px;background:var(--pg-inner-bg);border-radius:10px;">'+teamsChips+'</div>':'')
        + '</div>';
    return html;
}

/* Карточки команд (как было в v2) */
function renderTeamCard(t){
    var mgrTxt = t.manager_id ? 'Рук.: <b>'+esc(t.manager_id)+'</b>' : 'Без руководителя';
    var deptChip = t.department_name ? '<span class="dept-chip" style="margin-left:0;margin-right:6px;">'+esc(t.department_name)+'</span>' : '';
    var cls = coverCls(t.coverage);
    var ex = t.extras || {};
    var d = t.deltas || {};
    var html = '<div class="team-head">'+deptChip+'<div class="team-name">'+esc(t.name)+'</div><div class="team-mgr">'+mgrTxt+'</div></div>';
    html += '<div class="team-kpi">'
         + '<div class="kpi-cell"><div class="kpi-v">'+fmtH(t.total_hours)+'</div><div class="kpi-l">Часов</div></div>'
         + '<div class="kpi-cell"><div class="kpi-v">'+fmtI(t.total_done)+'</div><div class="kpi-l">Закрыто</div></div>'
         + '<div class="kpi-cell"><div class="kpi-v" style="color:'+(t.total_overdue?'#ec7063':'#f5d76e')+';">'+fmtI(t.total_overdue)+'</div><div class="kpi-l">Просроч.</div></div>'
         + '</div>';
    html += '<div class="cover-bar"><div class="cover-fill '+cls+'" style="width:'+Math.min(t.coverage,100)+'%;"></div></div>';
    html += '<div class="cover-info"><span>Покрытие '+fmtPct(t.coverage)+'</span><span>'+fmtH(t.total_hours)+' / '+fmtH(t.possible_hours)+'</span></div>';
    html += '<div class="cover-info"><span>Активных: '+fmtI(t.active_members)+' / '+fmtI(t.members_count)+'</span><span>Ср.: '+fmtH(t.avg_per_emp)+'</span></div>';
    html += '<div class="team-kpi" style="grid-template-columns: repeat(3, 1fr);">'
         + '<div class="kpi-cell"><div class="kpi-v">'+fmtPct(ex.on_time_pct)+'</div><div class="kpi-l">В срок</div></div>'
         + '<div class="kpi-cell"><div class="kpi-v">'+(ex.cycle_avg_days?ex.cycle_avg_days+' дн':'—')+'</div><div class="kpi-l">Cycle</div></div>'
         + (d.hours ? '<div class="kpi-cell"><div class="kpi-v" style="color:'+(d.hours.pct>=0?'#58d68d':'#ec7063')+';">'+(d.hours.pct>=0?'+':'')+fmtPct(d.hours.pct)+'</div><div class="kpi-l">Δ часов</div></div>' : '<div class="kpi-cell"><div class="kpi-v">—</div><div class="kpi-l">Δ часов</div></div>')
         + '</div>';
    html += renderRank('🏆 Топ по часам', t.top_hours, 'hours');
    html += renderRank('✅ Топ по закрытым', t.top_done, 'done');
    if (t.overdue_tasks && t.overdue_tasks.length) {
        html += '<div class="ov-tasks"><div class="ot-title">⚠ Просроченные задачи</div>';
        t.overdue_tasks.slice(0, 5).forEach(function(ot){
            html += '<div class="ot-row"><span>'+esc(ot.icon||'📋')+' '+esc(ot.name)+'</span><span class="ot-dl">'+fmtDate(ot.deadline)+'</span></div>';
        });
        html += '</div>';
    }
    var card = document.createElement('div');
    card.className = 'team-card';
    card.innerHTML = html;
    return card;
}

function renderRank(title, rows, kind){
    if (!rows || !rows.length) return '';
    var h = '<div class="rank-block"><div class="rank-title">'+title+'</div>';
    rows.forEach(function(r, i){
        var medal = i === 0 ? '🥇' : (i === 1 ? '🥈' : '🥉');
        var val = kind === 'hours' ? fmtH(r.hours) : (kind === 'done' ? fmtI(r.tasks_done)+' шт' : fmtPct(r.coverage));
        h += '<div class="rank-row"><span class="rank-medal">'+medal+'</span><span class="rank-avatar" style="background:'+esc(r.color||'#888')+';">'+esc(initials(r.name))+'</span><span class="rank-name">'+(window.__trkEscName?window.__trkEscName(r.name):esc(r.name))+'</span><span class="rank-val">'+val+'</span></div>';
    });
    return h + '</div>';
}

function load(){
    var q = '?preset='+encodeURIComponent(state.preset);
    if (state.preset === 'custom') q += '&from='+encodeURIComponent(state.from)+'&to='+encodeURIComponent(state.to);
    fetch('/api/plugins/stats_teams/data'+q, {credentials:'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){ if (!d || !d.success) { alert('Ошибка загрузки'); return; } DATA = d; renderAll(); })
        .catch(function(){ alert('Ошибка соединения'); });
}

function renderAll(){
    if (!DATA) return;
    var depts = DATA.departments || [];
    var teams = DATA.teams || [];

    renderKpis(DATA.summary || {});

    // --- Отделы ---
    document.getElementById('deptsCount').textContent = depts.length;
    var sel = document.getElementById('teamDeptFilter');
    sel.innerHTML = '<option value="">Все отделы</option>';
    depts.forEach(function(d){
        var o = document.createElement('option');
        o.value = d.department_id;
        o.textContent = d.name;
        if (d.department_id === state.deptFilter) o.selected = true;
        sel.appendChild(o);
    });

    renderBars('chartDeptHours', depts.map(function(d){return {name: d.name, value: d.total_hours};}), {
        colorFn: function(it){ return it.value > 0 ? '#f5d76e' : '#607d8b'; }, fmtFn: fmtH
    });
    renderBars('chartDeptCoverage', depts.map(function(d){return {name: d.name, value: d.coverage};}), {
        colorFn: function(it){ return it.value >= 70 ? '#58d68d' : (it.value >= 40 ? '#f7dc6f' : '#ec7063'); }, fmtFn: fmtPct
    });

    var dg = document.getElementById('deptsGrid');
    dg.innerHTML = depts.length ? depts.map(renderDeptCard).join('') : '<div class="empty">Нет отделов</div>';
    dg.querySelectorAll('.dept-card').forEach(function(card){
        card.addEventListener('click', function(){
            var did = this.getAttribute('data-dept-id');
            state.deptFilter = (state.deptFilter === did) ? '' : did;
            document.getElementById('teamDeptFilter').value = state.deptFilter;
            renderAll();
        });
    });

    renderCompareTable('deptTable', depts, { showDept: false });

    // --- Команды ---
    var filtered = state.deptFilter ? teams.filter(function(t){ return t.department_id === state.deptFilter; }) : teams;
    document.getElementById('teamsCount').textContent = filtered.length;

    var axes = [
        { key: 'hours', label: 'Часы', get: function(t){ return t.total_hours; }, fmt: fmtH },
        { key: 'coverage', label: 'Покрытие', get: function(t){ return t.coverage; }, fmt: fmtPct },
        { key: 'on_time', label: 'В срок %', get: function(t){ return (t.extras||{}).on_time_pct || 0; }, fmt: fmtPct },
        { key: 'active', label: 'Активных', get: function(t){ return t.active_members; }, fmt: fmtI },
        { key: 'no_over', label: 'Без просрочек', get: function(t){ return t.total_overdue; }, invert: true, fmt: function(v){ return fmtI(v) + ' просроч.'; } }
    ];
    renderRadar('chartRadar', 'radarLegend', filtered.slice(0, 8), axes);
    renderLeaderboard(filtered);

    renderBars('chartHours', filtered.map(function(t){return {name: t.name, value: t.total_hours};}), {
        colorFn: function(){ return '#f5d76e'; }, fmtFn: fmtH
    });
    renderBars('chartCoverage', filtered.map(function(t){return {name: t.name, value: t.coverage};}), {
        colorFn: function(it){ return it.value >= 70 ? '#58d68d' : (it.value >= 40 ? '#f7dc6f' : '#ec7063'); }, fmtFn: fmtPct
    });
    renderBars('chartDone', filtered.map(function(t){return {name: t.name, value: t.total_done};}), {
        colorFn: function(){ return '#5dade2'; }, fmtFn: function(v){ return fmtI(v)+' шт'; }
    });
    renderBars('chartOverdue', filtered.map(function(t){return {name: t.name, value: t.total_overdue};}), {
        colorFn: function(){ return '#ec7063'; }, fmtFn: function(v){ return fmtI(v)+' шт'; }
    });

    renderCompareTable('compareTable', filtered, { showDept: true });

    var tg = document.getElementById('teamsGrid');
    document.getElementById('teamsDetailsCount').textContent = filtered.length;
    tg.innerHTML = '';
    if (!filtered.length) { tg.innerHTML = '<div class="empty">Нет команд по фильтру</div>'; return; }
    filtered.forEach(function(t){ tg.appendChild(renderTeamCard(t)); });
}

document.querySelectorAll('.presets button').forEach(function(b){
    b.addEventListener('click', function(){
        document.querySelectorAll('.presets button').forEach(function(x){ x.classList.remove('active'); });
        this.classList.add('active');
        state.preset = this.getAttribute('data-preset');
        load();
    });
});
document.getElementById('stApply').addEventListener('click', function(){
    var f = document.getElementById('stFrom').value;
    var t = document.getElementById('stTo').value;
    if (!f || !t) return;
    state.preset = 'custom'; state.from = f; state.to = t;
    document.querySelectorAll('.presets button').forEach(function(x){ x.classList.remove('active'); });
    load();
});
document.getElementById('teamDeptFilter').addEventListener('change', function(){
    state.deptFilter = this.value;
    renderAll();
});

load();
})();
</script>
</body>
</html>'''


# ============================================================
# Регистрация
# ============================================================
def register(app, db, hooks):
    print('[stats_teams] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/stats_teams.js', methods=['GET'])
    def _st_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/plugins/stats_teams/', methods=['GET'])
    def _st_page():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return redirect('/login')
            if not user_has(db, u, 'plugin.stats_teams.use'):
                return redirect('/')
        except Exception:
            return redirect('/login')
        return Response(_page_html(), mimetype='text/html')

    @app.route('/api/plugins/stats_teams/data', methods=['GET'])
    def _st_data():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return jsonify({'success': False, 'error': 'auth'}), 401
            if not user_has(db, u, 'plugin.stats_teams.use'):
                return jsonify({'success': False, 'error': 'forbidden'}), 403
        except Exception:
            return jsonify({'success': False, 'error': 'auth'}), 401

        d1, d2, preset = _period_from_args()
        prev_start, prev_end = _prev_period(d1, d2)
        data = db.load_all()
        global _STATS_IGNORE_FUTURE
        try:
            _STATS_IGNORE_FUTURE = str(db.get_setting('stats_ignore_future', '1')) != '0'
        except Exception:
            _STATS_IGNORE_FUTURE = True

        all_teams = data.get('teams', [])
        all_depts = data.get('departments', [])
        all_emps = data.get('employees', [])
        depts_by_id = {d['id']: d for d in all_depts}

        # Определяем, к какому отделу относится каждая команда
        team_to_dept = {}
        for tm in all_teams:
            did = tm.get('department_id') or ''
            if not did:
                counts = {}
                member_ids = list(tm.get('member_ids') or [])
                if tm.get('manager_id'):
                    member_ids.append(tm['manager_id'])
                for eid in member_ids:
                    e = next((x for x in all_emps if x['id'] == eid), None)
                    if e and e.get('department_id'):
                        counts[e['department_id']] = counts.get(e['department_id'], 0) + 1
                if counts:
                    did = max(counts.items(), key=lambda kv: kv[1])[0]
            team_to_dept[tm['id']] = did

        # --- Команды (как в v2) ---
        teams_out = []
        for tm in all_teams:
            emp_ids = set()
            if tm.get('manager_id'):
                emp_ids.add(tm['manager_id'])
            for m in (tm.get('member_ids') or []):
                if m:
                    emp_ids.add(m)
            dept_id = team_to_dept.get(tm['id'], '')
            dept = depts_by_id.get(dept_id) or {}
            prev_agg = _aggregate(data, tm.get('name', ''), emp_ids, prev_start, prev_end) if emp_ids else None
            agg = _aggregate(data, tm.get('name', ''), emp_ids, d1, d2, prev=prev_agg, extra={
                'team_id': tm['id'],
                'team_name': tm.get('name', ''),
                'manager_id': tm.get('manager_id', ''),
                'department_id': dept_id,
                'department_name': dept.get('name', ''),
                'department_color': dept.get('color', ''),
            })
            teams_out.append(agg)
        teams_out.sort(key=lambda t: -t['total_hours'])

        # --- Отделы (верхний уровень, НОВОЕ) ---
        depts_out = []
        for dep in all_depts:
            did = dep['id']
            emp_ids = set()
            # все сотрудники отдела
            for e in all_emps:
                if e.get('department_id') == did and not e.get('fired'):
                    emp_ids.add(e['id'])
            # плюс все сотрудники команд этого отдела
            for tm in all_teams:
                if team_to_dept.get(tm['id']) == did:
                    if tm.get('manager_id'):
                        emp_ids.add(tm['manager_id'])
                    for m in (tm.get('member_ids') or []):
                        if m:
                            emp_ids.add(m)

            prev_agg = _aggregate(data, dep.get('name', ''), emp_ids, prev_start, prev_end) if emp_ids else None
            agg = _aggregate(data, dep.get('name', ''), emp_ids, d1, d2, prev=prev_agg, extra={
                'department_id': did,
                'department_name': dep.get('name', ''),
                'department_color': dep.get('color', '#f5d76e'),
                'manager_id': dep.get('head_employee_id') or '',
                'teams': [
                    {'name': t['team_name'], 'total_hours': t['total_hours'], 'total_done': t['total_done'], 'total_overdue': t['total_overdue'], 'coverage': t['coverage']}
                    for t in teams_out if t['department_id'] == did
                ],
                'teams_count': sum(1 for t in teams_out if t['department_id'] == did),
            })
            depts_out.append(agg)
        depts_out.sort(key=lambda d: -d['total_hours'])

        # Итоговые KPI
        all_emp_ids = set(e['id'] for e in all_emps if not e.get('fired'))
        summary_agg = _aggregate(data, 'Все', all_emp_ids, d1, d2) if all_emp_ids else {
            'total_hours': 0, 'total_done': 0, 'total_overdue': 0, 'coverage': 0,
            'active_members': 0, 'members_count': 0
        }
        summary = {
            'depts_count': len(depts_out),
            'teams_count': len(teams_out),
            'employees_total': len(all_emp_ids),
            'active_employees': summary_agg['active_members'],
            'hours_total': summary_agg['total_hours'],
            'tasks_done': summary_agg['total_done'],
            'tasks_overdue': summary_agg['total_overdue'],
            'coverage': summary_agg['coverage'],
        }

        return jsonify({
            'success': True,
            'period': {'from': _iso(d1), 'to': _iso(d2), 'preset': preset},
            'summary': summary,
            'departments': depts_out,
            'teams': teams_out,
        })

    def on_startup(**ctx):
        print('[stats_teams] готов — отделы + команды')

    hooks.on('on_startup', on_startup)


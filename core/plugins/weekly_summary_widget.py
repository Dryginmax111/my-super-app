"""plugins/weekly_summary_widget.py — Виджет недельного свода.

Добавляет на вкладку «Календарь» компактный блок со статистикой
за текущую неделю (понедельник — воскресенье):
  • Всего часов за неделю
  • Топ-5 сотрудников по часам
  • Кол-во просроченных активных задач
  • Средняя загрузка (% от нормы 8ч × рабочих дней)

PATCH 1.0.20: маскирование ФИО в топе сотрудников, HTML-экранирование.
"""
__version__ = '1.1'
__description__ = 'Виджет «Свод за неделю» на вкладке Календарь'

import json
from datetime import date, timedelta


def _monday_of(d):
    return d - timedelta(days=d.weekday())


def _working_days_between(a, b):
    cur = a
    n = 0
    while cur <= b:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


_JS = r'''
(function(){
'use strict';

function fmtHours(h){
    h = Number(h) || 0;
    if (h === Math.floor(h)) return h + ' ч';
    return h.toFixed(2).replace(/0+$/, '').replace(/\.$/, '') + ' ч';
}

function fmtI(n){
    return (Number(n) || 0).toLocaleString('ru-RU');
}

/* PATCH 1.0.20 — маскирование ФИО и HTML-экранирование */
function _maskEnabled(){
    try { return localStorage.getItem('reestr_tracker_mask') === '1'; }
    catch (e) { return false; }
}
function _maskName(s){
    if (!_maskEnabled()) return s;
    return String(s || '').split(/\s+/).map(function(w){
        if (w.length <= 1) return w;
        return w[0] + new Array(w.length).join('*');
    }).join(' ');
}
function _escH(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
}
function _escName(s){
    return _escH(_maskName(s));
}

function buildHtml(d){
    var top = (d.top_employees || []).map(function(e, i){
        return '<span class="wsw-top-item">'
            + '<span class="wsw-rank">' + (i + 1) + '</span>'
            + '<span class="wsw-dot" style="background:' + _escH(e.color || '#888') + ';"></span>'
            + '<span class="wsw-name">' + _escName(e.name) + '</span>'
            + '<span class="wsw-hours">' + fmtHours(e.hours) + '</span>'
            + '</span>';
    }).join('');
    var overloadCls = 'ok';
    if (d.avg_load >= 100) overloadCls = 'over';
    else if (d.avg_load >= 85) overloadCls = 'high';
    else if (d.avg_load < 50) overloadCls = 'low';
    var html = '<div class="wsw-header">'
        + '<span class="wsw-title">📅 Неделя ' + _escH(d.from_fmt) + ' — ' + _escH(d.to_fmt) + '</span>'
        + '<span class="wsw-sub">сформировано автоматически</span>'
        + '</div>'
        + '<div class="wsw-grid">'
        + '<div class="wsw-stat"><span class="wsw-stat-val">' + fmtHours(d.hours_total) + '</span><span class="wsw-stat-lbl">всего часов</span></div>'
        + '<div class="wsw-stat ' + overloadCls + '"><span class="wsw-stat-val">' + _escH(d.avg_load) + '%</span><span class="wsw-stat-lbl">средняя загрузка</span></div>'
        + '<div class="wsw-stat"><span class="wsw-stat-val">' + _escH(d.overdue_count) + '</span><span class="wsw-stat-lbl">просрочено</span></div>'
        + '<div class="wsw-stat"><span class="wsw-stat-val">' + _escH(d.working_days) + '</span><span class="wsw-stat-lbl">рабочих дней</span></div>'
        + '</div>'
        + (top ? '<div class="wsw-top"><span class="wsw-top-title">🏆 Топ по часам:</span>' + top + '</div>' : '');
    return html;
}

function inject(){
    if (!window.REESTR_PERMS || !window.REESTR_PERMS['tab.calendar']) return;
    var panel = document.getElementById('panel-calendar');
    if (!panel) return;
    if (document.getElementById('weeklySummaryWidget')) return;
    var toolbar = panel.querySelector('.cal-toolbar');
    if (!toolbar) return;
    var wrap = document.createElement('div');
    wrap.id = 'weeklySummaryWidget';
    wrap.className = 'wsw-wrap';
    wrap.innerHTML = '<div class="wsw-loading">Загрузка недельного свода…</div>';
    toolbar.parentNode.insertBefore(wrap, toolbar.nextSibling);
    fetch('/api/plugins/weekly_summary/data', {credentials: 'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (!d.success) { wrap.innerHTML = ''; wrap.style.display = 'none'; return; }
            wrap.innerHTML = buildHtml(d);
        })
        .catch(function(){ wrap.innerHTML = ''; wrap.style.display = 'none'; });
}

function boot(){ setTimeout(inject, 500); setTimeout(inject, 1500); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();

document.addEventListener('click', function(e){
    if (e.target && e.target.closest && e.target.closest('.tracker-tab[data-tab="calendar"]')) {
        setTimeout(inject, 200);
    }
});
})();
'''


_CSS = '''
.wsw-wrap {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
    background: var(--trk-hover-row);
    border: 1px solid var(--trk-card-border);
    border-radius: 12px;
}
.wsw-loading {
    color: var(--trk-meta);
    font-size: 0.82rem;
    font-style: italic;
}
.wsw-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
}
.wsw-title {
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--trk-text);
}
.wsw-sub {
    font-size: 0.72rem;
    color: var(--trk-meta);
    font-style: italic;
}
.wsw-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 8px;
}
.wsw-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 12px;
    background: var(--trk-panel-bg);
    border: 1px solid var(--trk-card-border);
    border-radius: 10px;
}
.wsw-stat-val {
    font-size: 1.2rem;
    font-weight: 800;
    color: var(--trk-accent);
    line-height: 1.1;
}
.wsw-stat-lbl {
    font-size: 0.68rem;
    color: var(--trk-meta);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 700;
}
.wsw-stat.low .wsw-stat-val { color: #2e86c1; }
.wsw-stat.ok .wsw-stat-val { color: #239b56; }
.wsw-stat.high .wsw-stat-val { color: #b7950b; }
.wsw-stat.over .wsw-stat-val { color: #c0392b; }
.wsw-top {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding-top: 6px;
    border-top: 1px dashed var(--trk-border-soft);
    font-size: 0.78rem;
}
.wsw-top-title {
    font-weight: 700;
    color: var(--trk-meta);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-size: 0.68rem;
}
.wsw-top-item {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 10px;
    background: var(--trk-panel-bg);
    border: 1px solid var(--trk-card-border);
    border-radius: 12px;
}
.wsw-rank {
    font-size: 0.68rem;
    font-weight: 800;
    color: var(--trk-meta);
    min-width: 12px;
    text-align: center;
}
.wsw-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}
.wsw-name {
    font-weight: 600;
    color: var(--trk-text);
}
.wsw-hours {
    font-weight: 800;
    color: var(--trk-accent);
    margin-left: 4px;
}
body.trk-theme-light .wsw-wrap {
    background: #ffffff;
    border-color: rgba(0,0,0,0.14);
}
body.trk-theme-light .wsw-stat,
body.trk-theme-light .wsw-top-item {
    background: #f7f9fa;
    border-color: rgba(0,0,0,0.12);
}
'''


def _collect_stats(db):
    data = db.load_all()
    today = date.today()
    monday = _monday_of(today)
    sunday = monday + timedelta(days=6)
    from_iso = monday.strftime('%Y-%m-%d')
    to_iso = sunday.strftime('%Y-%m-%d')

    employees = {e['id']: e for e in data.get('employees', [])}
    holidays = data.get('holidays', {}) or {}

    logs = data.get('log', [])
    week_logs = [l for l in logs if from_iso <= (l.get('date') or '') <= to_iso]

    hours_by_emp = {}
    hours_total = 0.0
    for l in week_logs:
        try:
            h = float(l.get('hours') or 0)
        except Exception:
            h = 0
        eid = l.get('employee_id')
        hours_by_emp[eid] = hours_by_emp.get(eid, 0.0) + h
        hours_total += h

    top_employees = []
    for eid, h in sorted(hours_by_emp.items(), key=lambda x: -x[1])[:5]:
        e = employees.get(eid)
        if not e:
            continue
        top_employees.append({
            'name': e.get('name', ''),
            'color': e.get('color', '#888'),
            'hours': round(h * 4) / 4,
        })

    tasks = data.get('tasks', [])
    overdue_count = 0
    for t in tasks:
        if t.get('status') not in ('active', 'paused'):
            continue
        dl = t.get('deadline') or ''
        if dl and dl < today.strftime('%Y-%m-%d'):
            overdue_count += 1

    workdays = 0
    cur = monday
    while cur <= sunday:
        if cur.weekday() < 5 and cur.strftime('%Y-%m-%d') not in holidays:
            workdays += 1
        cur += timedelta(days=1)

    norm_total = workdays * 8 * max(1, len(hours_by_emp))
    avg_load = 0
    if norm_total > 0:
        avg_load = round((hours_total / norm_total) * 100)

    return {
        'from': from_iso,
        'to': to_iso,
        'from_fmt': monday.strftime('%d.%m'),
        'to_fmt': sunday.strftime('%d.%m'),
        'hours_total': round(hours_total * 4) / 4,
        'top_employees': top_employees,
        'overdue_count': overdue_count,
        'working_days': workdays,
        'avg_load': avg_load,
    }


def register(app, db, hooks):
    print(f'[weekly_summary_widget] v{__version__} · {__description__}')

    @app.route('/api/plugins/weekly_summary/data', methods=['GET'])
    def _wsw_data():
        try:
            payload = _collect_stats(db)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return app.response_class(
                json.dumps({'success': False, 'error': str(e)}),
                mimetype='application/json', status=500)
        payload['success'] = True
        return app.response_class(
            json.dumps(payload, ensure_ascii=False),
            mimetype='application/json')

    @app.route('/plugins-assets/weekly_summary_widget.js', methods=['GET'])
    def _wsw_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/plugins-assets/weekly_summary_widget.css', methods=['GET'])
    def _wsw_css():
        return app.response_class(_CSS, mimetype='text/css')

    def on_startup(**ctx):
        print('[weekly_summary_widget] готов — виджет появится на вкладке «Календарь»')
    hooks.on('on_startup', on_startup)

    @app.after_request
    def _inject_assets(resp):
        try:
            ct = resp.headers.get('Content-Type', '')
            if 'text/html' not in ct:
                return resp
            if resp.status_code != 200:
                return resp
            html = resp.get_data(as_text=True)
            if 'weekly_summary_widget.js' in html:
                return resp
            if '</body>' not in html:
                return resp
            inject = '<link rel="stylesheet" href="/plugins-assets/weekly_summary_widget.css">'
            inject += '<script src="/plugins-assets/weekly_summary_widget.js"></script>'
            html = html.replace('</body>', inject + '</body>', 1)
            resp.set_data(html)
        except Exception:
            pass
        return resp

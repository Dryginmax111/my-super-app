"""plugins/reminders.py — Умные напоминания."""
__version__ = '1.2'
__description__ = 'Умные напоминания: дедлайн сегодня/завтра, просрочки (клик → запись или день)'

from datetime import date, timedelta
from flask import jsonify


_JS = r'''
(function(){
'use strict';
var INTERVAL_MS = 5 * 60 * 1000;
function getBell() {
    var b = document.getElementById('trkBell');
    if (b) return b;
    var header = document.querySelector('.tracker-header');
    if (!header) return null;
    b = document.createElement('button');
    b.id = 'trkBell';
    b.type = 'button';
    b.className = 'theme-toggle-btn trk-bell';
    b.title = 'Напоминания';
    b.innerHTML = '🔔 <span class="trk-bell-cnt" id="trkBellCnt"></span>';
    b.addEventListener('click', function(e){ e.stopPropagation(); toggleDrop(); });
    var anchor = header.querySelector('.user-menu');
    if (anchor) header.insertBefore(b, anchor);
    else header.appendChild(b);
    var drop = document.createElement('div');
    drop.id = 'trkBellDrop';
    drop.className = 'trk-bell-drop';
    drop.style.display = 'none';
    document.body.appendChild(drop);
    document.addEventListener('click', function(e){
        if (e.target && e.target.closest && (e.target.closest('.trk-bell-item') || e.target.closest('#trkBell'))) return;
        drop.style.display = 'none';
    });
    return b;
}
function toggleDrop() {
    var d = document.getElementById('trkBellDrop');
    if (!d) return;
    d.style.display = (d.style.display === 'none') ? '' : 'none';
}
function _esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function render(items) {
    var cnt = document.getElementById('trkBellCnt');
    var drop = document.getElementById('trkBellDrop');
    var b = document.getElementById('trkBell');
    var n = items.length;
    if (cnt) cnt.textContent = n ? String(n) : '';
    if (b) b.classList.toggle('active', n > 0);
    if (!drop) return;
    if (!n) {
        drop.innerHTML = '<div class="trk-bell-empty">Напоминаний нет 👍</div>';
        return;
    }
    var html = '<div class="trk-bell-head">Напоминания (' + n + ')</div>';
    items.forEach(function(it){
        var cls = it.kind === 'overdue' ? 'trk-bell-item-overdue' : (it.kind === 'tomorrow' ? 'trk-bell-item-tomorrow' : 'trk-bell-item-today');
        var ico = it.kind === 'overdue' ? '⚠' : (it.kind === 'tomorrow' ? '⏰' : '🔥');
        html += '<div class="trk-bell-item ' + cls + '" data-task-id="' + _esc(it.task_id) + '" data-kind="' + _esc(it.kind) + '">';
        html += '<div class="trk-bell-ico">' + ico + '</div>';
        html += '<div class="trk-bell-body"><div class="trk-bell-name">' + _esc(it.task_name) + '</div>';
        html += '<div class="trk-bell-meta">' + _esc(it.label) + '</div></div>';
        html += '</div>';
    });
    drop.innerHTML = html;
}
function load() {
    var csrf = window.REESTR_CSRF || '';
    fetch('/api/plugins/reminders/me', {
        credentials: 'same-origin',
        headers: csrf ? {'X-CSRF-Token': csrf} : {}
    }).then(function(r){ return r.json(); }).then(function(d){
        if (!d || !d.success) return;
        render(d.items || []);
    }).catch(function(){});
}
function todayISO() {
    var st = window.__trkState;
    if (st && st.today) return st.today;
    var d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function findMyLatestLog(taskId, dk) {
    var st = window.__trkState;
    if (!st || !st.log) return null;
    var me = st.currentUser ? (st.currentUser.employee_id || '') : '';
    if (!me) return null;
    var best = null;
    st.log.forEach(function(l) {
        if (l.task_id !== taskId) return;
        if (l.employee_id !== me) return;
        if ((l.date || '') !== dk) return;
        if (!best || (l.id || 0) > (best.id || 0)) best = l;
    });
    return best;
}
function buildLogModalEntry(rec) {
    if (!rec) return null;
    var st = window.__trkState;
    var t = (st && st.tasks) ? st.tasks.find(function(x) { return x.id === rec.task_id; }) : null;
    var e = (st && st.employees) ? st.employees.find(function(x) { return x.id === rec.employee_id; }) : null;
    return {
        id: rec.id,
        employee_id: rec.employee_id,
        employee_name: e ? e.name : '',
        task_id: rec.task_id,
        task_name: t ? t.name : '',
        task_icon: t ? (t.icon || '📋') : '📋',
        date: rec.date,
        hours: rec.hours,
        status: rec.status || 'in_progress',
        comment: rec.comment || '',
        link: rec.link || ''
    };
}
function goToTask(tid, kind) {
    if (!tid) return;
    var tab = document.querySelector('.tracker-tab[data-tab="calendar"]');
    if (tab && !tab.classList.contains('active')) tab.click();
    var dk = todayISO();
    var isOverdue = (kind === 'overdue');
    setTimeout(function(){
        var rec = findMyLatestLog(tid, dk);
        if (rec && typeof window.__trkOpenLogModal === 'function') {
            window.__trkOpenLogModal(buildLogModalEntry(rec));
            return;
        }
        if (isOverdue && typeof window.__trkOpenLogModal === 'function') {
            var st2 = window.__trkState;
            var me2 = (st2 && st2.currentUser) ? (st2.currentUser.employee_id || '') : '';
            window.__trkOpenLogModal({
                id: null,
                employee_id: me2,
                task_id: tid,
                date: dk,
                hours: 8,
                status: 'in_progress',
                comment: '',
                link: ''
            });
            return;
        }
        if (typeof window.__trkOpenDayModal === 'function') {
            var st = window.__trkState;
            if (st) st.currentDay = dk;
            if (typeof window.__trkRenderCalendar === 'function') {
                Promise.resolve(window.__trkRenderCalendar()).then(function() {
                    window.__trkOpenDayModal(dk);
                });
            } else {
                window.__trkOpenDayModal(dk);
            }
            return;
        }
        if (typeof window.__trkOpenLogModal === 'function') {
            window.__trkOpenLogModal({
                id: null,
                employee_id: (window.__trkState && window.__trkState.currentUser) ? (window.__trkState.currentUser.employee_id || '') : '',
                task_id: tid,
                date: dk,
                hours: 8,
                status: 'in_progress',
                comment: '',
                link: ''
            });
        }
    }, 400);
}
function boot(){
    if (!window.REESTR_PERMS || !window.REESTR_PERMS['tab.calendar']) return;
    if (!getBell()) return;
    load();
    setInterval(load, INTERVAL_MS);
    document.addEventListener('click', function(e){
        var item = e.target && e.target.closest && e.target.closest('.trk-bell-item');
        if (!item) return;
        var tid = item.getAttribute('data-task-id');
        var kind = item.getAttribute('data-kind');
        var drop = document.getElementById('trkBellDrop');
        if (drop) drop.style.display = 'none';
        goToTask(tid, kind);
    });
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ setTimeout(boot, 400); });
else setTimeout(boot, 400);
})();
'''


def register(app, db, hooks):
    print('[reminders] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/reminders.js', methods=['GET'])
    def _rm_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/api/plugins/reminders/me', methods=['GET'])
    def _rm_me():
        try:
            from auth import current_user
            u = current_user(db)
        except Exception:
            u = None
        if not u:
            return jsonify({'success': False, 'error': 'auth'}), 401
        emp_id = (u.get('employee_id') or '').strip()
        if not emp_id:
            return jsonify({'success': True, 'items': []})

        data = db.load_all()
        today = date.today().strftime('%Y-%m-%d')
        tomorrow = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')

        my_tasks_today = set()
        for l in data.get('log', []):
            if l.get('employee_id') == emp_id and l.get('date') == today:
                my_tasks_today.add(l.get('task_id'))

        items = []
        for t in data.get('tasks', []):
            if t.get('status') not in ('active', 'paused'):
                continue
            if emp_id not in (t.get('assignees') or []):
                continue
            if t.get('id') in my_tasks_today:
                continue
            dl = t.get('deadline') or ''
            if not dl:
                continue
            if dl < today:
                items.append({
                    'kind': 'overdue',
                    'task_id': t.get('id'),
                    'task_name': t.get('name'),
                    'deadline': dl,
                    'label': 'Просрочена · дедлайн ' + dl,
                })
            elif dl == today:
                items.append({
                    'kind': 'today',
                    'task_id': t.get('id'),
                    'task_name': t.get('name'),
                    'deadline': dl,
                    'label': 'Дедлайн сегодня, отметки нет',
                })
            elif dl == tomorrow:
                items.append({
                    'kind': 'tomorrow',
                    'task_id': t.get('id'),
                    'task_name': t.get('name'),
                    'deadline': dl,
                    'label': 'Дедлайн завтра',
                })

        items.sort(key=lambda x: ({'overdue': 0, 'today': 1, 'tomorrow': 2}).get(x['kind'], 3))
        return jsonify({'success': True, 'items': items[:20]})

    def on_startup(**ctx):
        print('[reminders] готов — колокольчик в шапке, клик ведёт к записи')
    hooks.on('on_startup', on_startup)

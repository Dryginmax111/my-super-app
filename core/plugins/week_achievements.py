"""plugins/week_achievements.py — Достижения недели.

Считает за текущую неделю (пн–вс):
  • топ-3 по закрытым задачам (число done-отметок)
  • топ-3 по часам
  • топ-3 просроченных (deadline < сегодня, нет отметок)

Отдаёт данные через /api/plugins/week_achievements/data.
Кнопка + модалка — /plugins-assets/week_achievements.js.
PATCH 1.0.14: права, маскирование ФИО, регистрация в реестре плагинов.
"""
__version__ = '1.1'
__description__ = 'Достижения недели: топ по закрытым, по часам, просрочки'

from datetime import date, timedelta
from flask import request, jsonify


def _monday_of_week(d=None):
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def _sunday_of_week(d=None):
    return _monday_of_week(d) + timedelta(days=6)


_JS = r'''
(function(){
'use strict';

function _esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
function _fh(h){ h=Number(h)||0; if(h===Math.floor(h)) return h+' ч'; return h.toFixed(2).replace(/0+$/,'').replace(/\.$/,'')+' ч'; }
function _initials(n){ var p=String(n||'').trim().split(/\s+/); if(!p.length) return '?'; if(p.length===1) return p[0].slice(0,2).toUpperCase(); return (p[0][0]+(p[1][0]||'')).toUpperCase(); }

/* PATCH 1.0.14: маскирование ФИО */
function _maskEnabled(){ try { return localStorage.getItem('reestr_tracker_mask') === '1'; } catch(e){ return false; } }
function _maskName(s){
    if (!_maskEnabled()) return s;
    return String(s||'').split(/\s+/).map(function(w){
        if (w.length <= 1) return w;
        return w[0] + new Array(w.length).join('*');
    }).join(' ');
}
function _escName(s){ return _esc(_maskName(s)); }

/* PATCH 1.0.14: регистрация в реестре плагинов */
function registerPlugin(){
    if (typeof window.__trkRegisterPlugin !== 'function') {
        setTimeout(registerPlugin, 200);
        return;
    }
    window.__trkRegisterPlugin({
        id: 'week_achievements',
        icon: '🏆',
        name: 'Достижения недели',
        url: '#',
        onClick: openModal,
        perm: 'plugin.week_ach.use'
    });
}

function _ensureStyles(){
    if (document.getElementById('wkAchStyles')) return;
    var st = document.createElement('style');
    st.id = 'wkAchStyles';
    st.textContent = (
        '.wk-ach-modal{z-index:9000 !important;}'
        + '.wk-ach-modal .wk-modal{max-width:620px;}'
        + '.wk-ach-modal .wk-head{display:flex;align-items:center;gap:12px;padding-bottom:12px;margin-bottom:14px;border-bottom:1px solid var(--trk-card-border,rgba(245,215,110,0.18));}'
        + '.wk-ach-modal .wk-icon{font-size:2rem;line-height:1;}'
        + '.wk-ach-modal .wk-title{font-size:1.2rem;font-weight:800;color:var(--trk-accent,#f5d76e);}'
        + '.wk-ach-modal .wk-sub{font-size:0.78rem;color:var(--trk-meta);margin-top:3px;}'
        + '.wk-ach-modal .wk-section{margin-bottom:18px;}'
        + '.wk-ach-modal .wk-sec-title{font-size:0.75rem;font-weight:800;text-transform:uppercase;letter-spacing:0.7px;color:var(--trk-filter-active);padding-bottom:6px;margin-bottom:8px;border-bottom:1px dashed var(--trk-border-soft);}'
        + '.wk-ach-modal .wk-row{display:grid;grid-template-columns:30px 36px 1fr auto;gap:10px;align-items:center;padding:8px 10px;margin-bottom:4px;background:var(--trk-hover-row);border-radius:10px;}'
        + '.wk-ach-modal .wk-row-done{background:linear-gradient(90deg,rgba(46,204,113,0.08),transparent);}'
        + '.wk-ach-modal .wk-row-hours{background:linear-gradient(90deg,rgba(52,152,219,0.08),transparent);}'
        + '.wk-ach-modal .wk-row-overdue{background:linear-gradient(90deg,rgba(231,76,60,0.08),transparent);}'
        + '.wk-ach-modal .wk-medal{font-size:1.2rem;text-align:center;}'
        + '.wk-ach-modal .wk-avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:0.75rem;text-shadow:0 1px 3px rgba(0,0,0,0.4);}'
        + '.wk-ach-modal .wk-name{font-weight:700;color:var(--trk-text);font-size:0.92rem;}'
        + '.wk-ach-modal .wk-val{font-weight:800;font-size:0.82rem;color:var(--trk-accent);padding:3px 10px;border-radius:10px;background:var(--trk-filter-active-bg);white-space:nowrap;}'
        + '.wk-ach-modal .wk-row-overdue .wk-val{background:rgba(231,76,60,0.16);color:var(--trk-err);}'
        + '.wk-ach-modal .wk-empty{text-align:center;padding:16px 8px;color:var(--trk-meta);font-style:italic;font-size:0.82rem;}'
        + '.wk-ach-modal .wk-loading{text-align:center;padding:30px;color:var(--trk-meta);}'
        + 'body.trk-theme-light .wk-ach-modal .wk-title{color:#00695c;}'
    );
    document.head.appendChild(st);
}

function _getModal(){
    var m = document.getElementById('wkAchModal');
    if (m) return m;
    _ensureStyles();
    m = document.createElement('div');
    m.id = 'wkAchModal';
    m.className = 'modal wk-ach-modal';
    m.style.setProperty('z-index', '9000', 'important');
    m.innerHTML = '<div class="modal-content wk-modal">'
        + '<div class="wk-head"><span class="wk-icon">🏆</span>'
        + '<div><div class="wk-title">Достижения недели</div>'
        + '<div class="wk-sub" id="wkSub"></div></div></div>'
        + '<div id="wkBody"></div>'
        + '<div class="modal-actions"><button class="btn btn-secondary" data-wk-close="1">Закрыть</button></div>'
        + '</div>';
    document.body.appendChild(m);
    m.addEventListener('click', function(e){ if(e.target===m) m.classList.remove('active'); });
    var cb = m.querySelector('[data-wk-close]');
    if (cb) cb.addEventListener('click', function(){ m.classList.remove('active'); });
    return m;
}

function _rowHtml(p, i, kind){
    var medal = i === 0 ? '🥇' : (i === 1 ? '🥈' : '🥉');
    var cls = 'wk-row wk-row-' + kind;
    return '<div class="' + cls + '">'
        + '<span class="wk-medal">' + medal + '</span>'
        + '<span class="wk-avatar" style="background:' + _esc(p.color||'#888') + ';">' + _esc(_initials(p.name)) + '</span>'
        + '<span class="wk-name">' + _escName(p.name) + '</span>'
        + '<span class="wk-val">' + (kind === 'hours' ? _fh(p.hours) : (kind === 'done' ? (p.done_count + ' задач') : (p.overdue_count + ' просроч.'))) + '</span>'
        + '</div>';
}

function _section(title, rows, kind, emptyMsg){
    var h = '<div class="wk-section"><div class="wk-sec-title">' + title + '</div>';
    if (!rows || !rows.length) h += '<div class="wk-empty">' + emptyMsg + '</div>';
    else rows.forEach(function(r, i) { h += _rowHtml(r, i, kind); });
    h += '</div>';
    return h;
}

function openModal(){
    var m = _getModal();
    var body = m.querySelector('#wkBody');
    var sub = m.querySelector('#wkSub');
    body.innerHTML = '<div class="wk-loading">Загрузка…</div>';
    m.classList.add('active');
    fetch('/api/plugins/week_achievements/data', {credentials: 'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (!d || !d.success) { body.innerHTML = '<div class="wk-empty">Ошибка загрузки</div>'; return; }
            if (sub) sub.textContent = d.from + ' — ' + d.to;
            var html = '';
            html += _section('✅ Больше всего закрыто задач', d.top_done, 'done', 'Нет закрытых задач за неделю');
            html += _section('⏱ Больше всего часов', d.top_hours, 'hours', 'Нет отметок за неделю');
            html += _section('⚠ Просроченные задачи', d.top_overdue, 'overdue', 'Просрочек нет');
            body.innerHTML = html;
        })
        .catch(function(){ body.innerHTML = '<div class="wk-empty">Ошибка соединения</div>'; });
}

registerPlugin();

window.__trkOpenWeekAch = openModal;
window.__trkMaskNameWk = _maskName;

})();
'''


def register(app, db, hooks):
    print('[week_achievements] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/week_achievements.js', methods=['GET'])
    def _wk_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/api/plugins/week_achievements/data', methods=['GET'])
    def _wk_data():
        # PATCH 1.0.14: открытый доступ для пользователей с plugin.week_ach.use
        # или с базовым доступом к календарю/статистике.
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return jsonify({'success': False, 'error': 'auth'}), 401
            has = (user_has(db, u, 'plugin.week_ach.use')
                   or user_has(db, u, 'tab.calendar')
                   or user_has(db, u, 'tab.summary'))
            if not has:
                return jsonify({'success': False, 'error': 'forbidden'}), 403
        except Exception:
            return jsonify({'success': False, 'error': 'auth'}), 401

        monday = _monday_of_week()
        sunday = _sunday_of_week()
        dfrom = monday.strftime('%Y-%m-%d')
        dto = sunday.strftime('%Y-%m-%d')

        data = db.load_all()
        emps = {e['id']: e for e in data.get('employees', [])}

        hours_by_emp = {}
        done_by_emp = {}
        for l in data.get('log', []):
            ld = l.get('date') or ''
            if ld < dfrom or ld > dto:
                continue
            eid = l.get('employee_id')
            if not eid:
                continue
            try:
                hours_by_emp[eid] = hours_by_emp.get(eid, 0.0) + float(l.get('hours') or 0)
            except Exception:
                pass
            if l.get('status') == 'done':
                done_by_emp[eid] = done_by_emp.get(eid, 0) + 1

        today = date.today().strftime('%Y-%m-%d')

        def _pack(eid, extra):
            e = emps.get(eid, {})
            out = {'id': eid, 'name': e.get('name', eid), 'color': e.get('color', '#888')}
            out.update(extra)
            return out

        top_hours = sorted(
            [_pack(eid, {'hours': round(h * 4) / 4}) for eid, h in hours_by_emp.items()],
            key=lambda x: -x['hours']
        )[:3]
        top_done = sorted(
            [_pack(eid, {'done_count': n}) for eid, n in done_by_emp.items()],
            key=lambda x: -x['done_count']
        )[:3]

        overdue_by_emp = {}
        for t in data.get('tasks', []):
            if t.get('status') not in ('active', 'paused'):
                continue
            dl = t.get('deadline') or ''
            if not dl or dl >= today:
                continue
            for a in (t.get('assignees') or []):
                overdue_by_emp[a] = overdue_by_emp.get(a, 0) + 1
        top_overdue = sorted(
            [_pack(eid, {'overdue_count': n}) for eid, n in overdue_by_emp.items()],
            key=lambda x: -x['overdue_count']
        )[:3]

        return jsonify({
            'success': True,
            'from': dfrom,
            'to': dto,
            'top_hours': top_hours,
            'top_done': top_done,
            'top_overdue': top_overdue,
        })

    def on_startup(**ctx):
        print('[week_achievements] готов — пункт в реестре плагинов')

    hooks.on('on_startup', on_startup)

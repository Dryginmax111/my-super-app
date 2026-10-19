"""plugins/capacity.py — Ёмкость и загрузка сотрудников v3.0."""
__version__ = '3.0'
__description__ = 'Загрузка: ёмкость vs остаток по задачам, описание формулы в футере'

from datetime import date, datetime, timedelta
from flask import request, jsonify, Response, redirect


_JS = r'''
(function(){
'use strict';
function register(){
    if (typeof window.__trkRegisterPlugin !== 'function') {
        setTimeout(register, 200);
        return;
    }
    window.__trkRegisterPlugin({
        id: 'capacity',
        icon: '⚖',
        name: 'Загрузка сотрудников',
        url: '/plugins/capacity/',
        perm: 'plugin.capacity.use'
    });
}
register();
})();
'''


def _page_html():
    return r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Загрузка сотрудников</title>
<script src="/static/plugin_theme.js"></script>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;margin:0;padding:16px;font-size:14px;background:var(--pg-bg,#0f0f0f);background-attachment:fixed;color:var(--pg-text,#e8e8e8);min-height:100vh}
.w{max-width:1500px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
.head{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:14px 18px;background:var(--pg-card-bg,#1a1a1a);border:1px solid var(--pg-card-border,rgba(245,215,110,0.22));border-radius:14px}
.head h1{margin:0;font-size:1.2rem;font-weight:800;color:var(--pg-accent,#f5d76e)}
.back{color:var(--pg-desc,#c8c8c8);text-decoration:none;padding:6px 14px;border:1px solid var(--pg-card-border);border-radius:20px;font-size:0.85rem}
.back:hover{background:var(--pg-accent-bg);color:var(--pg-accent)}
.presets{display:flex;gap:6px;flex-wrap:wrap;margin-left:auto}
.presets button{padding:6px 14px;border-radius:8px;background:transparent;border:1px solid var(--pg-card-border);color:var(--pg-desc);font-size:0.82rem;font-weight:700;cursor:pointer;font-family:inherit}
.presets button:hover{color:var(--pg-accent);border-color:var(--pg-accent)}
.presets button.active{background:var(--pg-accent-bg);border-color:var(--pg-accent);color:var(--pg-accent)}
.period{padding:6px 8px;border-radius:8px;border:1px solid var(--pg-input-border);background:var(--pg-input-bg);color:var(--pg-text);font-family:inherit;font-size:0.8rem}
.range-info{display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:20px;background:var(--pg-inner-bg);border:1px solid var(--pg-card-border-soft);font-size:0.78rem;color:var(--pg-desc)}
.range-info b{color:var(--pg-accent)}
.range-info .sep{opacity:0.5}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{padding:14px 16px;background:var(--pg-card-bg);border:1px solid var(--pg-card-border);border-radius:12px}
.kpi .v{font-size:1.5rem;font-weight:800;line-height:1.05;color:var(--pg-accent)}
.kpi .l{font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;color:var(--pg-meta);font-weight:700;margin-top:4px}
.kpi.danger .v{color:var(--pg-err,#ec7063)}
.kpi.warn .v{color:var(--pg-warn,#f7dc6f)}
.kpi.ok .v{color:var(--pg-ok,#58d68d)}
.kpi.info .v{color:var(--pg-info,#6dc2f0)}
.list{display:flex;flex-direction:column;gap:8px}
.card{padding:14px 18px;background:var(--pg-card-bg);border:1px solid var(--pg-card-border);border-radius:12px;display:grid;grid-template-columns:240px 1fr 120px;gap:18px;align-items:center;transition:border-color .15s,transform .15s}
.card:hover{border-color:var(--pg-accent);transform:translateX(2px)}
.card.overload{border-left:4px solid var(--pg-err,#ec7063)}
.card.high{border-left:4px solid var(--pg-warn,#f7dc6f)}
.card.low{border-left:4px solid var(--pg-info,#6dc2f0)}
.card.ok{border-left:4px solid var(--pg-ok,#58d68d)}
.card.empty{border-left:4px solid var(--pg-meta);opacity:0.7}
.who{display:flex;align-items:center;gap:10px;min-width:0}
.avatar{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:0.78rem;text-shadow:0 1px 3px rgba(0,0,0,0.35);flex-shrink:0}
.who-body{min-width:0}
.who-name{font-weight:700;color:var(--pg-text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.who-dept{font-size:0.7rem;color:var(--pg-meta);margin-top:2px}
.bar-area{display:flex;flex-direction:column;gap:6px}
.bar-track{position:relative;height:26px;background:rgba(128,128,128,0.10);border-radius:8px;overflow:hidden}
.bar-load{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#6dc2f0,#2874a6);transition:width .3s}
.bar-load.warn{background:linear-gradient(90deg,#f7dc6f,#d4ac0d)}
.bar-load.err{background:linear-gradient(90deg,#ec7063,#b03a2e)}
.bar-load.low{background:linear-gradient(90deg,#a5c8e8,#5dade2)}
.bar-cap{position:absolute;top:0;bottom:0;width:2px;background:var(--pg-ok,#58d68d);box-shadow:0 0 6px var(--pg-ok,#58d68d)}
.bar-label{position:absolute;right:10px;top:0;bottom:0;display:flex;align-items:center;font-size:0.72rem;font-weight:700;color:var(--pg-text);text-shadow:0 1px 2px rgba(0,0,0,0.5);pointer-events:none}
.bar-legend{display:flex;gap:14px;font-size:0.68rem;color:var(--pg-meta);flex-wrap:wrap}
.meta{text-align:right}
.meta .pct{font-size:1.3rem;font-weight:800;line-height:1}
.meta .sub{font-size:0.7rem;color:var(--pg-meta);margin-top:4px}
.meta.overload .pct{color:var(--pg-err,#ec7063)}
.meta.high .pct{color:var(--pg-warn,#f7dc6f)}
.meta.low .pct{color:var(--pg-info,#6dc2f0)}
.meta.ok .pct{color:var(--pg-ok,#58d68d)}
.meta.empty .pct{color:var(--pg-meta)}
.empty,.loading{text-align:center;padding:60px;color:var(--pg-meta);font-style:italic}
.footer{padding:16px 18px;background:var(--pg-card-bg);border:1px solid var(--pg-card-border);border-radius:12px;font-size:0.8rem;line-height:1.6;color:var(--pg-desc)}
.footer h3{margin:0 0 10px 0;font-size:0.85rem;font-weight:800;color:var(--pg-accent);text-transform:uppercase;letter-spacing:0.6px;border-bottom:1px dashed var(--pg-card-border-soft);padding-bottom:6px}
.footer code{font-family:monospace;font-size:0.78rem;background:rgba(245,215,110,0.08);padding:1px 5px;border-radius:4px;color:var(--pg-accent)}
.footer ul{margin:6px 0;padding-left:20px}
.footer li{margin:3px 0}
.footer b{color:var(--pg-text)}
@media (max-width:900px){.card{grid-template-columns:1fr;gap:10px}.meta{text-align:left}}
@media (max-width:700px){.head{padding:12px 14px}.head h1{font-size:1rem}}
</style>
</head>
<body>
<div class="w">

<div class="head">
<a class="back" href="/">← К трекеру</a>
<h1>⚖ Загрузка сотрудников</h1>
<div class="presets">
<button data-preset="week">Неделя</button>
<button data-preset="biweek" class="active">2 недели</button>
<button data-preset="month">Месяц</button>
<button data-preset="quarter">Квартал</button>
</div>
<input type="date" id="cFrom" class="period">
<input type="date" id="cTo" class="period">
<button class="period" id="cApply">✓</button>
<div class="range-info" id="rangeInfo"></div>
</div>

<div class="kpis" id="kpis"><div class="loading">Загрузка…</div></div>

<div class="list" id="list"><div class="loading">Загрузка…</div></div>

<div class="footer">
<h3>📖 Как считается загрузка</h3>
<b>Ёмкость сотрудника</b>
<ul>
<li><code>рабочие дни Пн–Пт в периоде</code> — минус праздники</li>
<li>минус отсутствия: 🏖 отпуск, 🤒 больничный, ✈️ командировка (🏠 удалёнка НЕ вычитается)</li>
<li>если <code>hired_date</code> &gt; начала периода — отсчёт с даты выхода</li>
<li>если <code>fired_date</code> &lt; конца периода — отсчёт до даты увольнения</li>
<li><code>ёмкость = рабочие_дни_сотрудника × 8ч</code></li>
</ul>
<b>Оценка задачи</b> (сколько часов займёт)
<ul>
<li><code>4ч × рабочие_дни между start_date и deadline</code>, ограничение 4–40ч</li>
<li>если даты не заданы — 4ч по умолчанию</li>
</ul>
<b>Остаток по задаче для сотрудника</b>
<ul>
<li><code>max(0, оценка_задачи − уже_отработано_этим_сотрудником)</code></li>
<li>если сотрудник отработал больше оценки — задача считается закрытой, остаток 0</li>
</ul>
<b>Нагрузка и загрузка</b>
<ul>
<li><code>нагрузка = сумма остатков</code> по всем задачам, где сотрудник в исполнителях и задача <code>active</code> или <code>paused</code></li>
<li><code>загрузка% = 100 × нагрузка / ёмкость</code></li>
<li>0–50% — 💤 недогружен, 50–100% — ✅ норма, 100–120% — ⚠ на пределе, &gt;120% — 🔥 перегруз</li>
</ul>
<b>Ограничения модели</b>
<ul>
<li>Оценка задачи грубая: 4ч/рабочий_день. Точные оценки по задачам в трекере не задаются.</li>
<li>Пересечение задач по времени не моделируется — считается, что вся нагрузка ложится на период.</li>
<li>Приоритеты и срочность задач не влияют на распределение.</li>
</ul>
</div>

</div>

<script>
(function(){
'use strict';

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function initials(n){var p=String(n||'').trim().split(/\s+/);if(!p.length)return'?';if(p.length===1)return p[0].slice(0,2).toUpperCase();return (p[0][0]+(p[1][0]||'')).toUpperCase();}
function fmtH(h){h=Number(h)||0;if(h===Math.floor(h))return h+' ч';return h.toFixed(2).replace(/0+$/,'').replace(/\.$/,'')+' ч';}
function fmtI(n){return (Number(n)||0).toLocaleString('ru-RU');}
function fmtPct(n){return (Number(n)||0)+'%';}
function cls(pct, capacity){pct=Number(pct)||0;if(capacity<=0)return'empty';if(pct>120)return'overload';if(pct>100)return'high';if(pct<50)return'low';return'ok';}

function _maskEnabled(){try{return localStorage.getItem('reestr_tracker_mask')==='1';}catch(e){return false;}}
function _maskName(s){
    if(!_maskEnabled())return s;
    return String(s||'').split(/\s+/).map(function(w){if(w.length<=1)return w;return w[0]+new Array(w.length).join('*');}).join(' ');
}
function _escName(s){return esc(_maskName(s));}

var state = {preset:'biweek', from:'', to:''};

function renderKpis(s){
    var el = document.getElementById('kpis');
    var cards = [
        {v:fmtI(s.employees_total),l:'Сотрудников',cls:''},
        {v:fmtI(s.overloaded),l:'Перегружены',cls:'danger'},
        {v:fmtI(s.at_capacity),l:'На пределе',cls:'warn'},
        {v:fmtI(s.normal),l:'В норме',cls:'ok'},
        {v:fmtI(s.underused),l:'Недогружены',cls:'info'},
        {v:fmtI(s.no_load),l:'Без задач',cls:''},
        {v:fmtH(s.hours_total),l:'Часов нагрузки',cls:''},
        {v:fmtH(s.capacity_total),l:'Ёмкость команды',cls:''},
        {v:fmtPct(s.avg_pct),l:'Средняя загрузка',cls:s.avg_pct>100?'warn':'ok'}
    ];
    el.innerHTML = cards.map(function(c){return '<div class="kpi '+c.cls+'"><div class="v">'+c.v+'</div><div class="l">'+c.l+'</div></div>';}).join('');
}

function renderRow(e){
    var c = cls(e.pct, e.capacity);
    var bg = esc(e.color || '#888');
    var width = e.capacity > 0 ? Math.min(e.pct, 200) / 2 : 0;
    var barCls = c === 'overload' ? 'err' : (c === 'high' ? 'warn' : (c === 'low' ? 'low' : ''));
    var badge = '';
    if (e.pct > 120) badge = ' 🔥';
    else if (e.pct < 50 && e.capacity > 0) badge = ' 💤';
    var capMark = e.capacity > 0 && e.pct <= 100 ? '<div class="bar-cap" style="left:'+Math.min(e.pct,100)+'%;"></div>' : (e.capacity > 0 ? '<div class="bar-cap" style="left:50%;"></div>' : '');
    var label = e.capacity > 0 ? (fmtH(e.hours_open) + ' из ' + fmtH(e.capacity)) : fmtH(e.hours_open);
    return '<div class="card '+c+'">'
        + '<div class="who">'
        +   '<div class="avatar" style="background:'+bg+';">'+esc(initials(e.name))+'</div>'
        +   '<div class="who-body">'
        +     '<div class="who-name">'+_escName(e.name)+badge+'</div>'
        +     (e.department ? '<div class="who-dept">🏢 '+esc(e.department)+'</div>' : '')
        +   '</div>'
        + '</div>'
        + '<div class="bar-area">'
        +   '<div class="bar-track">'
        +     '<div class="bar-load '+barCls+'" style="width:'+width+'%;"></div>'
        +     capMark
        +     '<div class="bar-label">'+label+'</div>'
        +   '</div>'
        +   '<div class="bar-legend">'
        +     '<span>Задач: <b>'+e.tasks_open+'</b></span>'
        +     '<span>Активных: <b>'+e.tasks_active+'</b></span>'
        +     '<span>Просрочено: <b style="color:'+(e.tasks_overdue > 0 ? 'var(--pg-err)' : 'inherit')+'">'+e.tasks_overdue+'</b></span>'
        +     (e.absence_days > 0 ? '<span>Отсутствий: <b>'+e.absence_days+' дн.</b></span>' : '')
        +   '</div>'
        + '</div>'
        + '<div class="meta '+c+'">'
        +   '<div class="pct">'+(e.capacity > 0 ? fmtPct(e.pct) : '—')+'</div>'
        +   '<div class="sub">'+fmtH(e.hours_open)+' / '+fmtH(e.capacity)+'</div>'
        + '</div>'
        + '</div>';
}

function load(){
    var el = document.getElementById('list');
    el.innerHTML = '<div class="loading">Загрузка…</div>';
    var q = '?preset=' + encodeURIComponent(state.preset);
    if (state.preset === 'custom') q += '&from=' + encodeURIComponent(state.from) + '&to=' + encodeURIComponent(state.to);
    fetch('/api/plugins/capacity/data' + q, {credentials: 'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (!d || !d.success) { el.innerHTML = '<div class="empty">Ошибка загрузки</div>'; return; }
            renderKpis(d.summary || {});
            document.getElementById('rangeInfo').innerHTML =
                '<span>📅</span> <b>' + d.from + '</b> <span class="sep">→</span> <b>' + d.to + '</b>' +
                '<span class="sep">·</span> ' + d.workdays + ' раб. дн.';
            if (!d.employees || !d.employees.length) { el.innerHTML = '<div class="empty">Нет сотрудников</div>'; return; }
            el.innerHTML = d.employees.map(renderRow).join('');
        })
        .catch(function(){ el.innerHTML = '<div class="empty">Ошибка соединения</div>'; });
}

document.querySelectorAll('.presets button').forEach(function(b){
    b.addEventListener('click', function(){
        document.querySelectorAll('.presets button').forEach(function(x){ x.classList.remove('active'); });
        this.classList.add('active');
        state.preset = this.getAttribute('data-preset');
        state.from = ''; state.to = '';
        load();
    });
});
document.getElementById('cApply').addEventListener('click', function(){
    var f = document.getElementById('cFrom').value;
    var t = document.getElementById('cTo').value;
    if (!f || !t) return;
    state.preset = 'custom'; state.from = f; state.to = t;
    document.querySelectorAll('.presets button').forEach(function(x){ x.classList.remove('active'); });
    load();
});

load();
})();
</script>
</body>
</html>'''


def _parse_iso(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None


def _period_from_args():
    preset = (request.args.get('preset') or 'biweek').strip().lower()
    today = date.today()
    if preset == 'week':
        return today, today + timedelta(days=6), 'week'
    if preset == 'biweek':
        return today, today + timedelta(days=13), 'biweek'
    if preset == 'month':
        return today, today + timedelta(days=29), 'month'
    if preset == 'quarter':
        return today, today + timedelta(days=89), 'quarter'
    d1 = _parse_iso(request.args.get('from') or '')
    d2 = _parse_iso(request.args.get('to') or '')
    if d1 and d2 and d1 <= d2:
        if (d2 - d1).days > 365:
            d2 = d1 + timedelta(days=365)
        return d1, d2, 'custom'
    return today, today + timedelta(days=13), 'biweek'


def _workdays_between(d1, d2):
    n = 0
    cur = d1
    while cur <= d2:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


def _holidays_set(data):
    h = data.get('holidays') or {}
    if isinstance(h, dict):
        return set(h.keys())
    return set()


def _employee_capacity_days(e, d1_iso, d2_iso, holidays):
    """Рабочие дни сотрудника в интервале с учётом праздников, отпусков, найма/увольнения."""
    hired = (e.get('hired_date') or '').strip()
    fired = (e.get('fired_date') or '').strip() if e.get('fired') else ''
    start_iso = d1_iso
    end_iso = d2_iso
    if hired and hired > start_iso:
        start_iso = hired
    if fired and fired < end_iso:
        end_iso = fired
    if start_iso > end_iso:
        return 0
    # Отпуска/больничные/командировки
    absence_dates = set()
    for v in (e.get('vacations') or []):
        vt = v.get('type') or 'vacation'
        if vt == 'remote':
            continue
        vf = v.get('from') or ''
        vto = v.get('to') or ''
        if not vf or not vto:
            continue
        s = max(vf, start_iso)
        en = min(vto, end_iso)
        if s > en:
            continue
        try:
            cur = datetime.strptime(s, '%Y-%m-%d').date()
            end = datetime.strptime(en, '%Y-%m-%d').date()
            while cur <= end:
                iso = cur.strftime('%Y-%m-%d')
                if cur.weekday() < 5 and iso not in holidays:
                    absence_dates.add(iso)
                cur += timedelta(days=1)
        except Exception:
            pass
    try:
        start = datetime.strptime(start_iso, '%Y-%m-%d').date()
        end = datetime.strptime(end_iso, '%Y-%m-%d').date()
    except Exception:
        return 0
    n = 0
    cur = start
    while cur <= end:
        iso = cur.strftime('%Y-%m-%d')
        if cur.weekday() < 5 and iso not in holidays and iso not in absence_dates:
            n += 1
        cur += timedelta(days=1)
    return n


def _task_estimate_hours(t, holidays):
    """Оценка задачи: 4ч × раб.дни между start_date и deadline, ограничение 4–40ч."""
    sd = (t.get('start_date') or '').strip()
    dl = (t.get('deadline') or '').strip()
    if sd and dl:
        d1 = _parse_iso(sd)
        d2 = _parse_iso(dl)
        if d1 and d2 and d1 <= d2:
            days = 0
            cur = d1
            while cur <= d2:
                iso = cur.strftime('%Y-%m-%d')
                if cur.weekday() < 5 and iso not in holidays:
                    days += 1
                cur += timedelta(days=1)
            if days == 0:
                days = 1
            return max(4.0, min(days * 4.0, 40.0))
    return 4.0


# ============================================================
# Регистрация
# ============================================================
def register(app, db, hooks):
    print('[capacity] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/capacity.js', methods=['GET'])
    def _cp_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/plugins/capacity/', methods=['GET'])
    def _cp_page():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return redirect('/login')
            if not (user_has(db, u, 'tab.summary') or user_has(db, u, 'tab.stats')):
                return redirect('/')
        except Exception:
            return redirect('/login')
        return Response(_page_html(), mimetype='text/html')

    @app.route('/api/plugins/capacity/data', methods=['GET'])
    def _cp_data():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return jsonify({'success': False, 'error': 'auth'}), 401
            if not (user_has(db, u, 'tab.summary') or user_has(db, u, 'tab.stats')):
                return jsonify({'success': False, 'error': 'forbidden'}), 403
        except Exception:
            return jsonify({'success': False, 'error': 'auth'}), 401

        d1, d2, preset = _period_from_args()
        d1_iso = d1.strftime('%Y-%m-%d')
        d2_iso = d2.strftime('%Y-%m-%d')
        today = date.today()
        today_iso = today.strftime('%Y-%m-%d')

        data = db.load_all()
        holidays = _holidays_set(data)
        wd = _workdays_between(d1, d2)

        # Часы по (сотрудник, задача) — только done не важно, берём всё
        emp_task_hours = {}
        for l in data.get('log', []):
            eid = l.get('employee_id')
            tid = l.get('task_id')
            if not eid or not tid:
                continue
            try:
                h = float(l.get('hours') or 0)
            except Exception:
                h = 0
            emp_task_hours[(eid, tid)] = emp_task_hours.get((eid, tid), 0.0) + h

        # Задачи заранее посчитаем оценку один раз
        task_est = {}
        for t in data.get('tasks', []):
            if t.get('status') not in ('active', 'paused'):
                continue
            task_est[t['id']] = _task_estimate_hours(t, holidays)

        employees_out = []
        for e in data.get('employees', []):
            if e.get('fired'):
                continue
            eid = e['id']
            cap_days = _employee_capacity_days(e, d1_iso, d2_iso, holidays)
            capacity = cap_days * 8
            absence_days = 0
            for v in (e.get('vacations') or []):
                if (v.get('type') or 'vacation') == 'remote':
                    continue
                vf = v.get('from') or ''
                vto = v.get('to') or ''
                if not vf or not vto:
                    continue
                s = max(vf, d1_iso)
                en = min(vto, d2_iso)
                if s > en:
                    continue
                try:
                    cur = datetime.strptime(s, '%Y-%m-%d').date()
                    end = datetime.strptime(en, '%Y-%m-%d').date()
                    while cur <= end:
                        if cur.weekday() < 5:
                            iso = cur.strftime('%Y-%m-%d')
                            if iso not in holidays:
                                absence_days += 1
                        cur += timedelta(days=1)
                except Exception:
                    pass

            tasks_open = 0
            tasks_active = 0
            tasks_overdue = 0
            hours_open = 0.0
            for t in data.get('tasks', []):
                if t.get('status') not in ('active', 'paused'):
                    continue
                if eid not in (t.get('assignees') or []):
                    continue
                sd = (t.get('start_date') or '').strip()
                dl = (t.get('deadline') or '').strip()
                # задача должна пересекаться с [d1, d2]
                if sd and sd > d2_iso:
                    continue
                if dl and dl < d1_iso and t.get('status') != 'active':
                    continue
                est = task_est.get(t['id'], 4.0)
                done_h = emp_task_hours.get((eid, t['id']), 0.0)
                remain = max(0.0, est - done_h)
                hours_open += remain
                tasks_open += 1
                if t.get('status') == 'active':
                    tasks_active += 1
                if dl and dl < today_iso:
                    tasks_overdue += 1
            hours_open = round(hours_open, 1)
            pct = round(100 * hours_open / capacity) if capacity > 0 else 0
            employees_out.append({
                'id': eid,
                'name': e.get('name', ''),
                'color': e.get('color', '#888'),
                'department': e.get('department', ''),
                'tasks_open': tasks_open,
                'tasks_active': tasks_active,
                'tasks_overdue': tasks_overdue,
                'hours_open': hours_open,
                'capacity': capacity,
                'absence_days': absence_days,
                'pct': pct,
            })

        employees_out.sort(key=lambda x: (-x['pct'], -x['hours_open']))

        overloaded = sum(1 for e in employees_out if e['capacity'] > 0 and e['pct'] > 120)
        at_capacity = sum(1 for e in employees_out if e['capacity'] > 0 and 100 < e['pct'] <= 120)
        normal = sum(1 for e in employees_out if e['capacity'] > 0 and 50 <= e['pct'] <= 100)
        underused = sum(1 for e in employees_out if e['capacity'] > 0 and 0 < e['pct'] < 50)
        no_load = sum(1 for e in employees_out if e['capacity'] == 0 or e['hours_open'] == 0)
        hours_total = round(sum(e['hours_open'] for e in employees_out), 1)
        capacity_total = sum(e['capacity'] for e in employees_out)
        active_pcts = [e['pct'] for e in employees_out if e['capacity'] > 0]
        avg_pct = round(sum(active_pcts) / len(active_pcts)) if active_pcts else 0

        return jsonify({
            'success': True,
            'preset': preset,
            'from': d1_iso,
            'to': d2_iso,
            'workdays': wd,
            'summary': {
                'employees_total': len(employees_out),
                'overloaded': overloaded,
                'at_capacity': at_capacity,
                'normal': normal,
                'underused': underused,
                'no_load': no_load,
                'hours_total': hours_total,
                'capacity_total': capacity_total,
                'avg_pct': avg_pct,
            },
            'employees': employees_out,
        })

    def on_startup(**ctx):
        print('[capacity] готов — v3.0')

    hooks.on('on_startup', on_startup)

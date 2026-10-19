"""plugins/my_week.py — личный дашборд «Моя неделя» с выбором периода."""

__version__ = '3.0'
__description__ = 'Моя неделя: часы, задачи, тренды, графики, топ задач. Период: неделя / месяц / квартал / год'

from datetime import date, datetime, timedelta
from flask import jsonify, Response, redirect, request


# ============================================================
# JS — кнопка в шапку трекера
# ============================================================
_JS = r'''
(function(){
'use strict';
function inject(){
    if (!(window.REESTR_PERMS && window.REESTR_PERMS['tab.calendar'])) return;
    if (document.getElementById('myWeekBtn')) return;
    var header = document.querySelector('.tracker-header');
    if (!header) return;
    var b = document.createElement('a');
    b.id = 'myWeekBtn';
    b.className = 'theme-toggle-btn';
    b.href = '/plugins/my_week/';
    b.title = 'Моя неделя';
    b.innerHTML = '📅';
    var anchor = header.querySelector('.user-menu');
    if (anchor) header.insertBefore(b, anchor);
    else header.appendChild(b);
}
setTimeout(inject, 500);
setTimeout(inject, 1500);
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
<title>Моя неделя</title>
<script src="/static/plugin_theme.js"></script>
<style>
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    margin: 0; padding: 16px; font-size: 14px;
    background: var(--pg-bg, #0f0f0f);
    background-attachment: fixed;
    color: var(--pg-text, #e8e8e8);
    min-height: 100vh;
}
.w { max-width: 1600px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }

.head {
    display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
    padding: 14px 18px;
    background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 14px;
}
.head h1 { margin: 0; font-size: 1.2rem; font-weight: 800; color: var(--pg-accent, #f5d76e); }
.back {
    color: var(--pg-desc, #c8c8c8); text-decoration: none;
    padding: 6px 14px; border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 20px; font-size: 0.85rem;
}
.back:hover { background: var(--pg-accent-bg); color: var(--pg-accent); border-color: var(--pg-accent); }
.presets { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
.presets button {
    padding: 6px 14px; border-radius: 8px; background: transparent;
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    color: var(--pg-desc, #c8c8c8);
    font-size: 0.82rem; font-weight: 700; cursor: pointer; font-family: inherit;
}
.presets button:hover { color: var(--pg-accent); border-color: var(--pg-accent); }
.presets button.active { background: var(--pg-accent-bg); border-color: var(--pg-accent); color: var(--pg-accent); }
.period {
    padding: 6px 8px; border-radius: 8px;
    border: 1px solid var(--pg-input-border, rgba(245,215,110,0.26));
    background: var(--pg-input-bg, #232323);
    color: var(--pg-text, #e8e8e8);
    font-family: inherit; font-size: 0.8rem;
}
.period-btn {
    padding: 6px 12px; border-radius: 8px;
    border: 1px solid var(--pg-input-border);
    background: var(--pg-input-bg);
    color: var(--pg-text); font-family: inherit; font-size: 0.85rem; cursor: pointer;
}
.period-btn:hover { color: var(--pg-accent); border-color: var(--pg-accent); }

.who { display: flex; align-items: center; gap: 10px; margin-left: 8px; }
.who .avatar {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 800; font-size: 0.8rem;
    text-shadow: 0 1px 3px rgba(0,0,0,0.35);
}
.who .name { font-weight: 700; color: var(--pg-text); font-size: 0.9rem; }
.who .period { font-size: 0.72rem; color: var(--pg-meta); }

/* KPI */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.kpi {
    padding: 14px 16px; background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 12px; position: relative; overflow: hidden;
}
.kpi::after {
    content: ''; position: absolute; right: -20px; top: -20px;
    width: 80px; height: 80px; border-radius: 50%;
    background: radial-gradient(circle, rgba(245,215,110,0.08), transparent 70%);
    pointer-events: none;
}
.kpi .v { font-size: 1.5rem; font-weight: 800; line-height: 1.05; color: var(--pg-accent, #f5d76e); }
.kpi .l { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.8px; color: var(--pg-meta, #a0a0a0); font-weight: 700; margin-top: 4px; }
.kpi .sub { font-size: 0.68rem; color: var(--pg-meta, #a0a0a0); margin-top: 3px; }
.kpi.danger .v { color: var(--pg-err, #ec7063); }
.kpi.warn .v { color: var(--pg-warn, #f7dc6f); }
.kpi.ok .v { color: var(--pg-ok, #58d68d); }
.kpi.info .v { color: var(--pg-info, #6dc2f0); }

/* Layout */
.main-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 14px; align-items: start; }
@media (max-width: 1100px) { .main-grid { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 14px; }

.card {
    padding: 16px 18px;
    background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 14px;
}
.card-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.78rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.8px;
    color: var(--pg-accent, #f5d76e);
    margin-bottom: 12px; padding-bottom: 8px;
    border-bottom: 1px dashed var(--pg-card-border-soft, rgba(245,215,110,0.14));
}
.card-title .cnt {
    margin-left: auto;
    font-size: 0.68rem; padding: 1px 8px; border-radius: 8px;
    background: var(--pg-accent-bg, rgba(245,215,110,0.14));
    color: var(--pg-accent, #f5d76e); font-weight: 700;
}
.card-title.danger { color: var(--pg-err, #ec7063); }
.card-title.warn { color: var(--pg-warn, #f7dc6f); }
.card-title.ok { color: var(--pg-ok, #58d68d); }
.card-title.info { color: var(--pg-info, #6dc2f0); }

.chart-wrap svg { display: block; width: 100%; height: auto; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 10px; font-size: 0.72rem; color: var(--pg-meta, #a0a0a0); }
.chart-legend .it { display: flex; align-items: center; gap: 5px; }
.chart-legend .sw { width: 12px; height: 12px; border-radius: 3px; }

.list { display: flex; flex-direction: column; gap: 5px; }
.row-item {
    display: grid; grid-template-columns: 26px 1fr auto;
    gap: 10px; align-items: center;
    padding: 8px 12px; background: var(--pg-inner-bg, #232323);
    border-radius: 8px; border-left: 3px solid var(--pg-meta, #a0a0a0);
    font-size: 0.83rem;
}
.row-item.danger { border-left-color: var(--pg-err, #ec7063); }
.row-item.warn { border-left-color: var(--pg-warn, #f7dc6f); }
.row-item.ok { border-left-color: var(--pg-ok, #58d68d); }
.row-item.info { border-left-color: var(--pg-info, #6dc2f0); }
.row-item .ico { font-size: 1rem; text-align: center; }
.row-item .body { min-width: 0; }
.row-item .nm { color: var(--pg-text, #e8e8e8); word-break: break-word; }
.row-item .meta { font-size: 0.7rem; color: var(--pg-meta, #a0a0a0); margin-top: 2px; }
.row-item .pill {
    padding: 2px 9px; border-radius: 8px;
    font-size: 0.7rem; font-weight: 800;
    background: var(--pg-accent-bg, rgba(245,215,110,0.14));
    color: var(--pg-accent, #f5d76e); white-space: nowrap;
}
.row-item .pill.danger { background: rgba(231,76,60,0.18); color: var(--pg-err, #ec7063); }
.row-item .pill.ok { background: rgba(46,204,113,0.18); color: var(--pg-ok, #58d68d); }
.row-item .pill.warn { background: rgba(241,196,15,0.20); color: #b7950b; }

.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; margin-top: 10px; }
.status-cell {
    padding: 10px 8px; background: var(--pg-inner-bg, #232323);
    border-radius: 10px; text-align: center;
    border-top: 3px solid var(--sc, var(--pg-accent));
}
.status-cell .v { font-size: 1.25rem; font-weight: 800; color: var(--sc, var(--pg-accent)); }
.status-cell .l { font-size: 0.6rem; text-transform: uppercase; color: var(--pg-meta, #a0a0a0); letter-spacing: 0.5px; margin-top: 3px; font-weight: 700; }

.empty, .loading { text-align: center; padding: 24px; color: var(--pg-meta, #a0a0a0); font-style: italic; font-size: 0.82rem; }

@media (max-width: 700px) {
    .head { padding: 12px 14px; }
    .head h1 { font-size: 1.05rem; }
    .who { margin-left: 0; }
}
</style>
</head>
<body>
<div class="w">

    <div class="head">
        <a class="back" href="/">← К трекеру</a>
        <h1>📅 Моя неделя</h1>
        <div class="presets">
            <button data-preset="week" class="active">Текущая неделя</button>
            <button data-preset="prev_week">Прошлая неделя</button>
            <button data-preset="month">Месяц</button>
            <button data-preset="quarter">Квартал</button>
            <button data-preset="year">Год</button>
        </div>
        <input type="date" id="pFrom" class="period">
        <input type="date" id="pTo" class="period">
        <button class="period-btn" id="pApply">✓</button>
        <div class="who" id="who"></div>
    </div>

    <div class="kpis" id="kpis"><div class="loading">Загрузка…</div></div>

    <div class="main-grid">

        <div class="col">
            <div class="card">
                <div class="card-title"><span>📈</span><span>Активность за период</span></div>
                <div class="chart-wrap" id="chartActivity"></div>
                <div class="chart-legend">
                    <div class="it"><span class="sw" style="background:linear-gradient(180deg,#6dc2f0,#2874a6);"></span>Часы</div>
                    <div class="it"><span class="sw" style="background:#58d68d;border-radius:50%;"></span>Закрытые задачи</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title"><span>🗓</span><span>Загрузка по дням недели</span></div>
                <div class="chart-wrap" id="chartWeekdays"></div>
                <div class="chart-legend">
                    <div class="it" style="color:var(--pg-meta);">Средние часы по каждому дню недели за период</div>
                </div>
            </div>

            <div class="card">
                <div class="card-title"><span>🍩</span><span>Мои задачи по статусам</span></div>
                <div class="chart-wrap" id="chartStatus"></div>
                <div class="status-grid" id="statusGrid"></div>
            </div>
        </div>

        <div class="col">
            <div class="card">
                <div class="card-title danger"><span>⚠</span><span>Просрочено (сейчас)</span><span class="cnt" id="cOverdue">0</span></div>
                <div class="list" id="lOverdue"></div>
            </div>

            <div class="card">
                <div class="card-title warn"><span>🩶</span><span>Назначено, не начато</span><span class="cnt" id="cPending">0</span></div>
                <div class="list" id="lPending"></div>
            </div>

            <div class="card">
                <div class="card-title ok"><span>✅</span><span>Закрыто за период</span><span class="cnt" id="cDone">0</span></div>
                <div class="list" id="lDone"></div>
            </div>

            <div class="card">
                <div class="card-title info"><span>🏆</span><span>Топ задач по времени</span><span class="cnt" id="cTop">0</span></div>
                <div class="list" id="lTop"></div>
            </div>
        </div>
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
function fmtD(iso){if(!iso)return'';var p=iso.split('-');return p[2]+'.'+p[1];}

var state = { preset:'week', from:'', to:'' };

function renderKpis(k){
    var el = document.getElementById('kpis');
    var dSub = '';
    if (k.hours_prev > 0 || k.hours_period > 0) {
        var delta = k.hours_period - k.hours_prev;
        if (k.hours_prev > 0) {
            var pct = Math.round(100 * delta / k.hours_prev);
            dSub = (delta >= 0 ? '+' : '') + pct + '% к прошлому';
        } else if (k.hours_period > 0) {
            dSub = 'было 0';
        }
    }
    var cards = [
        { v: fmtH(k.hours_period), l: 'Часов за период', sub: dSub, cls: '' },
        { v: fmtI(k.done_period), l: 'Закрыто задач', cls: 'ok' },
        { v: fmtH(k.avg_per_day), l: 'Среднее в день', cls: 'info' },
        { v: fmtPct(k.capacity_pct), l: 'От нормы 8ч', cls: k.capacity_pct >= 90 ? 'ok' : (k.capacity_pct >= 60 ? 'warn' : 'danger') },
        { v: fmtI(k.active_tasks), l: 'Активных задач', cls: '' },
        { v: fmtI(k.overdue), l: 'Просрочено сейчас', cls: k.overdue > 0 ? 'danger' : '' },
        { v: fmtI(k.pending), l: 'Назначено без отметок', cls: k.pending > 0 ? 'warn' : '' },
        { v: fmtI(k.workdays), l: 'Рабочих дней в периоде', cls: '' }
    ];
    el.innerHTML = cards.map(function(c){
        return '<div class="kpi ' + c.cls + '"><div class="v">' + c.v + '</div><div class="l">' + c.l + '</div>' + (c.sub ? '<div class="sub">' + c.sub + '</div>' : '') + '</div>';
    }).join('');
}

function renderWho(d){
    var el = document.getElementById('who');
    el.innerHTML = '<div class="avatar" style="background:' + esc(d.employee.color || '#888') + ';">'
        + esc(initials(d.employee.name)) + '</div>'
        + '<div><div class="name">' + esc(d.employee.name) + '</div>'
        + '<div class="period">' + d.from + ' → ' + d.to + '</div></div>';
}

/* Активность за период. Если дней > 60 — агрегируем по неделям */
function renderActivity(series){
    var el = document.getElementById('chartActivity');
    if (!series || !series.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    var W = 720, H = 200, PAD = { l: 36, r: 12, t: 12, b: 28 };
    var innerW = W - PAD.l - PAD.r, innerH = H - PAD.t - PAD.b;
    var n = series.length;
    var maxH = Math.max.apply(null, series.map(function(x){return x.hours;}).concat([1]));
    var maxD = Math.max.apply(null, series.map(function(x){return x.done;}).concat([1]));
    var bw = innerW / n;
    var out = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">';
    for (var g = 0; g <= 4; g++) {
        var y = PAD.t + (innerH * g / 4);
        var label = Math.round(maxH * (4 - g) / 4);
        out += '<line x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y + '" y2="' + y + '" stroke="rgba(128,128,128,0.15)" stroke-width="1"/>';
        out += '<text x="' + (PAD.l - 6) + '" y="' + (y + 4) + '" font-size="10" fill="var(--pg-meta)" text-anchor="end">' + label + '</text>';
    }
    var every = Math.max(1, Math.floor(n / 12));
    series.forEach(function(d, i) {
        var bh = (d.hours / maxH) * innerH;
        var x = PAD.l + i * bw + bw * 0.15;
        var w = bw * 0.7;
        var y = PAD.t + innerH - bh;
        out += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + bh + '" fill="url(#actGrad)" rx="2"><title>' + d.date + ': ' + fmtH(d.hours) + (d.done ? ' · закрыто ' + d.done : '') + '</title></rect>';
        if (d.done > 0) {
            var dy = PAD.t + innerH - (d.done / maxD) * (innerH * 0.4);
            var cx = PAD.l + i * bw + bw * 0.5;
            out += '<circle cx="' + cx + '" cy="' + dy + '" r="2.5" fill="#58d68d"><title>закрыто ' + d.done + '</title></circle>';
        }
        if (i % every === 0) {
            out += '<text x="' + (PAD.l + i * bw + bw * 0.5) + '" y="' + (H - 8) + '" font-size="9" fill="var(--pg-meta)" text-anchor="middle">' + fmtD(d.date) + '</text>';
        }
    });
    out += '<defs><linearGradient id="actGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#6dc2f0"/><stop offset="100%" stop-color="#2874a6"/></linearGradient></defs>';
    out += '</svg>';
    el.innerHTML = out;
}

/* График по дням недели — средние часы за пн, вт, ср, чт, пт, сб, вс */
function renderWeekdays(data){
    var el = document.getElementById('chartWeekdays');
    var names = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
    if (!data || !data.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    var maxV = Math.max.apply(null, data.map(function(x){return x.avg;}).concat([1]));
    var W = 720, H = 180, PAD = { l: 40, r: 20, t: 20, b: 30 };
    var innerW = W - PAD.l - PAD.r, innerH = H - PAD.t - PAD.b;
    var n = 7;
    var bw = innerW / n * 0.6;
    var gap = innerW / n;
    var out = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">';
    for (var g = 0; g <= 3; g++) {
        var y = PAD.t + (innerH * g / 3);
        var label = (maxV * (3 - g) / 3).toFixed(1);
        out += '<line x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y + '" y2="' + y + '" stroke="rgba(128,128,128,0.15)"/>';
        out += '<text x="' + (PAD.l - 6) + '" y="' + (y + 4) + '" font-size="10" fill="var(--pg-meta)" text-anchor="end">' + label + '</text>';
    }
    data.forEach(function(d, i) {
        var bh = (d.avg / maxV) * innerH;
        var x = PAD.l + i * gap + (gap - bw) / 2;
        var y = PAD.t + innerH - bh;
        var isWeekend = (i >= 5);
        var color = isWeekend ? '#607d8b' : (d.avg >= 8 ? '#58d68d' : (d.avg >= 4 ? '#f7dc6f' : '#ec7063'));
        out += '<rect x="' + x + '" y="' + y + '" width="' + bw + '" height="' + bh + '" fill="' + color + '" rx="4" opacity="0.85">'
            + '<title>' + names[i] + ': ' + fmtH(d.avg) + ' · всего ' + fmtH(d.total) + ' за ' + d.days + ' дн</title></rect>';
        if (d.avg > 0) {
            out += '<text x="' + (x + bw / 2) + '" y="' + (y - 6) + '" font-size="10" font-weight="700" fill="var(--pg-accent)" text-anchor="middle">' + d.avg.toFixed(1) + '</text>';
        }
        out += '<text x="' + (x + bw / 2) + '" y="' + (H - 12) + '" font-size="12" font-weight="700" fill="var(--pg-meta)" text-anchor="middle">' + names[i] + '</text>';
    });
    out += '</svg>';
    el.innerHTML = out;
}

function renderStatus(data){
    var el = document.getElementById('chartStatus');
    var items = [
        { key: 'active',   label: 'Активные',   color: '#5dade2' },
        { key: 'overdue',  label: 'Просрочено', color: '#ec7063' },
        { key: 'paused',   label: 'Пауза',      color: '#f7dc6f' },
        { key: 'done',     label: 'Закрыто',    color: '#58d68d' }
    ];
    var total = items.reduce(function(s, it){ return s + (data[it.key] || 0); }, 0);
    if (!total) { el.innerHTML = '<div class="empty">Нет задач</div>'; }
    else {
        var cx = 100, cy = 100, r = 72, ir = 46;
        var ang = -Math.PI / 2;
        var out = '<svg viewBox="0 0 200 200" preserveAspectRatio="xMidYMid meet" style="max-width:220px;margin:0 auto;">';
        items.forEach(function(it) {
            var v = data[it.key] || 0;
            if (!v) return;
            var slice = (v / total) * Math.PI * 2;
            var a1 = ang, a2 = ang + slice;
            var x1 = cx + r * Math.cos(a1),  y1 = cy + r * Math.sin(a1);
            var x2 = cx + r * Math.cos(a2),  y2 = cy + r * Math.sin(a2);
            var xi1 = cx + ir * Math.cos(a1), yi1 = cy + ir * Math.sin(a1);
            var xi2 = cx + ir * Math.cos(a2), yi2 = cy + ir * Math.sin(a2);
            var large = slice > Math.PI ? 1 : 0;
            out += '<path d="M ' + x1.toFixed(2) + ' ' + y1.toFixed(2)
                + ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x2.toFixed(2) + ' ' + y2.toFixed(2)
                + ' L ' + xi2.toFixed(2) + ' ' + yi2.toFixed(2)
                + ' A ' + ir + ' ' + ir + ' 0 ' + large + ' 0 ' + xi1.toFixed(2) + ' ' + yi1.toFixed(2)
                + ' Z" fill="' + it.color + '" stroke="rgba(0,0,0,0.2)"><title>' + it.label + ': ' + v + '</title></path>';
            ang = a2;
        });
        out += '<text x="' + cx + '" y="' + (cy - 2) + '" font-size="22" font-weight="800" fill="var(--pg-accent)" text-anchor="middle">' + total + '</text>';
        out += '<text x="' + cx + '" y="' + (cy + 16) + '" font-size="10" fill="var(--pg-meta)" text-anchor="middle">задач</text>';
        out += '</svg>';
        el.innerHTML = out;
    }
    var grid = document.getElementById('statusGrid');
    grid.innerHTML = items.map(function(it) {
        var v = data[it.key] || 0;
        return '<div class="status-cell" style="--sc:' + it.color + ';"><div class="v">' + v + '</div><div class="l">' + it.label + '</div></div>';
    }).join('');
}

function renderList(elId, cntId, items, cls){
    var el = document.getElementById(elId);
    var cnt = document.getElementById(cntId);
    if (cnt) cnt.textContent = items.length;
    if (!el) return;
    if (!items.length) { el.innerHTML = '<div class="empty">Пусто 🎉</div>'; return; }
    el.innerHTML = items.map(function(t) {
        return '<div class="row-item ' + cls + '">'
            + '<span class="ico">' + esc(t.icon || '📋') + '</span>'
            + '<div class="body"><div class="nm">' + esc(t.name) + '</div>'
            + (t.meta ? '<div class="meta">' + esc(t.meta) + '</div>' : '') + '</div>'
            + (t.pill ? '<span class="pill ' + (t.pillCls || '') + '">' + esc(t.pill) + '</span>' : '')
            + '</div>';
    }).join('');
}

function load(){
    document.getElementById('kpis').innerHTML = '<div class="loading">Загрузка…</div>';
    var q = '?preset=' + encodeURIComponent(state.preset);
    if (state.preset === 'custom') q += '&from=' + encodeURIComponent(state.from) + '&to=' + encodeURIComponent(state.to);
    fetch('/api/plugins/my_week/data' + q, {credentials: 'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (!d || !d.success) { alert('Ошибка загрузки'); return; }
            if (!d.employee || !d.employee.id) {
                document.querySelector('.w').innerHTML = '<div class="card"><div class="empty">Ваш аккаунт не привязан к сотруднику</div></div>';
                return;
            }
            renderWho(d);
            renderKpis(d.stats || {});
            renderActivity(d.activity || []);
            renderWeekdays(d.weekdays || []);
            renderStatus(d.statuses || {});
            renderList('lOverdue', 'cOverdue', d.overdue || [], 'danger');
            renderList('lPending', 'cPending', d.pending || [], 'warn');
            renderList('lDone', 'cDone', d.done_list || [], 'ok');
            renderList('lTop', 'cTop', d.top_tasks || [], 'info');
        })
        .catch(function(){ alert('Ошибка соединения'); });
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
document.getElementById('pApply').addEventListener('click', function(){
    var f = document.getElementById('pFrom').value;
    var t = document.getElementById('pTo').value;
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


# ============================================================
# Утилиты
# ============================================================
def _parse_iso(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return None


def _period_from_args():
    preset = (request.args.get('preset') or 'week').strip().lower()
    today = date.today()
    if preset == 'week':
        monday = today - timedelta(days=today.weekday())
        return monday, today, 'week'
    if preset == 'prev_week':
        this_monday = today - timedelta(days=today.weekday())
        prev_monday = this_monday - timedelta(days=7)
        prev_sunday = this_monday - timedelta(days=1)
        return prev_monday, prev_sunday, 'prev_week'
    if preset == 'month':
        return today.replace(day=1), today, 'month'
    if preset == 'quarter':
        m = (today.month - 1) // 3 * 3 + 1
        return today.replace(month=m, day=1), today, 'quarter'
    if preset == 'year':
        return today.replace(month=1, day=1), today, 'year'
    d1 = _parse_iso(request.args.get('from') or '')
    d2 = _parse_iso(request.args.get('to') or '')
    if d1 and d2 and d1 <= d2:
        # ограничение — 365 дней
        if (d2 - d1).days > 365:
            d2 = d1 + timedelta(days=365)
        return d1, d2, 'custom'
    monday = today - timedelta(days=today.weekday())
    return monday, today, 'week'


def _workdays_between(d1, d2):
    n = 0
    cur = d1
    while cur <= d2:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


def _prev_period_same_length(d1, d2):
    span = (d2 - d1).days + 1
    return d1 - timedelta(days=span), d1 - timedelta(days=1)


# ============================================================
# Регистрация
# ============================================================
def register(app, db, hooks):
    print('[my_week] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/my_week.js', methods=['GET'])
    def _mw_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/plugins/my_week/', methods=['GET'])
    def _mw_page():
        try:
            from auth import current_user
            u = current_user(db)
        except Exception:
            u = None
        if not u:
            return redirect('/login')
        return Response(_page_html(), mimetype='text/html')

    @app.route('/api/plugins/my_week/data', methods=['GET'])
    def _mw_data():
        try:
            from auth import current_user
            u = current_user(db)
        except Exception:
            u = None
        if not u:
            return jsonify({'success': False, 'error': 'auth'}), 401

        emp_id = (u.get('employee_id') or '').strip()
        empty = {
            'success': True, 'employee': {}, 'stats': {},
            'overdue': [], 'pending': [], 'done_list': [], 'top_tasks': [],
            'activity': [], 'weekdays': [], 'statuses': {},
            'from': '', 'to': '',
        }
        if not emp_id:
            return jsonify(empty)

        d1, d2, preset = _period_from_args()
        d1_iso = d1.strftime('%Y-%m-%d')
        d2_iso = d2.strftime('%Y-%m-%d')
        wd = _workdays_between(d1, d2)

        prev_d1, prev_d2 = _prev_period_same_length(d1, d2)
        prev_d1_iso = prev_d1.strftime('%Y-%m-%d')
        prev_d2_iso = prev_d2.strftime('%Y-%m-%d')

        data = db.load_all()
        emp = next((e for e in data.get('employees', []) if e['id'] == emp_id), None)
        if not emp:
            return jsonify({'success': False, 'error': 'employee not found'}), 404

        today = date.today()
        today_iso = today.strftime('%Y-%m-%d')

        my_logs = [l for l in data.get('log', []) if l.get('employee_id') == emp_id]

        # Считаем всё за период
        hours_period = 0.0
        hours_prev = 0.0
        done_ids_period = set()
        active_days = set()
        task_hours = {}
        activity_map = {}
        weekday_hours = {i: 0.0 for i in range(7)}
        weekday_days = {i: set() for i in range(7)}

        for l in my_logs:
            ld = l.get('date') or ''
            try:
                h = float(l.get('hours') or 0)
            except Exception:
                h = 0

            if d1_iso <= ld <= d2_iso:
                hours_period += h
                tid = l.get('task_id')
                if tid:
                    task_hours[tid] = task_hours.get(tid, 0.0) + h
                if l.get('status') == 'done' and tid:
                    done_ids_period.add(tid)
                if h > 0:
                    active_days.add(ld)
                    try:
                        dt = datetime.strptime(ld, '%Y-%m-%d').date()
                        wd_idx = dt.weekday()
                        weekday_hours[wd_idx] += h
                        weekday_days[wd_idx].add(ld)
                    except Exception:
                        pass

                row = activity_map.setdefault(ld, {'hours': 0.0, 'done': 0})
                row['hours'] += h
                if l.get('status') == 'done':
                    row['done'] += 1

            if prev_d1_iso <= ld <= prev_d2_iso:
                hours_prev += h

        avg_per_day = round(hours_period / max(len(active_days), 1) * 4) / 4 if active_days else 0
        capacity_pct = round(100 * hours_period / (wd * 8)) if wd else 0

        # --- Список 1: просрочено (снимок сейчас, независимо от периода)
        my_tasks = [t for t in data.get('tasks', []) if emp_id in (t.get('assignees') or [])]
        active_tasks = [t for t in my_tasks if t.get('status') == 'active']

        overdue = []
        for t in my_tasks:
            if t.get('status') not in ('active', 'paused'):
                continue
            dl = t.get('deadline') or ''
            if not dl or dl >= today_iso:
                continue
            has_done = any(l.get('task_id') == t['id'] and l.get('status') == 'done' for l in my_logs)
            if has_done:
                continue
            try:
                days_past = (today - datetime.strptime(dl, '%Y-%m-%d').date()).days
            except Exception:
                days_past = 0
            overdue.append({
                'icon': t.get('icon', '📋'),
                'name': t.get('name', ''),
                'meta': 'Дедлайн ' + dl,
                'pill': str(days_past) + ' дн',
                'pillCls': 'danger',
            })
        overdue.sort(key=lambda x: -int(x['pill'].split()[0]))

        # --- Список 2: назначено, не начато
        pending = []
        my_logged_tasks = set(l.get('task_id') for l in my_logs if l.get('task_id'))
        for t in my_tasks:
            if t.get('status') not in ('active', 'paused'):
                continue
            if t['id'] in my_logged_tasks:
                continue
            dl = t.get('deadline') or ''
            if dl and dl < today_iso:
                continue
            pending.append({
                'icon': t.get('icon', '📋'),
                'name': t.get('name', ''),
                'meta': ('Дедлайн ' + dl) if dl else 'Без дедлайна',
                'pill': '',
                'pillCls': 'warn',
            })

        # --- Список 3: закрыто за период
        done_list = []
        for tid in done_ids_period:
            t = next((x for x in data.get('tasks', []) if x['id'] == tid), None)
            if not t:
                continue
            h = task_hours.get(tid, 0)
            done_list.append({
                'icon': t.get('icon', '📋'),
                'name': t.get('name', ''),
                'meta': 'Часов за период: ' + str(round(h * 4) / 4),
                'pill': fmt_h(round(h * 4) / 4),
                'pillCls': 'ok',
            })
        done_list.sort(key=lambda x: -float(x['meta'].split(': ')[-1].replace(' ч','')) if ':' in x['meta'] else 0)

        # --- Список 4: топ задач за период
        top_tasks = []
        for tid, h in sorted(task_hours.items(), key=lambda kv: -kv[1])[:10]:
            t = next((x for x in data.get('tasks', []) if x['id'] == tid), None)
            if not t:
                continue
            top_tasks.append({
                'icon': t.get('icon', '📋'),
                'name': t.get('name', ''),
                'meta': 'За период',
                'pill': fmt_h(round(h * 4) / 4),
                'pillCls': 'info',
            })

        # --- Активность за период (если > 60 дней — по неделям)
        activity = []
        span = (d2 - d1).days
        if span <= 60:
            cur = d1
            while cur <= d2:
                dk = cur.strftime('%Y-%m-%d')
                row = activity_map.get(dk, {'hours': 0.0, 'done': 0})
                activity.append({'date': dk, 'hours': round(row['hours'] * 4) / 4, 'done': row['done']})
                cur += timedelta(days=1)
        else:
            cur = d1
            while cur <= d2:
                week_end = min(cur + timedelta(days=6), d2)
                wh = 0.0
                wdone = 0
                c2 = cur
                while c2 <= week_end:
                    dk = c2.strftime('%Y-%m-%d')
                    row = activity_map.get(dk)
                    if row:
                        wh += row['hours']
                        wdone += row['done']
                    c2 += timedelta(days=1)
                activity.append({'date': cur.strftime('%Y-%m-%d'), 'hours': round(wh * 4) / 4, 'done': wdone})
                cur += timedelta(days=7)

        # --- График по дням недели
        weekdays = []
        for i in range(7):
            days_cnt = len(weekday_days[i])
            total_h = weekday_hours[i]
            avg = round(total_h / days_cnt, 1) if days_cnt else 0
            weekdays.append({
                'idx': i,
                'total': round(total_h * 4) / 4,
                'days': days_cnt,
                'avg': avg,
            })

        # --- Статусы моих задач
        statuses = {
            'active': len([t for t in my_tasks if t.get('status') == 'active']),
            'paused': len([t for t in my_tasks if t.get('status') == 'paused']),
            'overdue': len(overdue),
            'done': len(done_ids_period),
        }

        return jsonify({
            'success': True,
            'preset': preset,
            'employee': {
                'id': emp_id,
                'name': emp.get('name', ''),
                'color': emp.get('color', '#888'),
            },
            'from': d1_iso,
            'to': d2_iso,
            'stats': {
                'hours_period': round(hours_period * 4) / 4,
                'hours_prev': round(hours_prev * 4) / 4,
                'done_period': len(done_ids_period),
                'avg_per_day': avg_per_day,
                'capacity_pct': capacity_pct,
                'workdays': wd,
                'active_tasks': len(active_tasks),
                'overdue': len(overdue),
                'pending': len(pending),
            },
            'statuses': statuses,
            'overdue': overdue[:15],
            'pending': pending[:15],
            'done_list': done_list[:15],
            'top_tasks': top_tasks[:10],
            'activity': activity,
            'weekdays': weekdays,
        })

    def on_startup(**ctx):
        print('[my_week] готов — выбор периода + дни недели')

    hooks.on('on_startup', on_startup)


def fmt_h(h):
    h = float(h) or 0
    if h == int(h):
        return str(int(h)) + ' ч'
    return ('%.2f' % h).rstrip('0').rstrip('.') + ' ч'


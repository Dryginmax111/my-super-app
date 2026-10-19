"""plugins/pulse.py — Пульс проекта с выбором периода."""

__version__ = '3.0'
__description__ = 'Пульс: KPI, графики, сводные таблицы, health-score. Период: неделя / месяц / квартал / год'

from datetime import date, datetime, timedelta
from flask import request, jsonify, Response, redirect


# ============================================================
# JS — кнопка в шапку трекера
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
        id: 'pulse',
        icon: '💓',
        name: 'Пульс проекта',
        url: '/plugins/pulse/',
        perm: 'plugin.pulse.use'
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
<title>Пульс проекта</title>
<script src="/static/plugin_theme.js"></script>
<script src="/static/plugin_mask.js"></script>
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
.w { max-width: 1800px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }

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
.back:hover { background: var(--pg-accent-bg); color: var(--pg-accent); }
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
    border: 1px solid var(--pg-input-border, rgba(245,215,110,0.26));
    background: var(--pg-input-bg, #232323);
    color: var(--pg-text, #e8e8e8);
    font-family: inherit; font-size: 0.85rem; cursor: pointer;
}
.period-btn:hover { color: var(--pg-accent); border-color: var(--pg-accent); }
.range-info {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 12px; border-radius: 20px;
    background: var(--pg-inner-bg, #232323);
    border: 1px solid var(--pg-card-border-soft, rgba(245,215,110,0.14));
    font-size: 0.75rem; color: var(--pg-desc, #c8c8c8);
}
.range-info b { color: var(--pg-accent, #f5d76e); }

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
.kpi .v { font-size: 1.55rem; font-weight: 800; line-height: 1.05; color: var(--pg-accent, #f5d76e); }
.kpi .l { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.8px; color: var(--pg-meta, #a0a0a0); font-weight: 700; margin-top: 4px; }
.kpi.danger .v { color: var(--pg-err, #ec7063); }
.kpi.warn .v { color: var(--pg-warn, #f7dc6f); }
.kpi.ok .v { color: var(--pg-ok, #58d68d); }
.kpi.info .v { color: var(--pg-info, #6dc2f0); }

/* Health */
.health {
    padding: 20px 24px; background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 14px; display: grid;
    grid-template-columns: auto 1fr auto; gap: 20px; align-items: center;
}
.health-ring { position: relative; width: 88px; height: 88px; }
.health-ring svg { transform: rotate(-90deg); }
.health-ring .val {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; font-weight: 800; color: var(--pg-accent, #f5d76e);
}
.health .title { font-size: 1.05rem; font-weight: 800; color: var(--pg-text); }
.health .desc { font-size: 0.85rem; color: var(--pg-meta); margin-top: 4px; line-height: 1.5; }
.health .badge { padding: 6px 14px; border-radius: 20px; font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; }
.health .badge.ok { background: rgba(46,204,113,0.18); color: #58d68d; }
.health .badge.warn { background: rgba(241,196,15,0.20); color: #f7dc6f; }
.health .badge.danger { background: rgba(231,76,60,0.20); color: #ec7063; }

/* Layout */
.main-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 14px; align-items: start; }
@media (max-width: 1200px) { .main-grid { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 14px; }

.card { padding: 16px 18px; background: var(--pg-card-bg, #1a1a1a); border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22)); border-radius: 14px; }
.card-title {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.78rem; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.8px;
    color: var(--pg-accent, #f5d76e);
    margin-bottom: 12px; padding-bottom: 8px;
    border-bottom: 1px dashed var(--pg-card-border-soft, rgba(245,215,110,0.14));
}
.card-title .cnt {
    margin-left: auto; font-size: 0.68rem;
    padding: 1px 8px; border-radius: 8px;
    background: var(--pg-accent-bg, rgba(245,215,110,0.14));
    color: var(--pg-accent, #f5d76e); font-weight: 700;
}
.card-title.danger { color: var(--pg-err, #ec7063); }
.card-title.warn { color: var(--pg-warn, #f7dc6f); }

table.mini { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
table.mini th { text-align: left; padding: 6px 8px; font-size: 0.68rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: var(--pg-meta); border-bottom: 1px solid var(--pg-card-border-soft); white-space: nowrap; }
table.mini th.num, table.mini td.num { text-align: right; }
table.mini td { padding: 6px 8px; border-bottom: 1px solid var(--pg-card-border-soft); color: var(--pg-text); }
table.mini tr:hover td { background: var(--pg-inner-bg); }
table.mini td.num { font-weight: 700; }
table.mini td.err { color: var(--pg-err); }
table.mini td.ok { color: var(--pg-ok); }
table.mini td.muted { color: var(--pg-meta); }
.emp-cell { display: flex; align-items: center; gap: 6px; }
.emp-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

.chart-wrap svg { display: block; width: 100%; height: auto; }
.chart-legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; font-size: 0.72rem; color: var(--pg-meta); }
.chart-legend .it { display: flex; align-items: center; gap: 5px; }
.chart-legend .sw { width: 12px; height: 12px; border-radius: 3px; }

.list { display: flex; flex-direction: column; gap: 5px; }
.row-item {
    display: flex; gap: 8px; align-items: center;
    padding: 8px 10px; background: var(--pg-inner-bg);
    border-radius: 8px; border-left: 3px solid var(--pg-meta);
    font-size: 0.83rem;
}
.row-item.danger { border-left-color: var(--pg-err); }
.row-item.warn { border-left-color: var(--pg-warn); }
.row-item.info { border-left-color: var(--pg-info); }
.row-item .ico { font-size: 1rem; flex-shrink: 0; }
.row-item .nm { flex: 1; min-width: 0; word-break: break-word; }
.row-item .meta { color: var(--pg-meta); font-size: 0.72rem; white-space: nowrap; }
.row-item .pill {
    padding: 1px 8px; border-radius: 8px;
    font-size: 0.68rem; font-weight: 800;
    background: var(--pg-accent-bg); color: var(--pg-accent);
    white-space: nowrap;
}
.empty, .loading { text-align: center; padding: 24px 12px; color: var(--pg-meta); font-style: italic; font-size: 0.82rem; }

.problems-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 1000px) { .problems-grid { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .head { padding: 12px 14px; } .head h1 { font-size: 1.05rem; } .health { grid-template-columns: 1fr; text-align: center; } .health .badge { margin: 0 auto; } }
</style>
</head>
<body>
<div class="w">

    <div class="head">
        <a class="back" href="/">← К трекеру</a>
        <h1>💓 Пульс проекта</h1>
        <div class="presets">
            <button data-preset="week">Неделя</button>
            <button data-preset="month" class="active">Месяц</button>
            <button data-preset="quarter">Квартал</button>
            <button data-preset="year">Год</button>
        </div>
        <input type="date" id="pFrom" class="period">
        <input type="date" id="pTo" class="period">
        <button class="period-btn" id="pApply">✓</button>
        <div class="range-info" id="rangeInfo"></div>
    </div>

    <div class="kpis" id="kpis"></div>
    <div class="health" id="health"></div>

    <div class="main-grid">
        <div class="col">
            <div class="card">
                <div class="card-title"><span>📈</span><span>Динамика активности за период</span></div>
                <div class="chart-wrap" id="chartActivity"></div>
                <div class="chart-legend">
                    <div class="it"><span class="sw" style="background:#5dade2;"></span>Часы в день</div>
                    <div class="it"><span class="sw" style="background:#58d68d;"></span>Закрыто задач</div>
                </div>
            </div>
            <div class="card">
                <div class="card-title"><span>🍩</span><span>Распределение задач по статусам</span></div>
                <div class="chart-wrap" id="chartStatus"></div>
                <div class="chart-legend" id="legendStatus"></div>
            </div>
            <div class="card">
                <div class="card-title"><span>📊</span><span>Топ дней с просрочками</span></div>
                <div class="chart-wrap" id="chartOverdueDays"></div>
            </div>
        </div>

        <div class="col">
            <div class="card">
                <div class="card-title"><span>🏢</span><span>По отделам за период</span></div>
                <div id="tblDepts"><div class="empty">Загрузка…</div></div>
            </div>
            <div class="card">
                <div class="card-title"><span>👥</span><span>По командам за период</span></div>
                <div id="tblTeams"><div class="empty">Загрузка…</div></div>
            </div>
            <div class="card">
                <div class="card-title danger"><span>🔥</span><span>Топ просрочек по сотрудникам</span></div>
                <div id="tblOverdueEmps"><div class="empty">Загрузка…</div></div>
            </div>
            <div class="card">
                <div class="card-title warn"><span>⏸</span><span>Топ без активности</span></div>
                <div id="tblStaleEmps"><div class="empty">Загрузка…</div></div>
            </div>
        </div>
    </div>

    <div class="problems-grid">
        <div class="card">
            <div class="card-title danger"><span>⚠</span><span>Просроченные</span><span class="cnt" id="cOverdue">0</span></div>
            <div class="list" id="lOverdue"></div>
        </div>
        <div class="card">
            <div class="card-title warn"><span>⏸</span><span>Нет активности 7+ дней</span><span class="cnt" id="cStale">0</span></div>
            <div class="list" id="lStale"></div>
        </div>
        <div class="card">
            <div class="card-title"><span>⏰</span><span>Дедлайн близко (≤3 дня)</span><span class="cnt" id="cSoon">0</span></div>
            <div class="list" id="lSoon"></div>
        </div>
        <div class="card">
            <div class="card-title danger"><span>🚪</span><span>Назначено на уволенных</span><span class="cnt" id="cOrphan">0</span></div>
            <div class="list" id="lOrphan"></div>
        </div>
        <div class="card">
            <div class="card-title warn"><span>👻</span><span>Без исполнителей</span><span class="cnt" id="cNoAsg">0</span></div>
            <div class="list" id="lNoAsg"></div>
        </div>
        <div class="card">
            <div class="card-title"><span>🔄</span><span>Долго в работе (30+ дней)</span><span class="cnt" id="cLong">0</span></div>
            <div class="list" id="lLong"></div>
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

var state = { preset:'month', from:'', to:'' };

function renderKpis(s){
    var el = document.getElementById('kpis');
    var cards = [
        {v: fmtI(s.tasks_total), l: 'Активных задач', cls: ''},
        {v: fmtI(s.tasks_overdue), l: 'Просрочено', cls: 'danger'},
        {v: fmtI(s.tasks_soon), l: 'Дедлайн ≤3 дня', cls: 'warn'},
        {v: fmtI(s.tasks_stale), l: 'Без активности 7+', cls: 'warn'},
        {v: fmtI(s.tasks_no_assignees), l: 'Без исполнителей', cls: 'warn'},
        {v: fmtI(s.tasks_orphan), l: 'На уволенных', cls: 'danger'},
        {v: fmtH(s.hours_period), l: 'Часов за период', cls: 'info'},
        {v: fmtI(s.done_period), l: 'Закрыто за период', cls: 'ok'}
    ];
    el.innerHTML = cards.map(function(c){
        return '<div class="kpi ' + c.cls + '"><div class="v">' + c.v + '</div><div class="l">' + c.l + '</div></div>';
    }).join('');
}

function renderHealth(s){
    var el = document.getElementById('health');
    var score = s.health_score;
    var cls = score >= 75 ? 'ok' : (score >= 50 ? 'warn' : 'danger');
    var verdict = score >= 75 ? 'Хорошо' : (score >= 50 ? 'Есть проблемы' : 'Критично');
    var r = 36, c = 2 * Math.PI * r;
    var dash = c * (score / 100);
    var color = score >= 75 ? '#58d68d' : (score >= 50 ? '#f7dc6f' : '#ec7063');
    var ring = ''
        + '<div class="health-ring">'
        +   '<svg width="88" height="88" viewBox="0 0 88 88">'
        +     '<circle cx="44" cy="44" r="' + r + '" fill="none" stroke="rgba(128,128,128,0.20)" stroke-width="6"/>'
        +     '<circle cx="44" cy="44" r="' + r + '" fill="none" stroke="' + color + '" stroke-width="6" stroke-dasharray="' + dash + ' ' + (c - dash) + '" stroke-linecap="round"/>'
        +   '</svg>'
        +   '<div class="val">' + score + '</div>'
        + '</div>';
    el.innerHTML = ring
        + '<div><div class="title">Здоровье отдела</div>'
        +   '<div class="desc">Индекс: просрочки, задачи без активности, без исполнителей, на уволенных. Не зависит от периода.</div></div>'
        + '<div class="badge ' + cls + '">' + verdict + '</div>';
}

function renderChartActivity(series){
    var el = document.getElementById('chartActivity');
    if (!series || !series.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    var W = 720, H = 200, PAD = { l: 36, r: 12, t: 12, b: 28 };
    var innerW = W - PAD.l - PAD.r, innerH = H - PAD.t - PAD.b;
    var n = series.length;
    var maxH = Math.max.apply(null, series.map(function(d){return d.hours;}).concat([1]));
    var maxD = Math.max.apply(null, series.map(function(d){return d.done;}).concat([1]));
    var bw = innerW / n;
    var out = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">';
    for (var g = 0; g <= 4; g++) {
        var y = PAD.t + (innerH * g / 4);
        var label = Math.round(maxH * (4 - g) / 4);
        out += '<line x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y + '" y2="' + y + '" stroke="rgba(128,128,128,0.15)" stroke-width="1"/>';
        out += '<text x="' + (PAD.l - 6) + '" y="' + (y + 4) + '" font-size="10" fill="var(--pg-meta)" text-anchor="end">' + label + '</text>';
    }
    series.forEach(function(d, i) {
        var bh = (d.hours / maxH) * innerH;
        var x = PAD.l + i * bw + bw * 0.15;
        var w = bw * 0.7;
        var y = PAD.t + innerH - bh;
        out += '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + bh + '" fill="url(#barGrad)" rx="2"><title>' + d.date + ': ' + fmtH(d.hours) + '</title></rect>';
        var dy = PAD.t + innerH - (d.done / maxD) * (innerH * 0.4);
        var cx = PAD.l + i * bw + bw * 0.5;
        out += '<circle cx="' + cx + '" cy="' + dy + '" r="2.5" fill="#58d68d"><title>' + d.date + ': закрыто ' + d.done + '</title></circle>';
        if (i % Math.max(1, Math.floor(n / 10)) === 0) {
            out += '<text x="' + cx + '" y="' + (H - 8) + '" font-size="9" fill="var(--pg-meta)" text-anchor="middle">' + fmtD(d.date) + '</text>';
        }
    });
    out += '<defs><linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#6dc2f0"/><stop offset="100%" stop-color="#2874a6"/></linearGradient></defs>';
    out += '</svg>';
    el.innerHTML = out;
}

function renderChartStatus(data){
    var el = document.getElementById('chartStatus');
    var legend = document.getElementById('legendStatus');
    var items = [
        { key: 'active', label: 'Активные', color: '#5dade2' },
        { key: 'paused', label: 'Приостановлены', color: '#f7dc6f' },
        { key: 'overdue', label: 'Просрочены', color: '#ec7063' },
        { key: 'done', label: 'Выполнены', color: '#58d68d' },
        { key: 'archived', label: 'Архив', color: '#aab7b8' }
    ];
    var total = items.reduce(function(s, it){ return s + (data[it.key] || 0); }, 0);
    if (!total) { el.innerHTML = '<div class="empty">Нет задач</div>'; legend.innerHTML = ''; return; }
    var cx = 110, cy = 110, r = 80, ir = 52;
    var ang = -Math.PI / 2;
    var out = '<svg viewBox="0 0 220 220" preserveAspectRatio="xMidYMid meet" style="max-width:220px;margin:0 auto;">';
    items.forEach(function(it) {
        var v = data[it.key] || 0;
        if (!v) return;
        var slice = (v / total) * Math.PI * 2;
        var a1 = ang, a2 = ang + slice;
        var x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
        var x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
        var xi1 = cx + ir * Math.cos(a1), yi1 = cy + ir * Math.sin(a1);
        var xi2 = cx + ir * Math.cos(a2), yi2 = cy + ir * Math.sin(a2);
        var large = slice > Math.PI ? 1 : 0;
        out += '<path d="M ' + x1.toFixed(2) + ' ' + y1.toFixed(2) + ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x2.toFixed(2) + ' ' + y2.toFixed(2) + ' L ' + xi2.toFixed(2) + ' ' + yi2.toFixed(2) + ' A ' + ir + ' ' + ir + ' 0 ' + large + ' 0 ' + xi1.toFixed(2) + ' ' + yi1.toFixed(2) + ' Z" fill="' + it.color + '" stroke="rgba(0,0,0,0.25)" stroke-width="1"><title>' + it.label + ': ' + v + '</title></path>';
        ang = a2;
    });
    out += '<text x="' + cx + '" y="' + (cy - 4) + '" font-size="24" font-weight="800" fill="var(--pg-accent)" text-anchor="middle">' + total + '</text>';
    out += '<text x="' + cx + '" y="' + (cy + 16) + '" font-size="11" fill="var(--pg-meta)" text-anchor="middle">задач</text>';
    out += '</svg>';
    el.innerHTML = out;
    legend.innerHTML = items.map(function(it) {
        var v = data[it.key] || 0;
        if (!v) return '';
        var pct = Math.round(100 * v / total);
        return '<div class="it"><span class="sw" style="background:' + it.color + ';"></span>' + it.label + ' <b style="color:var(--pg-text);">' + v + '</b> (' + pct + '%)</div>';
    }).join('');
}

function renderChartOverdueDays(series){
    var el = document.getElementById('chartOverdueDays');
    var items = series.filter(function(x){ return x.count > 0; }).slice(0, 10);
    if (!items.length) { el.innerHTML = '<div class="empty">Просрочек нет 🎉</div>'; return; }
    var html = '<table class="mini"><thead><tr><th>Дедлайн</th><th class="num">Просрочено</th><th class="num">Дней</th></tr></thead><tbody>';
    items.forEach(function(x) {
        html += '<tr><td>' + esc(x.deadline) + '</td><td class="num"><span class="pill">' + x.count + '</span></td><td class="num err">' + (x.days_past || 0) + ' дн</td></tr>';
    });
    html += '</tbody></table>';
    el.innerHTML = html;
}

function renderTableDepts(depts){
    var el = document.getElementById('tblDepts');
    if (!depts || !depts.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    var h = '<table class="mini"><thead><tr><th>Отдел</th><th class="num">Задач</th><th class="num">Просроч.</th><th class="num">Часов</th></tr></thead><tbody>';
    depts.forEach(function(d) {
        var ovCls = d.overdue > 0 ? 'err' : 'muted';
        h += '<tr><td>' + esc(d.name) + '</td><td class="num">' + d.tasks + '</td><td class="num ' + ovCls + '">' + d.overdue + '</td><td class="num">' + fmtH(d.hours) + '</td></tr>';
    });
    h += '</tbody></table>';
    el.innerHTML = h;
}

function renderTableTeams(teams){
    var el = document.getElementById('tblTeams');
    if (!teams || !teams.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
    var h = '<table class="mini"><thead><tr><th>Команда</th><th class="num">Задач</th><th class="num">Просроч.</th><th class="num">Часов</th></tr></thead><tbody>';
    teams.forEach(function(d) {
        var ovCls = d.overdue > 0 ? 'err' : 'muted';
        h += '<tr><td>' + esc(d.name) + '</td><td class="num">' + d.tasks + '</td><td class="num ' + ovCls + '">' + d.overdue + '</td><td class="num">' + fmtH(d.hours) + '</td></tr>';
    });
    h += '</tbody></table>';
    el.innerHTML = h;
}

function renderTableOverdueEmps(emps){
    var el = document.getElementById('tblOverdueEmps');
    if (!emps || !emps.length) { el.innerHTML = '<div class="empty">Просрочек нет</div>'; return; }
    var h = '<table class="mini"><thead><tr><th>Сотрудник</th><th class="num">Просроч.</th><th class="num">Макс. дней</th></tr></thead><tbody>';
    emps.forEach(function(e) {
        h += '<tr><td><div class="emp-cell"><span class="emp-dot" style="background:' + esc(e.color || '#888') + ';"></span>' + (window.__trkEscName?window.__trkEscName(e.name):esc(e.name)) + '</div></td><td class="num err">' + e.overdue + '</td><td class="num muted">' + e.max_days + ' дн</td></tr>';
    });
    h += '</tbody></table>';
    el.innerHTML = h;
}

function renderTableStaleEmps(emps){
    var el = document.getElementById('tblStaleEmps');
    if (!emps || !emps.length) { el.innerHTML = '<div class="empty">Активность есть у всех</div>'; return; }
    var h = '<table class="mini"><thead><tr><th>Сотрудник</th><th class="num">Задач без отметок</th><th class="num">Макс. дней</th></tr></thead><tbody>';
    emps.forEach(function(e) {
        h += '<tr><td><div class="emp-cell"><span class="emp-dot" style="background:' + esc(e.color || '#888') + ';"></span>' + (window.__trkEscName?window.__trkEscName(e.name):esc(e.name)) + '</div></td><td class="num" style="color:var(--pg-warn);">' + e.count + '</td><td class="num muted">' + e.max_days + ' дн</td></tr>';
    });
    h += '</tbody></table>';
    el.innerHTML = h;
}

function renderList(id, cntId, items, cls){
    var el = document.getElementById(id);
    var cnt = document.getElementById(cntId);
    if (cnt) cnt.textContent = items.length;
    if (!el) return;
    if (!items.length) { el.innerHTML = '<div class="empty">Все чисто 🎉</div>'; return; }
    el.innerHTML = items.map(function(t){
        return '<div class="row-item ' + cls + '"><span class="ico">' + esc(t.icon || '📋') + '</span><span class="nm">' + esc(t.name) + '</span>' + (t.meta ? '<span class="meta">' + esc(t.meta) + '</span>' : '') + (t.pill ? '<span class="pill">' + esc(t.pill) + '</span>' : '') + '</div>';
    }).join('');
}

function load(){
    var el = document.getElementById('list');
    var q = '?preset=' + encodeURIComponent(state.preset);
    if (state.preset === 'custom') q += '&from=' + encodeURIComponent(state.from) + '&to=' + encodeURIComponent(state.to);
    fetch('/api/plugins/pulse/data' + q, {credentials: 'same-origin'})
        .then(function(r){ return r.json(); })
        .then(function(d){
            if (!d || !d.success) { alert('Ошибка загрузки'); return; }
            document.getElementById('rangeInfo').innerHTML = '<span>📅</span> <b>' + d.from + '</b> → <b>' + d.to + '</b> · <b>' + d.workdays + '</b> раб. дн.';
            renderKpis(d.stats || {});
            renderHealth(d.stats || {});
            renderChartActivity(d.activity || []);
            renderChartStatus(d.statuses || {});
            renderChartOverdueDays(d.overdue_days || []);
            renderTableDepts(d.by_dept || []);
            renderTableTeams(d.by_team || []);
            renderTableOverdueEmps(d.overdue_emps || []);
            renderTableStaleEmps(d.stale_emps || []);
            renderList('lOverdue', 'cOverdue', d.overdue || [], 'danger');
            renderList('lStale', 'cStale', d.stale || [], 'warn');
            renderList('lSoon', 'cSoon', d.deadline_soon || [], 'info');
            renderList('lOrphan', 'cOrphan', d.orphan || [], 'danger');
            renderList('lNoAsg', 'cNoAsg', d.no_assignees || [], 'warn');
            renderList('lLong', 'cLong', d.long_running || [], 'info');
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
    preset = (request.args.get('preset') or 'month').strip().lower()
    today = date.today()
    if preset == 'week':
        monday = today - timedelta(days=today.weekday())
        return monday, today, 'week'
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
        return d1, d2, 'custom'
    return today.replace(day=1), today, 'month'


def _workdays_between(d1, d2):
    n = 0
    cur = d1
    while cur <= d2:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


# ============================================================
# Регистрация
# ============================================================
def register(app, db, hooks):
    print('[pulse] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/pulse.js', methods=['GET'])
    def _pl_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/plugins/pulse/', methods=['GET'])
    def _pl_page():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return redirect('/login')
            if not user_has(db, u, 'plugin.pulse.use'):
                return redirect('/')
        except Exception:
            return redirect('/login')
        return Response(_page_html(), mimetype='text/html')

    @app.route('/api/plugins/pulse/data', methods=['GET'])
    def _pl_data():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return jsonify({'success': False, 'error': 'auth'}), 401
            if not user_has(db, u, 'plugin.pulse.use'):
                return jsonify({'success': False, 'error': 'forbidden'}), 403
        except Exception:
            return jsonify({'success': False, 'error': 'auth'}), 401

        d1, d2, preset = _period_from_args()
        d1_iso = d1.strftime('%Y-%m-%d')
        d2_iso = d2.strftime('%Y-%m-%d')
        wd = _workdays_between(d1, d2)

        data = db.load_all()
        today = date.today()
        today_iso = today.strftime('%Y-%m-%d')
        soon_iso = (today + timedelta(days=3)).strftime('%Y-%m-%d')

        teams_by_id = {t['id']: t for t in data.get('teams', [])}
        depts_by_id = {d['id']: d for d in data.get('departments', [])}
        emps_by_id = {e['id']: e for e in data.get('employees', [])}

        # Данные по логам
        last_log = {}
        logs_by_task = {}
        hours_period = 0.0
        done_ids_period = set()
        activity_map = {}

        try:
            _ifu = str(db.get_setting('stats_ignore_future', '1')) != '0'
        except Exception:
            _ifu = True
        for l in data.get('log', []):
            tid = l.get('task_id')
            if not tid:
                continue
            ld = l.get('date') or ''
            if _ifu and ld > today_iso:
                continue
            eid = l.get('employee_id') or ''

            logs_by_task.setdefault(tid, []).append(l)
            if not last_log.get(tid) or ld > last_log[tid]:
                last_log[tid] = ld

            try:
                h = float(l.get('hours') or 0)
            except Exception:
                h = 0

            if d1_iso <= ld <= d2_iso:
                hours_period += h
                if l.get('status') == 'done':
                    done_ids_period.add(tid)
                row = activity_map.setdefault(ld, {'hours': 0.0, 'done': 0})
                row['hours'] += h
                if l.get('status') == 'done':
                    row['done'] += 1

        # Задачи
        statuses = {'active': 0, 'paused': 0, 'overdue': 0, 'done': 0, 'archived': 0}
        overdue, stale, deadline_soon, orphan, no_assignees, long_running = [], [], [], [], [], []
        by_dept = {}
        by_team = {}
        overdue_days_counter = {}
        overdue_emps = {}
        stale_emps = {}

        for t in data.get('tasks', []):
            st = t.get('status', 'active')
            tid = t['id']
            assigns = [a for a in (t.get('assignees') or []) if a]
            dl = t.get('deadline') or ''

            if st == 'active':
                statuses['active'] += 1
            elif st == 'paused':
                statuses['paused'] += 1
            elif st == 'done':
                statuses['done'] += 1
            elif st == 'archived':
                statuses['archived'] += 1

            if st in ('active', 'paused'):
                # просрочка
                if dl and dl < today_iso:
                    statuses['overdue'] += 1
                    try:
                        days_past = (today - datetime.strptime(dl, '%Y-%m-%d').date()).days
                    except Exception:
                        days_past = 0
                    overdue.append({
                        'icon': t.get('icon', '📋'),
                        'name': t.get('name', ''),
                        'meta': 'дедлайн ' + dl,
                        'pill': str(days_past) + ' дн',
                    })
                    key = dl
                    rec = overdue_days_counter.setdefault(key, {'count': 0, 'days_past': days_past})
                    rec['count'] += 1
                    rec['days_past'] = max(rec['days_past'], days_past)
                    for a in assigns:
                        e = emps_by_id.get(a)
                        if not e:
                            continue
                        r = overdue_emps.setdefault(a, {'overdue': 0, 'max_days': 0, 'name': e.get('name', a), 'color': e.get('color', '#888')})
                        r['overdue'] += 1
                        r['max_days'] = max(r['max_days'], days_past)

                # нет активности
                ll = last_log.get(tid)
                if ll:
                    try:
                        since = (today - datetime.strptime(ll, '%Y-%m-%d').date()).days
                    except Exception:
                        since = 0
                    if since >= 7:
                        stale.append({'icon': t.get('icon', '📋'), 'name': t.get('name', ''), 'meta': 'последняя ' + ll, 'pill': str(since) + ' дн'})
                        for a in assigns:
                            e = emps_by_id.get(a)
                            if not e:
                                continue
                            r = stale_emps.setdefault(a, {'count': 0, 'max_days': 0, 'name': e.get('name', a), 'color': e.get('color', '#888')})
                            r['count'] += 1
                            r['max_days'] = max(r['max_days'], since)
                else:
                    sd = t.get('start_date') or ''
                    if sd:
                        try:
                            since = (today - datetime.strptime(sd, '%Y-%m-%d').date()).days
                        except Exception:
                            since = 0
                        if since >= 7:
                            stale.append({'icon': t.get('icon', '📋'), 'name': t.get('name', ''), 'meta': 'старт ' + sd, 'pill': str(since) + ' дн'})

                # дедлайн близко
                if dl and today_iso <= dl <= soon_iso:
                    if not logs_by_task.get(tid):
                        deadline_soon.append({'icon': t.get('icon', '📋'), 'name': t.get('name', ''), 'meta': 'дедлайн ' + dl, 'pill': ''})

                # уволенные
                if assigns:
                    fired = [a for a in assigns if emps_by_id.get(a, {}).get('fired')]
                    if fired and len(fired) == len(assigns):
                        orphan.append({'icon': t.get('icon', '📋'), 'name': t.get('name', ''), 'meta': '', 'pill': 'все уволены'})
                else:
                    no_assignees.append({'icon': t.get('icon', '📋'), 'name': t.get('name', ''), 'meta': '', 'pill': 'никого'})

                # долго в работе
                sd = t.get('start_date') or ''
                if sd:
                    try:
                        days_in_work = (today - datetime.strptime(sd, '%Y-%m-%d').date()).days
                    except Exception:
                        days_in_work = 0
                    if days_in_work >= 30:
                        long_running.append({'icon': t.get('icon', '📋'), 'name': t.get('name', ''), 'meta': 'старт ' + sd, 'pill': str(days_in_work) + ' дн'})

                # Сводка по отделам — часы за период
                dept_keys = set()
                if t.get('department_ids'):
                    for d in t['department_ids']:
                        dept_keys.add(d)
                else:
                    for a in assigns:
                        e = emps_by_id.get(a)
                        if e and e.get('department_id'):
                            dept_keys.add(e['department_id'])
                for dk in dept_keys:
                    dname = (depts_by_id.get(dk) or {}).get('name', dk)
                    r = by_dept.setdefault(dk, {'name': dname, 'tasks': 0, 'overdue': 0, 'hours': 0.0})
                    r['tasks'] += 1
                    if dl and dl < today_iso:
                        r['overdue'] += 1
                    for l in logs_by_task.get(tid, []):
                        ld = l.get('date') or ''
                        if d1_iso <= ld <= d2_iso:
                            try:
                                r['hours'] += float(l.get('hours') or 0)
                            except Exception:
                                pass

                # Сводка по командам — часы за период
                team_keys = set()
                for tm in data.get('teams', []):
                    tm_members = set(tm.get('member_ids') or [])
                    if tm.get('manager_id'):
                        tm_members.add(tm['manager_id'])
                    if set(assigns) & tm_members:
                        team_keys.add(tm['id'])
                for tk in team_keys:
                    tm = teams_by_id.get(tk) or {}
                    r = by_team.setdefault(tk, {'name': tm.get('name', tk), 'tasks': 0, 'overdue': 0, 'hours': 0.0})
                    r['tasks'] += 1
                    if dl and dl < today_iso:
                        r['overdue'] += 1
                    for l in logs_by_task.get(tid, []):
                        ld = l.get('date') or ''
                        if d1_iso <= ld <= d2_iso:
                            try:
                                r['hours'] += float(l.get('hours') or 0)
                            except Exception:
                                pass

        for k in by_dept.values():
            k['hours'] = round(k['hours'] * 4) / 4
        for k in by_team.values():
            k['hours'] = round(k['hours'] * 4) / 4

        overdue_emps_list = sorted([dict(v) for v in overdue_emps.values()], key=lambda x: (-x['overdue'], -x['max_days']))[:10]
        stale_emps_list = sorted([dict(v) for v in stale_emps.values()], key=lambda x: (-x['count'], -x['max_days']))[:10]

        # Динамика за выбранный период — все дни
        activity = []
        span = (d2 - d1).days
        max_days = 90  # ограничим отображение — если период длиннее, схлопнем по неделям
        if span <= max_days:
            cur = d1
            while cur <= d2:
                dk = cur.strftime('%Y-%m-%d')
                row = activity_map.get(dk, {'hours': 0.0, 'done': 0})
                activity.append({'date': dk, 'hours': round(row['hours'] * 4) / 4, 'done': row['done']})
                cur += timedelta(days=1)
        else:
            # агрегируем по неделям
            cur = d1
            while cur <= d2:
                week_end = min(cur + timedelta(days=6), d2)
                wh = 0.0
                wd_cnt = 0
                c2 = cur
                while c2 <= week_end:
                    dk = c2.strftime('%Y-%m-%d')
                    row = activity_map.get(dk)
                    if row:
                        wh += row['hours']
                        wd_cnt += row['done']
                    c2 += timedelta(days=1)
                activity.append({'date': cur.strftime('%Y-%m-%d'), 'hours': round(wh * 4) / 4, 'done': wd_cnt})
                cur += timedelta(days=7)

        overdue_days = [{'deadline': k, 'count': v['count'], 'days_past': v['days_past']} for k, v in overdue_days_counter.items()]
        overdue_days.sort(key=lambda x: -x['count'])

        # Health score
        total_active = statuses['active'] + statuses['paused'] + statuses['overdue']
        if total_active > 0:
            ov_rate = statuses['overdue'] / total_active
            stale_rate = len(stale) / total_active
            noasg_rate = len(no_assignees) / total_active
            orphan_rate = len(orphan) / total_active
            # Веса: 50 + 20 + 15 + 15 = 100 — максимум штрафа при 100% каждой проблемы
            penalty = ov_rate * 50 + stale_rate * 20 + noasg_rate * 15 + orphan_rate * 15
            # PATCH v1.0.5: было `100 - penalty * 100` — health всегда 0 при penalty>1
            health = max(0, min(100, round(100 - penalty)))
        else:
            health = 100

        return jsonify({
            'success': True,
            'from': d1_iso,
            'to': d2_iso,
            'preset': preset,
            'workdays': wd,
            'stats': {
                'tasks_total': total_active,
                'tasks_overdue': statuses['overdue'],
                'tasks_soon': len(deadline_soon),
                'tasks_stale': len(stale),
                'tasks_no_assignees': len(no_assignees),
                'tasks_orphan': len(orphan),
                'hours_period': round(hours_period * 4) / 4,
                'done_period': len(done_ids_period),
                'health_score': health,
            },
            'statuses': statuses,
            'activity': activity,
            'overdue_days': overdue_days,
            'by_dept': sorted(by_dept.values(), key=lambda x: -x['overdue']),
            'by_team': sorted(by_team.values(), key=lambda x: -x['overdue']),
            'overdue_emps': overdue_emps_list,
            'stale_emps': stale_emps_list,
            'overdue': overdue[:30],
            'stale': stale[:30],
            'deadline_soon': deadline_soon[:30],
            'orphan': orphan[:30],
            'no_assignees': no_assignees[:30],
            'long_running': long_running[:30],
        })

    def on_startup(**ctx):
        print('[pulse] готов — с выбором периода')

    hooks.on('on_startup', on_startup)


"""plugins/gantt.py — План проверок (Гант) для трекера."""

__version__ = '2.0'
__description__ = 'Диаграмма Ганта: sticky-заголовок, sticky-колонка задач, крупные полосы, светлая/тёмная тема'

from datetime import date, datetime, timedelta
from flask import request, jsonify, Response, redirect


# ============================================================
# JS — инжектор кнопки в шапку трекера
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
        id: 'gantt',
        icon: '📊',
        name: 'План проверок',
        url: '/plugins/gantt/',
        perm: 'plugin.gantt.use'
    });
}
register();
})();
'''


# ============================================================
# HTML-страница
# ============================================================
def _page_html():
    return r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>План проверок</title>
<script src="/static/plugin_theme.js"></script>
<script src="/static/plugin_mask.js"></script>
<style>
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    margin: 0;
    padding: 16px;
    font-size: 14px;
    background: var(--pg-bg, #0f0f0f);
    background-attachment: fixed;
    color: var(--pg-text, #e8e8e8);
    min-height: 100vh;
}
.wrap { max-width: 1800px; margin: 0 auto; display: flex; flex-direction: column; gap: 14px; }

/* Шапка */
.head {
    display: flex; flex-direction: column; gap: 10px;
    padding: 14px 18px;
    background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 14px;
}
.head-top { display: flex; align-items: center; gap: 14px; }
.head-filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.head h1 {
    margin: 0; font-size: 1.6rem; font-weight: 800;
    color: var(--pg-accent, #f5d76e);
}
.back {
    color: var(--pg-desc, #c8c8c8);
    text-decoration: none;
    padding: 6px 14px;
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 20px;
    font-size: 0.85rem;
    transition: all 0.15s;
}
.back:hover {
    background: var(--pg-accent-bg, rgba(245,215,110,0.14));
    color: var(--pg-accent, #f5d76e);
    border-color: var(--pg-accent, #f5d76e);
}
.head label { font-size: 0.75rem; color: var(--pg-meta, #a0a0a0); display: inline-flex; align-items: center; gap: 4px; }
.head input[type="date"],
.head select {
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid var(--pg-input-border, rgba(245,215,110,0.26));
    background: var(--pg-input-bg, #232323);
    color: var(--pg-text, #e8e8e8);
    font-family: inherit;
    font-size: 0.82rem;
}
.head input:focus, .head select:focus { outline: none; border-color: var(--pg-accent, #f5d76e); }
.head button.apply {
    padding: 6px 16px;
    border-radius: 8px;
    border: none;
    background: linear-gradient(135deg, var(--pg-accent, #f5d76e), var(--pg-accent-2, #e6a81a));
    color: #0a0a0a;
    font-weight: 800;
    cursor: pointer;
    font-family: inherit;
    font-size: 0.82rem;
    transition: transform 0.15s;
}
.head button.apply:hover { transform: scale(1.05); }

/* Основной контейнер диаграммы */
.gantt-box {
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 14px;
    background: var(--pg-card-bg, #1a1a1a);
    overflow: auto;
    max-height: 76vh;
    position: relative;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}

/* Внутренний layout */
.gantt-inner {
    display: inline-block;
    min-width: 100%;
}

/* Шапка (sticky top) */
.gg-header {
    display: flex;
    position: sticky;
    top: 0;
    z-index: 30;
    height: 58px;
    background: var(--pg-inner-bg, #232323);
    border-bottom: 2px solid var(--pg-card-border, rgba(245,215,110,0.22));
}
.gg-corner {
    flex: 0 0 320px;
    width: 320px;
    position: sticky;
    left: 0;
    z-index: 31;
    background: var(--pg-inner-bg, #232323);
    border-right: 2px solid var(--pg-card-border, rgba(245,215,110,0.22));
    display: flex;
    align-items: center;
    padding: 0 16px;
    font-weight: 800;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    color: var(--pg-meta, #a0a0a0);
}
.gg-days { display: flex; }
.gg-day {
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    border-right: 1px solid var(--pg-card-border-soft, rgba(245,215,110,0.12));
    padding: 6px 0;
    line-height: 1.15;
    transition: background 0.15s;
}
.gg-day.weekend { background: rgba(128,128,128,0.10); }
.gg-day.today {
    background: rgba(46,204,113,0.18);
    box-shadow: inset 0 -3px 0 #2ecc71;
}
.gg-dow {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--pg-meta, #a0a0a0);
}
.gg-date {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--pg-text, #e8e8e8);
}
.gg-day.weekend .gg-date { color: var(--pg-meta, #a0a0a0); }
.gg-day.today .gg-date { color: #2ecc71; font-weight: 800; }

/* Тело */
.gg-body { position: relative; }

/* Фон: выходные + сегодня */
.gg-bg {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 320px;
    pointer-events: none;
    z-index: 0;
}
.gg-bg-cell {
    position: absolute;
    top: 0;
    bottom: 0;
    background: rgba(128,128,128,0.07);
}
.gg-bg-cell.gg-bg-today { background: rgba(46,204,113,0.06); }
.gg-today-line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #2ecc71;
    box-shadow: 0 0 8px rgba(46,204,113,0.6);
    opacity: 0.8;
}

/* Строка задачи */
.gg-row {
    display: flex;
    height: 42px;
    border-bottom: 1px solid var(--pg-card-border-soft, rgba(245,215,110,0.12));
    position: relative;
    z-index: 1;
    transition: background 0.12s;
}
/* П.3: высота строки = 1.5× ширины столбца (день 44→66, неделя 92→138) */
.gg-mode-day .gg-row { height: 40px; }
.gg-mode-week .gg-row { height: 70px; }
/* П.7: число нагрузки в ячейке недели */
.gg-wk-load {
    position: absolute; top: 3px; right: 4px;
    font-size: 0.66rem; font-weight: 800;
    color: rgba(0,0,0,0.75);
    pointer-events: none;
}
.gg-row:hover { background: rgba(245,215,110,0.04); }

.gg-name {
    flex: 0 0 320px;
    width: 320px;
    position: sticky;
    left: 0;
    z-index: 5;
    background: var(--pg-card-bg, #1a1a1a);
    border-right: 2px solid var(--pg-card-border, rgba(245,215,110,0.22));
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 16px;
    transition: background 0.12s;
}
.gg-row:hover .gg-name { background: var(--pg-inner-bg, #232323); }
.gg-edit {
    margin-left: 6px; flex: 0 0 auto;
    opacity: 0; text-decoration: none;
    font-size: 0.9rem; cursor: pointer;
    transition: opacity 0.12s;
}
.gg-row:hover .gg-edit { opacity: 0.85; }
.gg-edit:hover { opacity: 1; }
.gg-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 6px currentColor;
}
.gg-dot-active { background: #5dade2; color: #5dade2; }
.gg-dot-done { background: #58d68d; color: #58d68d; }
.gg-dot-paused { background: #f7dc6f; color: #f7dc6f; }
.gg-dot-archived { background: #aab7b8; color: #aab7b8; }
.gg-dot-overdue { background: #ec7063; color: #ec7063; }
.gg-dot-planned { background: #95a5a6; color: #95a5a6; }
.gg-ico { font-size: 1rem; flex-shrink: 0; }
.gg-task-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--pg-text, #e8e8e8);
}

.gg-track {
    position: relative;
    flex: 0 0 auto;
    height: 70px;
}
.gg-stage-seg {
    position: absolute;
    top: 0;
    height: 100%;
    opacity: 0.92;
    border-right: 1px solid rgba(0,0,0,0.25);
}
.gg-stage-seg:last-child { border-right: none; }
.gg-stage-legend {
    display: flex; flex-wrap: wrap; gap: 10px 16px;
    padding: 10px 14px; margin-top: 4px;
    background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 12px; font-size: 0.82rem;
}
.gg-stage-legend .lg-item { display: inline-flex; align-items: center; gap: 6px; }
.gg-stage-legend .lg-chip { width: 13px; height: 13px; border-radius: 3px; display: inline-block; }
.gg-bar {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 24px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    padding: 0 12px;
    color: #fff;
    font-weight: 700;
    overflow: hidden;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.3),
        0 2px 8px rgba(0,0,0,0.35);
    cursor: pointer;
    z-index: 2;
    transition: filter 0.15s, box-shadow 0.15s;
}
.gg-bar:hover {
    filter: brightness(1.15);
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.4),
        0 6px 16px rgba(0,0,0,0.45);
}
.gg-bar-label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 0.72rem;
    text-shadow: 0 1px 2px rgba(0,0,0,0.35);
}
.gg-bar-active { background: linear-gradient(180deg, #6dc2f0, #2874a6); }
.gg-bar-done { background: linear-gradient(180deg, #7be0a0, #239b56); }
.gg-bar-paused { background: linear-gradient(180deg, #fadc8a, #d4ac0d); color: #221a00; }
.gg-bar-paused .gg-bar-label { text-shadow: none; }
.gg-bar-archived { background: linear-gradient(180deg, #bcc7c8, #7b8a8b); }
.gg-bar-overdue {
    background: linear-gradient(180deg, #f08b80, #b03a2e);
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.3),
        0 0 14px rgba(231,76,60,0.4),
        0 2px 8px rgba(0,0,0,0.35);
}
.gg-bar-planned { background: linear-gradient(180deg, #b0bec5, #607d8b); }

/* Пустое состояние и загрузка */
.empty, .loading {
    text-align: center;
    padding: 60px 20px;
    color: var(--pg-meta, #a0a0a0);
    font-style: italic;
    font-size: 0.9rem;
}

/* Легенда */
.legend {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    padding: 12px 16px;
    font-size: 0.78rem;
    color: var(--pg-meta, #a0a0a0);
    border-top: 1px solid var(--pg-card-border-soft, rgba(245,215,110,0.12));
    background: var(--pg-card-bg, #1a1a1a);
}
.legend .it { display: flex; align-items: center; gap: 6px; }
.legend .sw {
    width: 16px; height: 10px; border-radius: 3px;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.25);
}
.legend .sw.active { background: linear-gradient(180deg, #6dc2f0, #2874a6); }
.legend .sw.done { background: linear-gradient(180deg, #7be0a0, #239b56); }
.legend .sw.paused { background: linear-gradient(180deg, #fadc8a, #d4ac0d); }
.legend .sw.overdue { background: linear-gradient(180deg, #f08b80, #b03a2e); }
.legend .sw.archived { background: linear-gradient(180deg, #bcc7c8, #7b8a8b); }

/* Светлая тема — override поверх plugin_theme.js */
body.trk-theme-light .gantt-box { background: #ffffff; border-color: rgba(0,0,0,0.14); box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
body.trk-theme-light .gg-header { background: #eceff1; border-bottom-color: rgba(0,0,0,0.14); }
body.trk-theme-light .gg-corner { background: #eceff1; border-right-color: rgba(0,0,0,0.14); color: #546e7a; }
body.trk-theme-light .gg-day { border-right-color: rgba(0,0,0,0.08); }
body.trk-theme-light .gg-day.weekend { background: rgba(96,125,139,0.12); }
body.trk-theme-light .gg-day.today { background: rgba(46,125,50,0.14); box-shadow: inset 0 -3px 0 #2e7d32; }
body.trk-theme-light .gg-date { color: #212121; }
body.trk-theme-light .gg-day.weekend .gg-date { color: #546e7a; }
body.trk-theme-light .gg-day.today .gg-date { color: #1b5e20; }
body.trk-theme-light .gg-bg-cell { background: rgba(96,125,139,0.08); }
body.trk-theme-light .gg-bg-cell.gg-bg-today { background: rgba(46,125,50,0.06); }
body.trk-theme-light .gg-today-line { background: #2e7d32; box-shadow: 0 0 8px rgba(46,125,50,0.5); }
body.trk-theme-light .gg-row { border-bottom-color: rgba(0,0,0,0.08); }
body.trk-theme-light .gg-row:hover { background: rgba(0,137,123,0.04); }
body.trk-theme-light .gg-name { background: #ffffff; border-right-color: rgba(0,0,0,0.14); }
body.trk-theme-light .gg-row:hover .gg-name { background: #f7f9fa; }
body.trk-theme-light .gg-task-name { color: #212121; }
body.trk-theme-light .gg-bar-active { background: linear-gradient(180deg, #4fc3f7, #1976d2); }
body.trk-theme-light .gg-bar-done { background: linear-gradient(180deg, #66bb6a, #2e7d32); }
body.trk-theme-light .gg-bar-paused { background: linear-gradient(180deg, #ffd54f, #f9a825); color: #3e2723; }
body.trk-theme-light .gg-bar-overdue { background: linear-gradient(180deg, #ef5350, #c62828); }
body.trk-theme-light .gg-bar-planned { background: linear-gradient(180deg, #b0bec5, #546e7a); }
body.trk-theme-light .gg-bar-archived { background: linear-gradient(180deg, #cfd8dc, #78909c); }
body.trk-theme-light .legend { background: #ffffff; border-top-color: rgba(0,0,0,0.08); }

/* --- Слайдер прокрутки --- */
.gg-slider-wrap {
    padding: 4px 18px 10px;
    background: var(--pg-card-bg, #1a1a1a);
    border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22));
    border-radius: 14px;
}
.gg-slider-wrap input[type="range"] {
    width: 100%;
    accent-color: var(--pg-accent, #f5d76e);
    cursor: pointer;
}

/* --- Недельный режим: двухслойная шапка --- */
.gg-wk-head { display: flex; flex-direction: column; }
.gg-wk-months, .gg-wk-weeks { display: flex; }
.gg-wk-month {
    flex: 0 0 auto;
    display: flex; align-items: center; justify-content: center;
    height: 26px;
    font-size: 0.72rem; font-weight: 800; text-transform: capitalize;
    letter-spacing: 0.4px;
    color: #0a0a0a;
    border-right: 2px solid rgba(0,0,0,0.25);
}
.gg-wk-week {
    flex: 0 0 auto;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 44px;
    font-size: 0.74rem; font-weight: 700; line-height: 1.05;
    text-align: center;
    color: var(--pg-text, #e8e8e8);
    border-right: 1px solid var(--pg-card-border-soft, rgba(245,215,110,0.12));
}
.gg-wk-week.today { box-shadow: inset 0 -3px 0 #2ecc71; color: #2ecc71; }
.gg-wk-cell {
    position: absolute; top: 4px; bottom: 4px;
    border-radius: 4px;
    border-right: 1px solid rgba(0,0,0,0.18);
    opacity: 0.95;
    cursor: default;
}
.gg-wk-cell .gg-wk-load-c {
    position: absolute; left: 0; right: 0; bottom: 4px;
    text-align: center;
    font-size: 0.72rem; font-weight: 800;
    color: rgba(0,0,0,0.78);
}
.gg-wk-cell.empty { background: transparent !important; border: none; }
body.trk-theme-light .gg-slider-wrap { background:#fff; }
body.trk-theme-light .gg-wk-week { color:#212121; }

/* --- Вторая таблица: нагрузка по тер банкам --- */
.banks-title {
    font-size: 1.1rem; font-weight: 800;
    color: var(--pg-accent, #f5d76e);
    padding: 2px 4px;
}
.gg-bank-cell {
    position: absolute; top: 6px; bottom: 6px;
    border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.82rem; font-weight: 800;
    color: var(--pg-text, #e8e8e8);
    background: var(--pg-input-bg, #232323);
    border: 1px solid var(--pg-card-border-soft, rgba(245,215,110,0.18));
}
/* Тепловая заливка по величине нагрузки */
.gg-bank-cell.lvl0 { background: transparent; border-color: transparent; color: var(--pg-meta,#888); }
.gg-bank-cell.lvl1 { background: rgba(93,173,226,0.25); }
.gg-bank-cell.lvl2 { background: rgba(88,214,141,0.30); }
.gg-bank-cell.lvl3 { background: rgba(244,208,63,0.38); color:#2a2300; }
.gg-bank-cell.lvl4 { background: rgba(235,152,78,0.45); color:#2a1600; }
.gg-bank-cell.lvl5 { background: rgba(236,112,99,0.55); color:#2a0a06; }
.gg-bank-total {
    font-weight: 800; color: var(--pg-accent, #f5d76e);
}
body.trk-theme-light .banks-title { color:#1b5e20; }
body.trk-theme-light .gg-bank-cell { color:#212121; background:#f1f3f4; border-color:rgba(0,0,0,0.1); }
body.trk-theme-light .gg-bank-cell.lvl0 { background:transparent; border-color:transparent; color:#999; }

@media (max-width: 700px) {
    .gg-corner, .gg-name { flex-basis: 220px; width: 220px; }
    .gg-bg { left: 220px; }
    .head { padding: 12px 14px; }
    .head h1 { font-size: 1.05rem; }
}
</style>
</head>
<body>
<div class="wrap">
    <div class="head">
        <div class="head-top">
            <a class="back" href="/">← К трекеру</a>
            <h1>📅 План проверок</h1>
        </div>
        <div class="head-filters">
            <select id="fType">
                <option value="">Все типы проверок</option>
                <option value="розничная">Розничная</option>
                <option value="корпоративная">Корпоративная</option>
            </select>
            <select id="fPocket"><option value="">Все карманы</option></select>
            <select id="fDept"><option value="">Все тер банки</option></select>
            <select id="fTeam"><option value="">Все команды</option></select>
            <label>С <input type="date" id="fFrom"></label>
            <label>По <input type="date" id="fTo"></label>
            <select id="fStatus">
                <option value="">Все статусы</option>
                <option value="active">Активные</option>
                <option value="paused">Приостановленные</option>
                <option value="done">Выполненные</option>
                <option value="archived">Архив</option>
            </select>
            <label>Вид <select id="fView">
                <option value="week">Недели</option>
                <option value="day">Дни</option>
            </select></label>
            <button class="apply" id="fApply">✓ Показать</button>
        </div>
    </div>
    <div class="gantt-box" id="ganttBox">
        <div class="loading">Загрузка…</div>
    </div>
    <div class="gg-slider-wrap" id="ggSliderWrap" style="display:none;">
        <input type="range" id="ggSlider" min="0" max="1000" value="0" step="1">
    </div>
    <div class="legend">
        <div class="it"><span class="sw active"></span>В работе</div>
        <div class="it"><span class="sw done"></span>Готово</div>
        <div class="it"><span class="sw paused"></span>Приостановлено</div>
        <div class="it"><span class="sw overdue"></span>Просрочено</div>
        <div class="it"><span class="sw archived"></span>Архив</div>
        <div class="it" style="margin-left:auto;font-style:italic;">Сегодняшний день выделен зелёным</div>
    </div>
    <div class="banks-title" id="banksTitle" style="display:none;">Нагрузка по тер банкам</div>
    <div class="gantt-box" id="banksBox" style="display:none;"></div>
</div>

<script>
(function(){
'use strict';

var DAY_W = 44;
var ROW_H = 42;
var NAME_W = 320;
var DOW = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
}
function fmtD(iso) {
    if (!iso) return '';
    var p = iso.split('-');
    return p[2] + '.' + p[1];
}
function isoAddDays(iso, n) {
    // PATCH v1.0.5: не используем toISOString (UTC-сдвиг на день)
    var p = iso.split('-');
    var d = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10));
    d.setDate(d.getDate() + n);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + dd;
}

/* Инициализация диапазона — полгода от понедельника текущей недели */
function initDates() {
    var t = new Date();
    var wd = t.getDay();
    var diff = (wd === 0) ? -6 : (1 - wd);
    var mon = new Date(t.getTime() + diff * 86400000);
    var end = new Date(mon.getFullYear(), mon.getMonth() + 6, mon.getDate());
    // PATCH v1.0.5: toISOString даёт UTC-сдвиг; пишем вручную
    var iso = function(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dd = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + dd;
    };
    document.getElementById('fFrom').value = iso(mon);
    document.getElementById('fTo').value = iso(end);
}

var WEEK_W = 46;         /* ширина недельной колонки (уже, подпись в 2 строки) */
var MONTH_COLORS = ['#3b5ba5','#2e8b7a','#a5683b','#6a4ba5','#a53b5b','#5b8b2e','#8b7a2e','#2e6aa5','#a53b8b','#4ba58b','#a5a53b','#7a2ea5'];
var MONTH_NAMES = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];

/* ISO-понедельник недели, в которую попадает дата iso */
function mondayOf(iso) {
    var p = iso.split('-');
    var d = new Date(parseInt(p[0],10), parseInt(p[1],10)-1, parseInt(p[2],10));
    var wd = d.getDay();
    var diff = (wd === 0) ? -6 : (1 - wd);
    d.setDate(d.getDate() + diff);
    var y=d.getFullYear(), m=String(d.getMonth()+1).padStart(2,'0'), dd=String(d.getDate()).padStart(2,'0');
    return y+'-'+m+'-'+dd;
}
/* Список недель (понедельников) перекрывающих диапазон days[] */
function buildWeeks(days) {
    if (!days.length) return [];
    var first = mondayOf(days[0]);
    var lastMon = mondayOf(days[days.length-1]);
    var weeks = [];
    var cur = first;
    var guard = 0;
    while (cur <= lastMon && guard < 520) {
        var sun = isoAddDays(cur, 6);
        weeks.push({ mon: cur, sun: sun });
        cur = isoAddDays(cur, 7);
        guard++;
    }
    return weeks;
}
/* Этап, активный в понедельник недели: stage.start <= mon <= stage.end */
function stageAtMonday(stages, mon) {
    if (!stages) return null;
    for (var i = 0; i < stages.length; i++) {
        var st = stages[i];
        if (!st.start) continue;
        var end = st.end || st.start;
        if (st.start <= mon && mon <= end) return st;
    }
    return null;
}

function loadMeta() {
    fetch('/api/plugins/gantt/meta', {credentials: 'same-origin'})
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (!d.success) return;
            var ds = document.getElementById('fDept');
            (d.departments || []).forEach(function(x) {
                ds.insertAdjacentHTML('beforeend', '<option value="' + esc(x.id) + '">' + esc(x.name) + '</option>');
            });
            var ts = document.getElementById('fTeam');
            (d.teams || []).forEach(function(x) {
                ts.insertAdjacentHTML('beforeend', '<option value="' + esc(x.id) + '">' + esc(x.name) + '</option>');
            });
        });
}

function fillPocketFilter(pockets) {
    var sel = document.getElementById('fPocket');
    if (!sel) return;
    var cur = sel.value;
    var html = '<option value="">Все карманы</option>';
    (pockets || []).forEach(function(p) {
        if (!p) return;
        html += '<option value="' + esc(p) + '">' + esc(p) + '</option>';
    });
    sel.innerHTML = html;
    // сохранить выбор, если он ещё есть в списке
    if (cur && (pockets || []).indexOf(cur) !== -1) sel.value = cur;
}

function load() {
    var box = document.getElementById('ganttBox');
    box.innerHTML = '<div class="loading">Загрузка…</div>';
    var q = '?from=' + encodeURIComponent(document.getElementById('fFrom').value) +
            '&to=' + encodeURIComponent(document.getElementById('fTo').value);
    var dep = document.getElementById('fDept').value;
    if (dep) q += '&department=' + encodeURIComponent(dep);
    var team = document.getElementById('fTeam').value;
    if (team) q += '&team=' + encodeURIComponent(team);
    var sts = document.getElementById('fStatus').value;
    if (sts) q += '&status=' + encodeURIComponent(sts);
    var fty = document.getElementById('fType').value;
    if (fty) q += '&task_type=' + encodeURIComponent(fty);
    var fpk = document.getElementById('fPocket').value;
    if (fpk) q += '&pocket=' + encodeURIComponent(fpk);
    fetch('/api/plugins/gantt/data' + q, {credentials: 'same-origin'})
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (!d || !d.success) { box.innerHTML = '<div class="empty">Ошибка загрузки</div>'; return; }
            fillPocketFilter(d.pockets || []);
            render(d);
        })
        .catch(function() {
            box.innerHTML = '<div class="empty">Ошибка соединения</div>';
        });
}

function render(d) {
    var view = document.getElementById('fView').value;
    if (view === 'week') { renderWeek(d); }
    else {
        // Вторая таблица (нагрузка по тер банкам) только в недельном режиме
        document.getElementById('banksTitle').style.display = 'none';
        document.getElementById('banksBox').style.display = 'none';
        renderDay(d);
    }
    setupSlider();
}

function setupSlider() {
    var box = document.getElementById('ganttBox');
    var wrap = document.getElementById('ggSliderWrap');
    var sl = document.getElementById('ggSlider');
    var banks = document.getElementById('banksBox');
    var maxScroll = box.scrollWidth - box.clientWidth;
    if (maxScroll <= 2) { wrap.style.display = 'none'; }
    else {
        wrap.style.display = 'block';
        sl.max = String(Math.round(maxScroll));
        sl.value = String(Math.round(box.scrollLeft));
        sl.oninput = function() {
            box.scrollLeft = parseInt(sl.value, 10);
            if (banks) banks.scrollLeft = box.scrollLeft;
        };
    }
    box.onscroll = function() {
        var ms = box.scrollWidth - box.clientWidth;
        sl.max = String(Math.round(ms));
        sl.value = String(Math.round(box.scrollLeft));
        if (banks && banks.style.display !== 'none') banks.scrollLeft = box.scrollLeft;
    };
    if (banks) {
        banks.onscroll = function() { box.scrollLeft = banks.scrollLeft; };
    }
}

function renderDay(d) {
    var box = document.getElementById('ganttBox');
    var tasks = d.tasks || [];
    var days = d.days || [];
    var today = d.today || '';

    if (!tasks.length) {
        box.innerHTML = '<div class="empty">Нет задач за выбранный период</div>';
        return;
    }
    if (!days.length) {
        box.innerHTML = '<div class="empty">Пустой диапазон дат</div>';
        return;
    }

    var trackW = days.length * DAY_W;
    var html = '<div class="gantt-inner gg-mode-day">';

    /* --- Шапка --- */
    html += '<div class="gg-header">';
    html += '<div class="gg-corner">Задача</div>';
    html += '<div class="gg-days">';
    days.forEach(function(dk) {
        var dt = new Date(dk + 'T00:00:00');
        var wd = dt.getDay();
        var cls = 'gg-day';
        if (wd === 0 || wd === 6) cls += ' weekend';
        if (dk === today) cls += ' today';
        html += '<div class="' + cls + '" style="width:' + DAY_W + 'px">';
        html += '<span class="gg-dow">' + DOW[wd] + '</span>';
        html += '<span class="gg-date">' + fmtD(dk) + '</span>';
        html += '</div>';
    });
    html += '</div></div>';

    /* --- Тело --- */
    html += '<div class="gg-body">';

    /* Фон — выходные и сегодня */
    html += '<div class="gg-bg" style="width:' + trackW + 'px">';
    days.forEach(function(dk, i) {
        var dt = new Date(dk + 'T00:00:00');
        var wd = dt.getDay();
        if (wd === 0 || wd === 6) {
            html += '<div class="gg-bg-cell" style="left:' + (i * DAY_W) + 'px;width:' + DAY_W + 'px"></div>';
        }
        if (dk === today) {
            html += '<div class="gg-bg-cell gg-bg-today" style="left:' + (i * DAY_W) + 'px;width:' + DAY_W + 'px"></div>';
            html += '<div class="gg-today-line" style="left:' + (i * DAY_W + DAY_W - 1) + 'px"></div>';
        }
    });
    html += '</div>';

    /* Этапы задачи (зеркало db.py TASK_STAGE_*) */
    var STAGE_ORDER = ['подготовка','проверка_нжя','проверка_соглЦА','ос_проф','реализация_возражения','реализация_согласования','запас','оценка_тб'];
    var STAGE_COLORS = {'подготовка':'#5dade2','проверка_нжя':'#48c9b0','проверка_соглЦА':'#58d68d','ос_проф':'#f4d03f','реализация_возражения':'#eb984e','реализация_согласования':'#e59866','запас':'#af7ac5','оценка_тб':'#ec7063'};
    var STAGE_LABELS = {'подготовка':'Подготовка','проверка_нжя':'Проверка НЖЯ','проверка_соглЦА':'Проверка согл. ЦА','ос_проф':'ОС проф.','реализация_возражения':'Реализация возражения','реализация_согласования':'Реализация согласования','запас':'Запас','оценка_тб':'Оценка ТБ'};
    function dayIndex(ds) {
        if (!ds) return -1;
        for (var i = 0; i < days.length; i++) { if (days[i] >= ds) return i; }
        return -1;
    }

    /* Строки задач */
    tasks.forEach(function(t) {
        var cls = t.overdue ? 'overdue' : (t.status || 'active');
        var sIdx = -1, eIdx = -1;
        for (var i = 0; i < days.length; i++) {
            if (sIdx < 0 && days[i] >= t.start_date) sIdx = i;
            if (days[i] <= t.deadline) eIdx = i;
        }
        if (sIdx < 0) sIdx = 0;
        if (eIdx < 0) eIdx = days.length - 1;
        if (eIdx < sIdx) eIdx = sIdx;

        var barLeft = sIdx * DAY_W + 3;
        var barWidth = (eIdx - sIdx + 1) * DAY_W - 6;
        if (barWidth < 16) barWidth = 16;

        var title = t.name + ' · ' + t.start_date + ' — ' + t.deadline +
                    (t.overdue ? ' · ПРОСРОЧЕНО' : '');

        html += '<div class="gg-row">';
        html +=   '<div class="gg-name">';
        html +=     '<span class="gg-dot gg-dot-' + cls + '"></span>';
        html +=     '<span class="gg-ico">' + esc(t.icon || '📋') + '</span>';
        html +=     '<span class="gg-task-name" title="' + esc(t.name) + '">' + esc(t.name) + '</span>';
        html +=     '<a class="gg-edit" href="/?open_task=' + encodeURIComponent(t.id) + '" title="Редактировать проверку" onclick="event.stopPropagation()">✏️</a>';
        html +=   '</div>';
        html +=   '<div class="gg-track" style="width:' + trackW + 'px">';
        html +=     '<div class="gg-bar gg-bar-' + cls + '" style="left:' + barLeft + 'px;width:' + barWidth + 'px" title="' + esc(title) + '">';
        // Цветные сегменты этапов внутри бара
        if (t.stages && t.stages.length) {
            t.stages.forEach(function(st) {
                if (!st.start) return;
                var ssi = dayIndex(st.start);
                if (ssi < 0) return;
                var sei = st.end ? dayIndex(st.end) : eIdx;
                if (sei < 0) sei = eIdx;
                if (sei < ssi) sei = ssi;
                var segLeft = (ssi - sIdx) * DAY_W;
                var segWidth = (sei - ssi + 1) * DAY_W;
                if (segLeft < 0) { segWidth += segLeft; segLeft = 0; }
                if (segWidth <= 0) return;
                var col = STAGE_COLORS[st.key] || '#888';
                var stTitle = (STAGE_LABELS[st.key] || st.key) + ': ' + st.start + (st.end ? ' — ' + st.end : '');
                html += '<div class="gg-stage-seg" style="left:' + segLeft + 'px;width:' + segWidth + 'px;background:' + col + '" title="' + esc(stTitle) + '"></div>';
            });
        }
        if (barWidth > 80) {
            html +=     '<span class="gg-bar-label" style="position:relative;z-index:2">' + esc(t.name) + '</span>';
        }
        html +=     '</div>';
        html +=   '</div>';
        html += '</div>';
    });

    html += '</div>';  /* gg-body */
    html += '</div>';  /* gantt-inner */

    /* Легенда этапов */
    html += '<div class="gg-stage-legend">';
    STAGE_ORDER.forEach(function(k) {
        html += '<span class="lg-item"><span class="lg-chip" style="background:' + STAGE_COLORS[k] + '"></span>' + STAGE_LABELS[k] + '</span>';
    });
    html += '</div>';

    box.innerHTML = html;
}

function renderWeek(d) {
    var box = document.getElementById('ganttBox');
    var tasks = d.tasks || [];
    var days = d.days || [];
    var today = d.today || '';

    if (!tasks.length) { box.innerHTML = '<div class="empty">Нет задач за выбранный период</div>'; return; }
    if (!days.length) { box.innerHTML = '<div class="empty">Пустой диапазон дат</div>'; return; }

    var STAGE_ORDER = ['подготовка','проверка_нжя','проверка_соглЦА','ос_проф','реализация_возражения','реализация_согласования','запас','оценка_тб'];
    var STAGE_COLORS = {'подготовка':'#5dade2','проверка_нжя':'#48c9b0','проверка_соглЦА':'#58d68d','ос_проф':'#f4d03f','реализация_возражения':'#eb984e','реализация_согласования':'#e59866','запас':'#af7ac5','оценка_тб':'#ec7063'};
    var STAGE_LABELS = {'подготовка':'Подготовка','проверка_нжя':'Проверка НЖЯ','проверка_соглЦА':'Проверка согл. ЦА','ос_проф':'ОС проф.','реализация_возражения':'Реализация возражения','реализация_согласования':'Реализация согласования','запас':'Запас','оценка_тб':'Оценка ТБ'};

    var weeks = buildWeeks(days);
    if (!weeks.length) { box.innerHTML = '<div class="empty">Пустой диапазон дат</div>'; return; }
    var todayMon = today ? mondayOf(today) : '';
    var trackW = weeks.length * WEEK_W;

    /* Группировка недель по месяцам (по месяцу понедельника) для верхнего слоя */
    var monthSpans = [];
    weeks.forEach(function(w) {
        var mi = parseInt(w.mon.split('-')[1], 10) - 1;
        var yr = w.mon.split('-')[0];
        var key = yr + '-' + mi;
        var last = monthSpans[monthSpans.length - 1];
        if (last && last.key === key) { last.count++; }
        else { monthSpans.push({ key: key, mi: mi, yr: yr, count: 1 }); }
    });

    var html = '<div class="gantt-inner gg-mode-week">';

    /* Шапка: двухслойная */
    html += '<div class="gg-header" style="height:70px;">';
    html += '<div class="gg-corner">Задача</div>';
    html += '<div class="gg-wk-head">';
    /* слой месяцев */
    html += '<div class="gg-wk-months">';
    monthSpans.forEach(function(m, idx) {
        var col = MONTH_COLORS[m.mi % MONTH_COLORS.length];
        html += '<div class="gg-wk-month" style="width:' + (m.count * WEEK_W) + 'px;background:' + col + '">' + MONTH_NAMES[m.mi] + '</div>';
    });
    html += '</div>';
    /* слой недель */
    html += '<div class="gg-wk-weeks">';
    weeks.forEach(function(w) {
        var cls = 'gg-wk-week' + (w.mon === todayMon ? ' today' : '');
        html += '<div class="' + cls + '" style="width:' + WEEK_W + 'px" title="' + w.mon + ' — ' + w.sun + '">' + fmtD(w.mon) + '–<br>' + fmtD(w.sun) + '</div>';
    });
    html += '</div>';
    html += '</div></div>';

    /* Тело */
    html += '<div class="gg-body">';
    /* фон недели "сегодня" */
    html += '<div class="gg-bg" style="width:' + trackW + 'px">';
    weeks.forEach(function(w, i) {
        if (w.mon === todayMon) {
            html += '<div class="gg-bg-cell gg-bg-today" style="left:' + (i * WEEK_W) + 'px;width:' + WEEK_W + 'px"></div>';
        }
    });
    html += '</div>';

    tasks.forEach(function(t) {
        html += '<div class="gg-row">';
        html +=   '<div class="gg-name">';
        html +=     '<span class="gg-dot gg-dot-' + (t.overdue ? 'overdue' : (t.status||'active')) + '"></span>';
        html +=     '<span class="gg-ico">' + esc(t.icon || '📋') + '</span>';
        html +=     '<span class="gg-task-name" title="' + esc(t.name) + '">' + esc(t.name) + '</span>';
        html +=     '<a class="gg-edit" href="/?open_task=' + encodeURIComponent(t.id) + '" title="Редактировать проверку" onclick="event.stopPropagation()">✏️</a>';
        html +=   '</div>';
        html +=   '<div class="gg-track" style="width:' + trackW + 'px">';
        /* По каждой неделе — цвет этапа, активного в понедельник */
        weeks.forEach(function(w, i) {
            var st = stageAtMonday(t.stages, w.mon);
            if (!st) return;
            var col = STAGE_COLORS[st.key] || '#888';
            var wt = (st.weight != null ? st.weight : 1);
            var wtTxt = (Math.round(wt * 100) / 100).toString();
            var ttl = (STAGE_LABELS[st.key] || st.key) + ' · неделя ' + fmtD(w.mon) + '–' + fmtD(w.sun) + ' · нагрузка ' + wtTxt;
            html += '<div class="gg-wk-cell" style="left:' + (i * WEEK_W + 2) + 'px;width:' + (WEEK_W - 4) + 'px;background:' + col + '" title="' + esc(ttl) + '">' +
                    '<span class="gg-wk-load-c">' + wtTxt + '</span></div>';
        });
        html +=   '</div>';
        html += '</div>';
    });

    html += '</div>';  /* gg-body */
    html += '</div>';  /* gantt-inner */

    /* Легенда этапов */
    html += '<div class="gg-stage-legend">';
    STAGE_ORDER.forEach(function(k) {
        html += '<span class="lg-item"><span class="lg-chip" style="background:' + STAGE_COLORS[k] + '"></span>' + STAGE_LABELS[k] + '</span>';
    });
    html += '</div>';

    box.innerHTML = html;

    /* П.6 обновления: вторая таблица — нагрузка по тер банкам */
    renderBanks(d, weeks, STAGE_COLORS, STAGE_LABELS);
}

/* Строит таблицу "Нагрузка по тер банкам": строки — банки,
   столбцы — те же недели; значение = сумма весов этапов всех задач
   банка, активных в понедельник недели. Фильтры уже применены на бэке. */
function renderBanks(d, weeks, STAGE_COLORS, STAGE_LABELS) {
    var titleEl = document.getElementById('banksTitle');
    var box = document.getElementById('banksBox');
    var banks = d.banks || [];
    var tasks = d.tasks || [];

    if (!banks.length || !weeks.length) {
        titleEl.style.display = 'none';
        box.style.display = 'none';
        return;
    }
    titleEl.style.display = 'block';
    box.style.display = 'block';

    var todayMon = d.today ? mondayOf(d.today) : '';
    var trackW = weeks.length * WEEK_W;

    /* Матрица: load[bankId][weekIdx] = сумма весов */
    var load = {};
    banks.forEach(function(b) {
        load[b.id] = [];
        for (var i = 0; i < weeks.length; i++) load[b.id].push(0);
    });
    tasks.forEach(function(t) {
        var dids = t.dept_ids || [];
        if (!dids.length) return;
        weeks.forEach(function(w, i) {
            var st = stageAtMonday(t.stages, w.mon);
            if (!st) return;
            var wt = (st.weight != null ? st.weight : 1);
            dids.forEach(function(did) {
                if (load[did]) load[did][i] += wt;
            });
        });
    });

    /* Группировка недель по месяцам (как в основной таблице) */
    var monthSpans = [];
    weeks.forEach(function(w) {
        var mi = parseInt(w.mon.split('-')[1], 10) - 1;
        var yr = w.mon.split('-')[0];
        var key = yr + '-' + mi;
        var last = monthSpans[monthSpans.length - 1];
        if (last && last.key === key) { last.count++; }
        else { monthSpans.push({ key: key, mi: mi, yr: yr, count: 1 }); }
    });

    var html = '<div class="gantt-inner gg-mode-week">';
    /* Шапка — те же недели */
    html += '<div class="gg-header" style="height:70px;">';
    html += '<div class="gg-corner">Тер банк</div>';
    html += '<div class="gg-wk-head">';
    html += '<div class="gg-wk-months">';
    monthSpans.forEach(function(m) {
        var col = MONTH_COLORS[m.mi % MONTH_COLORS.length];
        html += '<div class="gg-wk-month" style="width:' + (m.count * WEEK_W) + 'px;background:' + col + '">' + MONTH_NAMES[m.mi] + '</div>';
    });
    html += '</div>';
    html += '<div class="gg-wk-weeks">';
    weeks.forEach(function(w) {
        var cls = 'gg-wk-week' + (w.mon === todayMon ? ' today' : '');
        html += '<div class="' + cls + '" style="width:' + WEEK_W + 'px" title="' + w.mon + ' — ' + w.sun + '">' + fmtD(w.mon) + '–<br>' + fmtD(w.sun) + '</div>';
    });
    html += '</div></div></div>';

    /* Тело — строки банков */
    html += '<div class="gg-body">';
    banks.forEach(function(b) {
        html += '<div class="gg-row">';
        html +=   '<div class="gg-name">';
        html +=     '<span class="gg-ico">🏦</span>';
        html +=     '<span class="gg-task-name" title="' + esc(b.name) + '">' + esc(b.name) + '</span>';
        html +=   '</div>';
        html +=   '<div class="gg-track" style="width:' + trackW + 'px">';
        weeks.forEach(function(w, i) {
            var v = load[b.id][i];
            var txt = (Math.round(v * 100) / 100).toString();
            var lvl = 0;
            if (v > 0 && v <= 1) lvl = 1;
            else if (v <= 2) lvl = 2;
            else if (v <= 3) lvl = 3;
            else if (v <= 4) lvl = 4;
            else if (v > 4) lvl = 5;
            html += '<div class="gg-bank-cell lvl' + lvl + '" style="left:' + (i * WEEK_W + 2) + 'px;width:' + (WEEK_W - 4) + 'px" title="' + esc(b.name) + ' · неделя ' + fmtD(w.mon) + '–' + fmtD(w.sun) + ' · нагрузка ' + txt + '">' + (v > 0 ? txt : '') + '</div>';
        });
        html +=   '</div>';
        html += '</div>';
    });
    html += '</div></div>';

    box.innerHTML = html;
}

/* --- Запуск --- */
document.getElementById('fApply').addEventListener('click', load);
document.getElementById('fDept').addEventListener('change', load);
document.getElementById('fTeam').addEventListener('change', load);
document.getElementById('fStatus').addEventListener('change', load);
document.getElementById('fView').addEventListener('change', load);
document.getElementById('fType').addEventListener('change', load);
document.getElementById('fPocket').addEventListener('change', load);
initDates();
loadMeta();
load();

})();
</script>
</body>
</html>'''


# ============================================================
# Регистрация в приложении
# ============================================================
def register(app, db, hooks):
    print('[gantt] v' + __version__ + ' · ' + __description__)

    @app.route('/plugins-assets/gantt.js', methods=['GET'])
    def _g_js():
        return app.response_class(_JS, mimetype='application/javascript')

    @app.route('/plugins/gantt/', methods=['GET'])
    def _g_page():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return redirect('/login')
            if not user_has(db, u, 'plugin.gantt.use'):
                return redirect('/')
        except Exception:
            return redirect('/login')
        return Response(_page_html(), mimetype='text/html')

    @app.route('/api/plugins/gantt/meta', methods=['GET'])
    def _g_meta():
        # PATCH v1.0.5: добавлена проверка авторизации
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return jsonify({'success': False, 'error': 'auth'}), 401
            if not user_has(db, u, 'plugin.gantt.use'):
                return jsonify({'success': False, 'error': 'forbidden'}), 403
        except Exception:
            return jsonify({'success': False, 'error': 'auth'}), 401
        # PATCH v1.0.5: не грузим все данные ради имён отделов/команд
        departments = db.query('SELECT id, name FROM departments ORDER BY name')
        teams = db.query('SELECT id, name FROM teams ORDER BY name')
        return jsonify({
            'success': True,
            'departments': [{'id': d['id'], 'name': d.get('name', '')} for d in departments],
            'teams': [{'id': t['id'], 'name': t.get('name', '')} for t in teams],
        })

    @app.route('/api/plugins/gantt/data', methods=['GET'])
    def _g_data():
        # PATCH v1.0.5: добавлена проверка авторизации
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return jsonify({'success': False, 'error': 'auth'}), 401
            if not user_has(db, u, 'plugin.gantt.use'):
                return jsonify({'success': False, 'error': 'forbidden'}), 403
        except Exception:
            return jsonify({'success': False, 'error': 'auth'}), 401
        from_d = request.args.get('from', '').strip()
        to_d = request.args.get('to', '').strip()
        try:
            d1 = datetime.strptime(from_d, '%Y-%m-%d').date()
            d2 = datetime.strptime(to_d, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'success': False, 'error': 'bad dates'}), 400
        if d2 < d1:
            d1, d2 = d2, d1
        if (d2 - d1).days > 190:
            d2 = d1 + timedelta(days=190)

        dept = request.args.get('department', '').strip()
        team = request.args.get('team', '').strip()
        status = request.args.get('status', '').strip()
        f_type = request.args.get('task_type', '').strip()
        f_pocket = request.args.get('pocket', '').strip()

        data = db.load_all()

        team_ids = None
        if team:
            tm = next((x for x in data.get('teams', []) if x['id'] == team), None)
            if tm:
                team_ids = set(tm.get('member_ids') or [])
                if tm.get('manager_id'):
                    team_ids.add(tm['manager_id'])

        dept_emp_ids = None
        if dept:
            dept_emp_ids = set(e['id'] for e in data.get('employees', []) if e.get('department_id') == dept)

        # Карта сотрудник -> тер банк (отдел) для расчёта нагрузки по банкам.
        emp_dept = {e['id']: (e.get('department_id') or '') for e in data.get('employees', [])}
        dept_name = {d['id']: (d.get('name') or '') for d in data.get('departments', [])}

        days = []
        cur = d1
        while cur <= d2:
            days.append(cur.strftime('%Y-%m-%d'))
            cur += timedelta(days=1)

        today = date.today().strftime('%Y-%m-%d')
        d1_iso = d1.strftime('%Y-%m-%d')
        d2_iso = d2.strftime('%Y-%m-%d')

        logs_by_task = {}
        for l in data.get('log', []):
            tid = l.get('task_id')
            if tid:
                logs_by_task.setdefault(tid, []).append(l)

        out = []
        for t in data.get('tasks', []):
            if status and t.get('status') != status:
                continue
            if f_type and (t.get('task_type') or '') != f_type:
                continue
            if f_pocket and (t.get('pocket') or '') != f_pocket:
                continue
            assigns = t.get('assignees') or []
            if team_ids is not None and not (set(assigns) & team_ids):
                continue
            if dept_emp_ids is not None and not (set(assigns) & dept_emp_ids):
                continue
            sd = t.get('start_date') or ''
            dl = t.get('deadline') or ''
            if not sd and not dl:
                continue
            # PATCH v1.0.8: не рисуем задачу, если она полностью вне окна.
            # Раньше задача без start_date, но с deadline < d1_iso,
            # растягивалась на всю ширину окна.
            if dl and dl < d1_iso:
                continue
            if sd and sd > d2_iso:
                continue
            active_days = []
            for l in logs_by_task.get(t['id'], []):
                ld = l.get('date') or ''
                if d1_iso <= ld <= d2_iso:
                    try:
                        if float(l.get('hours') or 0) > 0:
                            active_days.append(ld)
                    except Exception:
                        pass
            overdue = bool(dl and dl < today and t.get('status') not in ('done', 'archived'))
            # Тер банки (отделы) задачи — по отделам её исполнителей.
            t_dept_ids = sorted({emp_dept.get(a, '') for a in assigns if emp_dept.get(a, '')})
            out.append({
                'id': t['id'],
                'name': t.get('name', ''),
                'icon': t.get('icon', '📋'),
                'status': t.get('status', 'active'),
                'start_date': sd or d1_iso,
                'deadline': dl or d2_iso,
                'overdue': overdue,
                'active_days': active_days,
                'stages': t.get('stages') or [],
                'task_type': t.get('task_type') or '',
                'pocket': t.get('pocket') or '',
                'dept_ids': t_dept_ids,
            })

        out.sort(key=lambda x: (x['start_date'], x['deadline'], x['name'].lower()))
        pockets = sorted({(_t.get('pocket') or '').strip()
                          for _t in data.get('tasks', [])
                          if (_t.get('pocket') or '').strip()})
        # Тер банки, встречающиеся в отфильтрованной выборке (для второй таблицы).
        bank_ids = sorted({did for _o in out for did in _o['dept_ids']})
        banks = [{'id': bid, 'name': dept_name.get(bid, bid)} for bid in bank_ids]
        return jsonify({
            'success': True,
            'days': days,
            'tasks': out,
            'today': today,
            'pockets': pockets,
            'banks': banks,
        })

    def on_startup(**ctx):
        print('[gantt] готов — «📅 План проверок» в шапке')

    hooks.on('on_startup', on_startup)


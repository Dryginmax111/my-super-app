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

/* Мультивыбор-дропдаун (карман / тер банк) — как в Excel */
.ms-dd { position: relative; display: inline-block; font-size: 0.82rem; }
.ms-dd-btn {
    padding: 6px 26px 6px 10px; border-radius: 8px;
    border: 1px solid var(--pg-input-border, rgba(245,215,110,0.26));
    background: var(--pg-input-bg, #232323); color: var(--pg-text, #e8e8e8);
    font-family: inherit; font-size: 0.82rem; cursor: pointer;
    min-width: 120px; max-width: 220px; text-align: left;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: relative;
}
.ms-dd-btn::after {
    content: '▾'; position: absolute; right: 9px; top: 50%;
    transform: translateY(-50%); color: var(--pg-meta, #a0a0a0); font-size: 0.7rem;
}
.ms-dd-btn:hover { border-color: var(--pg-accent, #f5d76e); }
.ms-dd.open .ms-dd-btn { border-color: var(--pg-accent, #f5d76e); }
.ms-dd-panel {
    display: none; position: absolute; z-index: 50; top: calc(100% + 4px); left: 0;
    min-width: 100%; max-height: 260px; overflow-y: auto;
    background: var(--pg-input-bg, #232323);
    border: 1px solid var(--pg-accent, #f5d76e); border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4); padding: 4px;
}
.ms-dd.open .ms-dd-panel { display: block; }
.ms-dd-item {
    display: flex; align-items: center; gap: 8px; padding: 6px 8px;
    border-radius: 6px; cursor: pointer; color: var(--pg-text, #e8e8e8);
    white-space: nowrap;
}
.ms-dd-item:hover { background: var(--pg-accent-bg, rgba(245,215,110,0.14)); }
.ms-dd-item input { margin: 0; cursor: pointer; }
.ms-dd-empty { padding: 8px; color: var(--pg-meta, #a0a0a0); font-style: italic; }

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
    opacity: 0.55; text-decoration: none;
    font-size: 0.95rem; cursor: pointer;
    transition: opacity 0.12s, background 0.12s, transform 0.12s;
    border: 1px solid transparent;
    background: transparent;
    color: var(--pg-text, #e8e8e8);
    border-radius: 5px; padding: 1px 5px; line-height: 1.4;
    font-family: inherit; white-space: nowrap;
}
.gg-row:hover .gg-edit { opacity: 1; }
.gg-edit:hover { opacity: 1; background: var(--pg-accent-soft, rgba(245,215,110,0.22)); transform: scale(1.12); }
body.trk-theme-light .gg-edit { color:#1b5e20; background:#eef3ee; border-color:rgba(0,0,0,0.15); }
body.trk-theme-light .gg-edit:hover { background:#dceadc; }
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
.gg-task-name.gg-expandable {
    font-size: 0.92rem;
    font-style: italic;
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
/* П.2/П.3: раскрытие банков-участников под названием проверки */
.gg-task-name.gg-expandable { cursor: pointer; user-select: none; }
.gg-task-name.gg-expandable:hover { text-decoration: underline; }
.gg-caret {
    display: inline-block; width: 0.9em; margin-right: 2px;
    font-size: 0.7rem; color: var(--pg-meta, #999);
    transition: transform 0.12s ease;
}
.gg-row.gg-sub-row { background: rgba(255,255,255,0.025); }
.gg-row.gg-sub-row .gg-name { padding-left: 18px; }
.gg-sub-name .gg-sub-bullet { margin-right: 10px; opacity: 0.75; }
.gg-sub-name .gg-task-name { padding-left: 14px; }
.gg-sub-mark { margin-left: auto; flex: 0 0 auto; opacity: 0.92; font-size: 0.95rem; }
.gg-row.gg-sub-lead { background: rgba(245,215,110,0.07); }
.gg-row.gg-sub-lead .gg-task-name { font-weight: 700; }
body.trk-theme-light .gg-row.gg-sub-row { background: rgba(0,0,0,0.03); }
body.trk-theme-light .gg-row.gg-sub-lead { background: rgba(245,215,110,0.14); }
.gg-bank-cell.gg-offday {
    background: repeating-linear-gradient(-45deg, rgba(140,140,140,0.18) 0 6px, rgba(140,140,140,0.08) 6px 12px) !important;
    color: transparent !important;
    text-shadow: none !important;
    border-color: rgba(160,160,160,0.18) !important;
}
body.trk-theme-light .gg-bank-cell.gg-offday {
    background: repeating-linear-gradient(-45deg, rgba(180,180,180,0.30) 0 6px, rgba(230,230,230,0.75) 6px 12px) !important;
    color: transparent !important;
    border-color: rgba(160,160,160,0.35) !important;
}

/* Урезанная модалка редактирования внутри gantt */
.gg-modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.48); display: none; align-items: center; justify-content: center; z-index: 2000; padding: 20px; }
.gg-modal-mask.open { display: flex; }
.gg-modal { width: min(1180px, 96vw); max-height: 92vh; overflow: auto; background: var(--pg-card-bg, #1a1a1a); color: var(--pg-text, #e8e8e8); border: 1px solid var(--pg-card-border, rgba(245,215,110,0.22)); border-radius: 16px; box-shadow: 0 18px 60px rgba(0,0,0,0.38); }
.gg-modal-head { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:16px 18px; border-bottom:1px solid var(--pg-card-border-soft, rgba(245,215,110,0.12)); position: sticky; top: 0; background: inherit; z-index: 2; }
.gg-modal-title { font-size: 1.05rem; font-weight: 800; }
.gg-modal-close { border:1px solid var(--pg-input-border, rgba(245,215,110,0.26)); background: var(--pg-input-bg, #232323); color: var(--pg-text, #e8e8e8); border-radius: 8px; padding: 6px 10px; cursor:pointer; }
.gg-modal-body { padding: 16px 18px 18px; display:flex; flex-direction:column; gap:16px; }
.gg-form-grid { display:grid; grid-template-columns: repeat(12, minmax(0,1fr)); gap: 12px; }
.gg-field { display:flex; flex-direction:column; gap:6px; }
.gg-field label { font-size:0.76rem; text-transform:uppercase; letter-spacing:0.5px; color: var(--pg-meta, #a0a0a0); font-weight:700; }
.gg-span-2 { grid-column: span 2; } .gg-span-3 { grid-column: span 3; } .gg-span-4 { grid-column: span 4; } .gg-span-6 { grid-column: span 6; } .gg-span-10 { grid-column: span 10; } .gg-span-12 { grid-column: span 12; }
.gg-field input[type="text"], .gg-field input[type="date"], .gg-field select { padding: 8px 10px; border-radius: 8px; border:1px solid var(--pg-input-border, rgba(245,215,110,0.26)); background: var(--pg-input-bg, #232323); color: var(--pg-text, #e8e8e8); font-family: inherit; font-size: 0.92rem; }
.gg-field input[readonly] { opacity: 0.85; cursor: default; }
.gg-box { border:1px solid var(--pg-card-border-soft, rgba(245,215,110,0.12)); border-radius: 12px; padding: 12px; background: rgba(255,255,255,0.02); }
.gg-box-title { font-size:0.82rem; font-weight:800; margin:0 0 10px; color: var(--pg-accent, #f5d76e); }
.gg-help { color: var(--pg-meta, #a0a0a0); font-size:0.78rem; font-style: italic; margin-top:4px; }
.gg-check-grid { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:8px 12px; }
.gg-check { display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:8px; background: rgba(255,255,255,0.03); }
.gg-check input { margin:0; }
.gg-stage-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; }
.gg-modal-actions { display:flex; justify-content:flex-end; gap:10px; padding-top: 4px; }
.gg-btn { border:1px solid var(--pg-input-border, rgba(245,215,110,0.26)); background: var(--pg-input-bg, #232323); color: var(--pg-text, #e8e8e8); border-radius: 8px; padding: 8px 12px; cursor:pointer; font-family:inherit; }
.gg-btn-primary { border:none; background: linear-gradient(135deg, var(--pg-accent, #f5d76e), var(--pg-accent-2, #e6a81a)); color:#0a0a0a; font-weight:800; }
.gg-error { display:none; color:#ffb3b3; background: rgba(231,76,60,0.12); border:1px solid rgba(231,76,60,0.24); border-radius:10px; padding:10px 12px; }
.gg-error.open { display:block; }
.gg-saving { opacity: 0.7; pointer-events:none; }
body.trk-theme-light .gg-modal { background:#fbfcfb; color:#13351a; border-color:#cfe1cf; }
body.trk-theme-light .gg-box { background:#f6faf6; }
body.trk-theme-light .gg-check { background:#eef5ee; }
@media (max-width: 980px) { .gg-check-grid, .gg-stage-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } .gg-span-2,.gg-span-3,.gg-span-4,.gg-span-6,.gg-span-10 { grid-column: span 12; } }
/* Тепловая заливка по величине нагрузки */
.gg-bank-cell.lvl0 { background: transparent; border-color: transparent; color: var(--pg-meta,#888); }
.gg-bank-cell.lvl1 { background: rgba(129,199,132,0.28); color:#dfeede; }  /* <2 — светло-зелёный */
.gg-bank-cell.lvl2 { background: rgba(255,224,130,0.30); color:#2a2300; }  /* 2..3 — светло-жёлтый */
.gg-bank-cell.lvl3 { background: rgba(239,154,154,0.32); color:#2a0a06; }  /* >=3 — светло-красный */
.gg-bank-total {
    font-weight: 800; color: var(--pg-accent, #f5d76e);
}
body.trk-theme-light .banks-title { color:#1b5e20; }
body.trk-theme-light .gg-bank-cell { color:#212121; background:#f1f3f4; border-color:rgba(0,0,0,0.1); }
body.trk-theme-light .gg-bank-cell.lvl0 { background:transparent; border-color:transparent; color:#999; }
body.trk-theme-light .gg-bank-cell.lvl1 { background:#d7efd8; color:#1b5e20; }
body.trk-theme-light .gg-bank-cell.lvl2 { background:#fff3c4; color:#7a5c00; }
body.trk-theme-light .gg-bank-cell.lvl3 { background:#fcdada; color:#9b1c1c; }

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
            <div class="ms-dd" id="fKindDD">
                <button type="button" class="ms-dd-btn" id="fKindBtn">Аудиторская проверка</button>
                <div class="ms-dd-panel" id="fKindPanel"></div>
            </div>
            <select id="fType">
                <option value="">Все типы проверок</option>
                <option value="розничная">Розничная</option>
                <option value="корпоративная">Корпоративная</option>
            </select>
            <div class="ms-dd" id="fPocketDD">
                <button type="button" class="ms-dd-btn" id="fPocketBtn">Все карманы</button>
                <div class="ms-dd-panel" id="fPocketPanel"></div>
            </div>
            <div class="ms-dd" id="fDeptDD">
                <button type="button" class="ms-dd-btn" id="fDeptBtn">Все тер банки</button>
                <div class="ms-dd-panel" id="fDeptPanel"></div>
            </div>
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
    <div class="gantt-box" id="banksBox" style="display:none;">
        <div class="loading">Загрузка…</div>
    </div>
    <div class="gg-modal-mask" id="ggTaskMask">
    <div class="gg-modal" role="dialog" aria-modal="true" aria-labelledby="ggTaskTitle">
        <div class="gg-modal-head">
            <div class="gg-modal-title" id="ggTaskTitle">Редактирование проверки</div>
            <button type="button" class="gg-modal-close" id="ggTaskClose">✕</button>
        </div>
        <div class="gg-modal-body" id="ggTaskBody">
            <div class="gg-error" id="ggTaskErr"></div>
            <div class="gg-form-grid">
                <div class="gg-field gg-span-2"><label>Иконка</label><input type="text" id="ggFIcon" maxlength="8"></div>
                <div class="gg-field gg-span-10"><label>Название</label><input type="text" id="ggFName" readonly></div>
                <div class="gg-field gg-span-3"><label>Тип задачи</label><select id="ggFType"><option value="">Выберите тип</option><option value="розничная">Розничная</option><option value="корпоративная">Корпоративная</option></select></div>
                <div class="gg-field gg-span-3"><label>Карман</label><input type="text" id="ggFPocket" maxlength="200"></div>
            </div>
            <div class="gg-box">
                <div class="gg-box-title">Этапы задачи</div>
                <div class="gg-stage-grid" id="ggStages"></div>
                <div class="gg-help">Указывается только дата начала этапа. Конец подтягивается автоматически на сервере; у последнего этапа — дедлайн задачи.</div>
            </div>
            <div class="gg-box">
                <div class="gg-box-title">Отделы / тер банки</div>
                <div class="gg-check-grid" id="ggDeptChecks"></div>
            </div>
            <div class="gg-box">
                <div class="gg-box-title">Назначено</div>
                <div class="gg-check-grid" id="ggAssignChecks"></div>
            </div>
            <div class="gg-box">
                <div class="gg-box-title">Руководитель проверки</div>
                <div class="gg-form-grid">
                    <div class="gg-field gg-span-6"><label>Банк-руководитель *</label><select id="ggFLeadDept"></select></div>
                    <div class="gg-field gg-span-6"><label>Сотрудник</label><select id="ggFLeadEmp"></select></div>
                </div>
            </div>
            <div class="gg-modal-actions">
                <button type="button" class="gg-btn" id="ggTaskCancel">Отмена</button>
                <button type="button" class="gg-btn gg-btn-primary" id="ggTaskSave">Сохранить</button>
            </div>
        </div>
    </div>
</div>
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

/* П.2: коэффициент руководителя проверки.
   Применяется ТОЛЬКО к банку-руководителю этой задачи:
   розничная -> x2, корпоративная -> x1.5, иначе (или рядовой банк) -> x1. */
function leadCoef(task, bankId) {
    if (!task || !bankId) return 1;
    if ((task.lead_department || '') !== bankId) return 1;
    var tp = task.task_type || '';
    if (tp === 'розничная') return 2;
    if (tp === 'корпоративная') return 1.5;
    return 1;
}
/* Нагрузка задачи в неделю для КОНКРЕТНОГО банка (с учётом коэффициента). */
function taskBankLoadAtMonday(task, bankId, mon) {
    var st = stageAtMonday(task.stages, mon);
    if (!st) return 0;
    var wt = (st.weight != null ? st.weight : 1);
    return wt * leadCoef(task, bankId);
}
function round2(v) { return Math.round(v * 100) / 100; }

/* Множество раскрытых задач (id). Клик по названию переключает. */
var ggExpanded = {};
var ggDeptNames = {};
var ggHolidays = {};
var ggTaskState = { loaded:false, tasksById:{}, employees:[], departments:[] };
var ggTaskCurrent = null;
var GG_STAGE_ORDER = ['подготовка','проверка_нжя','проверка_соглЦА','ос_проф','реализация_возражения','реализация_согласования','запас','оценка_тб'];
var GG_STAGE_LABELS = { 'подготовка':'Подготовка', 'проверка_нжя':'Проверка НЖЯ', 'проверка_соглЦА':'Проверка согл. ЦА', 'ос_проф':'ОС проф.', 'реализация_возражения':'Реализация возражения', 'реализация_согласования':'Реализация согласования', 'запас':'Запас', 'оценка_тб':'Оценка ТБ' };

function isOffDay(iso) {
    if (!iso) return false;
    var dt = new Date(iso + 'T00:00:00');
    var wd = dt.getDay();
    return wd === 0 || wd === 6 || !!ggHolidays[iso];
}

/* Подстроки «банки-участники» задачи для верхней таблицы.
   mode='week' -> периоды=weeks (у каждого .mon), mode='day' -> периоды=days (iso).
   Для каждого банка задачи выводим его нагрузку по периодам с коэффициентом
   руководителя (у банка-руководителя 👑 и бонус x2/x1.5). cellW — ширина колонки. */
function participantRowsHtml(t, periods, mode, trackW, cellW) {
    if (!ggExpanded[t.id]) return '';
    var dids = t.dept_ids || [];
    if (!dids.length) return '';
    var lead = t.lead_department || '';
    /* руководитель первым, остальные по алфавиту имени */
    var ordered = dids.slice().sort(function(a, b) {
        if (a === lead && b !== lead) return -1;
        if (b === lead && a !== lead) return 1;
        var na = ggDeptNames[a] || a, nb = ggDeptNames[b] || b;
        return na.localeCompare(nb, 'ru');
    });
    var html = '';
    ordered.forEach(function(did) {
        var isLead = (did === lead);
        var nm = ggDeptNames[did] || did;
        html += '<div class="gg-row gg-sub-row' + (isLead ? ' gg-sub-lead' : '') + '">';
        html +=   '<div class="gg-name gg-sub-name">';
        html +=     '<span class="gg-sub-bullet">•</span>';
        html +=     '<span class="gg-task-name" title="' + esc(nm) + '">' + esc(nm) + '</span>';
        html +=     '<span class="gg-sub-mark">' + (isLead ? '\ud83d\udc51' : '\ud83d\ude42') + '</span>';
        html +=   '</div>';
        html +=   '<div class="gg-track" style="width:' + trackW + 'px">';
        periods.forEach(function(p, i) {
            var mon = (mode === 'week') ? p.mon : p;
            var v = taskBankLoadAtMonday(t, did, mon);
            if (v <= 0) return;
            var txt = round2(v).toString();
            var lvl = v >= 3 ? 3 : (v < 2 ? 1 : 2);
            html += '<div class="gg-bank-cell lvl' + lvl + '" style="left:' + (i * cellW + 2) +
                    'px;width:' + (cellW - 4) + 'px" title="' + esc(nm) +
                    (isLead ? ' 👑' : '') + ' · нагрузка ' + txt + '">' + txt + '</div>';
        });
        html +=   '</div>';
        html += '</div>';
    });
    return html;
}

/* ---- Мультивыбор (Excel-стиль, чекбоксы) для карман / тер банк ---- */
/* Состояние: Set выбранных значений. Пусто = «все». */
var msSelected = { dept: {}, pocket: {}, kind: { audit: true } };
/* Справочник доступных пунктов: [{value,label}] */
var msOptions  = { dept: [], pocket: [], kind: [
    { value: 'audit', label: 'Аудиторская проверка' },
    { value: 'other', label: 'Другое' }
] };
/* Конфиг панелей мультивыбора: id панели/кнопки и подпись «все». */
var MS_CFG = {
    dept:   { panel: 'fDeptPanel',   btn: 'fDeptBtn',   all: 'Все тер банки' },
    pocket: { panel: 'fPocketPanel', btn: 'fPocketBtn', all: 'Все карманы' },
    kind:   { panel: 'fKindPanel',   btn: 'fKindBtn',   all: 'Все типы задач' }
};

function msRenderPanel(kind) {
    var cfg = MS_CFG[kind] || {};
    var panelId = cfg.panel;
    var panel = document.getElementById(panelId);
    if (!panel) return;
    var opts = msOptions[kind] || [];
    if (!opts.length) {
        panel.innerHTML = '<div class="ms-dd-empty">Нет вариантов</div>';
        return;
    }
    var html = '';
    opts.forEach(function(o) {
        var checked = msSelected[kind][o.value] ? ' checked' : '';
        html += '<label class="ms-dd-item">' +
                '<input type="checkbox" value="' + esc(o.value) + '"' + checked + '>' +
                '<span>' + esc(o.label) + '</span></label>';
    });
    panel.innerHTML = html;
    // Клик внутри панели не должен закрывать её (мультивыбор подряд).
    panel.addEventListener('click', function(e) { e.stopPropagation(); });
    panel.querySelectorAll('input[type=checkbox]').forEach(function(cb) {
        cb.addEventListener('change', function() {
            if (cb.checked) msSelected[kind][cb.value] = true;
            else delete msSelected[kind][cb.value];
            msUpdateBtn(kind);
            load();
        });
    });
}

function msUpdateBtn(kind) {
    var cfg = MS_CFG[kind] || {};
    var btn = document.getElementById(cfg.btn);
    if (!btn) return;
    var sel = Object.keys(msSelected[kind]);
    var allLabel = cfg.all || 'Все';
    if (!sel.length) { btn.textContent = allLabel; return; }
    if (sel.length === 1) {
        var o = (msOptions[kind] || []).find(function(x) { return x.value === sel[0]; });
        btn.textContent = o ? o.label : sel[0];
        return;
    }
    btn.textContent = 'Выбрано: ' + sel.length;
}

function msSetOptions(kind, opts) {
    msOptions[kind] = opts || [];
    // убираем из выбранного то, чего больше нет в списке
    var valid = {};
    msOptions[kind].forEach(function(o) { valid[o.value] = true; });
    Object.keys(msSelected[kind]).forEach(function(v) {
        if (!valid[v]) delete msSelected[kind][v];
    });
    msRenderPanel(kind);
    msUpdateBtn(kind);
}

function msGetSelected(kind) { return Object.keys(msSelected[kind]); }

/* Открытие/закрытие панелей по клику на кнопку и клику вне */
function msInit() {
    [['fKindDD','fKindBtn'], ['fDeptDD','fDeptBtn'], ['fPocketDD','fPocketBtn']].forEach(function(pair) {
        var dd = document.getElementById(pair[0]);
        var btn = document.getElementById(pair[1]);
        if (!dd || !btn) return;
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var wasOpen = dd.classList.contains('open');
            document.querySelectorAll('.ms-dd.open').forEach(function(x) { x.classList.remove('open'); });
            if (!wasOpen) dd.classList.add('open');
        });
    });
    document.addEventListener('click', function() {
        document.querySelectorAll('.ms-dd.open').forEach(function(x) { x.classList.remove('open'); });
    });
}

function ggTaskMask(){ return document.getElementById('ggTaskMask'); }
function ggTaskErr(msg) {
    var e = document.getElementById('ggTaskErr');
    if (!msg) { e.classList.remove('open'); e.textContent = ''; return; }
    e.textContent = msg; e.classList.add('open');
}
function ggNormList(v) { return Array.isArray(v) ? v.slice() : []; }
function ggTaskClone(o) { return JSON.parse(JSON.stringify(o || {})); }
function ggTaskSelectedChecks(boxId) {
    return Array.from(document.querySelectorAll('#' + boxId + ' input[type="checkbox"]:checked')).map(function(x){ return x.value; });
}
function ggTaskBuildStages(stages) {
    var box = document.getElementById('ggStages'); box.innerHTML = '';
    GG_STAGE_ORDER.forEach(function(k){
        var v = ''; (stages || []).forEach(function(st){ if (st && st.key === k) v = st.start || ''; });
        box.insertAdjacentHTML('beforeend', '<div class="gg-field"><label>' + esc(GG_STAGE_LABELS[k] || k) + '</label><input type="date" data-stage-key="' + esc(k) + '" value="' + esc(v) + '"></div>');
    });
}
function ggTaskBuildDeptChecks(selected) {
    var box = document.getElementById('ggDeptChecks'); var sel = {}; (selected || []).forEach(function(x){ sel[x] = true; }); box.innerHTML = '';
    (ggTaskState.departments || []).forEach(function(d){ box.insertAdjacentHTML('beforeend', '<label class="gg-check"><input type="checkbox" class="gg-dept-chk" value="' + esc(d.id) + '"' + (sel[d.id] ? ' checked' : '') + '><span>' + esc(d.name) + '</span></label>'); });
}
function ggTaskBuildAssignChecks(selected) {
    var box = document.getElementById('ggAssignChecks'); var deptSel = {}; ggTaskSelectedChecks('ggDeptChecks').forEach(function(x){ deptSel[x] = true; }); var sel = {}; (selected || []).forEach(function(x){ sel[x] = true; }); box.innerHTML = '';
    (ggTaskState.employees || []).filter(function(e){ return !Object.keys(deptSel).length || deptSel[e.department_id]; }).forEach(function(e){ var dep = e.department || ''; box.insertAdjacentHTML('beforeend', '<label class="gg-check"><input type="checkbox" class="gg-asg-chk" value="' + esc(e.id) + '"' + (sel[e.id] ? ' checked' : '') + '><span>' + esc(e.name) + (dep ? ' · ' + esc(dep) : '') + '</span></label>'); });
}
function ggTaskRebuildLeadOptions(preserveEmp) {
    var deptSel = ggTaskSelectedChecks('ggDeptChecks'); var ld = document.getElementById('ggFLeadDept'); var le = document.getElementById('ggFLeadEmp'); var curDept = ld.value; var curEmp = le.value;
    ld.innerHTML = deptSel.length ? '' : '<option value="">Сначала выберите банки-участники</option>';
    deptSel.forEach(function(id){ var d = (ggTaskState.departments || []).find(function(x){ return x.id === id; }); ld.insertAdjacentHTML('beforeend', '<option value="' + esc(id) + '">' + esc(d ? d.name : id) + '</option>'); });
    if (deptSel.indexOf(curDept) >= 0) ld.value = curDept; else if (deptSel.length) ld.value = deptSel[0]; else ld.value = '';
    var leadDept = ld.value; le.innerHTML = '<option value="">Не выбран</option>';
    (ggTaskState.employees || []).filter(function(e){ return leadDept && e.department_id === leadDept; }).forEach(function(e){ le.insertAdjacentHTML('beforeend', '<option value="' + esc(e.id) + '">' + esc(e.name) + '</option>'); });
    if (preserveEmp && curEmp) le.value = curEmp; if (le.value !== curEmp && preserveEmp && curEmp) le.value = '';
}
function ggTaskFillForm(task) {
    ggTaskCurrent = ggTaskClone(task);
    document.getElementById('ggFIcon').value = task.icon || '📋';
    document.getElementById('ggFName').value = task.name || '';
    document.getElementById('ggFType').value = task.task_type || '';
    document.getElementById('ggFPocket').value = task.pocket || '';
    ggTaskBuildStages(task.stages || []);
    ggTaskBuildDeptChecks(ggNormList(task.department_ids));
    ggTaskBuildAssignChecks(ggNormList(task.assignees));
    ggTaskRebuildLeadOptions(false);
    document.getElementById('ggFLeadDept').value = task.lead_department || document.getElementById('ggFLeadDept').value || '';
    ggTaskRebuildLeadOptions(true);
    document.getElementById('ggFLeadEmp').value = task.lead_employee || '';
    ggTaskErr(''); ggTaskMask().classList.add('open');
}
function ggTaskLoadState() {
    if (ggTaskState.loaded) return Promise.resolve(ggTaskState);
    return fetch('/api/tracker/state?log_days=0', {credentials:'same-origin'}).then(function(r){ return r.json(); }).then(function(d){
        if (!d || !d.success) throw new Error('Не удалось загрузить данные задач');
        ggTaskState.loaded = true; ggTaskState.employees = d.employees || []; ggTaskState.departments = d.departments || []; ggTaskState.tasksById = {};
        (d.tasks || []).forEach(function(t){ ggTaskState.tasksById[t.id] = t; }); return ggTaskState;
    });
}
function ggTaskOpen(taskId) {
    ggTaskLoadState().then(function(){ var t = ggTaskState.tasksById[taskId]; if (!t) throw new Error('Задача не найдена'); ggTaskFillForm(t); }).catch(function(err){ ggTaskErr(err && err.message ? err.message : 'Ошибка загрузки формы'); ggTaskMask().classList.add('open'); });
}
function ggTaskClose() { ggTaskMask().classList.remove('open'); ggTaskErr(''); }
function ggTaskPayload() {
    var t = ggTaskClone(ggTaskCurrent || {});
    t.icon = document.getElementById('ggFIcon').value.trim() || '📋';
    t.name = t.name || document.getElementById('ggFName').value.trim();
    t.task_type = document.getElementById('ggFType').value;
    t.pocket = document.getElementById('ggFPocket').value.trim();
    t.department_ids = ggTaskSelectedChecks('ggDeptChecks');
    t.assignees = ggTaskSelectedChecks('ggAssignChecks');
    t.lead_department = document.getElementById('ggFLeadDept').value;
    t.lead_employee = document.getElementById('ggFLeadEmp').value;
    var stages = {}; Array.from(document.querySelectorAll('#ggStages input[data-stage-key]')).forEach(function(inp){ stages[inp.getAttribute('data-stage-key')] = inp.value || ''; });
    t.stages = stages; return t;
}
function ggTaskSave() {
    var body = document.getElementById('ggTaskBody'); var p = ggTaskPayload();
    if (!p.department_ids.length) { ggTaskErr('Нужно выбрать минимум один банк-участник.'); return; }
    if (!p.lead_department) { ggTaskErr('Нужно выбрать банк-руководитель.'); return; }
    if (p.department_ids.indexOf(p.lead_department) < 0) { ggTaskErr('Банк-руководитель должен входить в состав участников.'); return; }
    ggTaskErr(''); body.classList.add('gg-saving');
    fetch('/api/tracker/task/save', { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body: JSON.stringify(p) })
        .then(function(r){ return r.json().then(function(d){ return {ok:r.ok, data:d}; }); })
        .then(function(res){ body.classList.remove('gg-saving'); if (!res.ok || !res.data || !res.data.success) throw new Error((res.data && (res.data.error || res.data.message)) || 'Ошибка сохранения'); ggTaskState.loaded = false; ggTaskClose(); load(); })
        .catch(function(err){ body.classList.remove('gg-saving'); ggTaskErr(err && err.message ? err.message : 'Ошибка сохранения'); });
}

function loadMeta() {
    fetch('/api/plugins/gantt/meta', {credentials: 'same-origin'})
        .then(function(r) { return r.json(); })
        .then(function(d) {
            if (!d.success) return;
            msSetOptions('dept', (d.departments || []).map(function(x) {
                return { value: x.id, label: x.name };
            }));
            var ts = document.getElementById('fTeam');
            (d.teams || []).forEach(function(x) {
                ts.insertAdjacentHTML('beforeend', '<option value="' + esc(x.id) + '">' + esc(x.name) + '</option>');
            });
        });
}

function fillPocketFilter(pockets) {
    var opts = [];
    (pockets || []).forEach(function(p) {
        if (p) opts.push({ value: p, label: p });
    });
    msSetOptions('pocket', opts);
}

function load() {
    var box = document.getElementById('ganttBox');
    box.innerHTML = '<div class="loading">Загрузка…</div>';
    var q = '?from=' + encodeURIComponent(document.getElementById('fFrom').value) +
            '&to=' + encodeURIComponent(document.getElementById('fTo').value);
    msGetSelected('dept').forEach(function(v) {
        q += '&department=' + encodeURIComponent(v);
    });
    var team = document.getElementById('fTeam').value;
    if (team) q += '&team=' + encodeURIComponent(team);
    var sts = document.getElementById('fStatus').value;
    if (sts) q += '&status=' + encodeURIComponent(sts);
    msGetSelected('kind').forEach(function(v) {
        q += '&task_kind=' + encodeURIComponent(v);
    });
    var fty = document.getElementById('fType').value;
    if (fty) q += '&task_type=' + encodeURIComponent(fty);
    msGetSelected('pocket').forEach(function(v) {
        q += '&pocket=' + encodeURIComponent(v);
    });
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
    window.__ggLastData = d;
    ggDeptNames = d.dept_names || {};
    ggHolidays = d.holidays || {};
    var view = document.getElementById('fView').value;
    if (view === 'week') { renderWeek(d); }
    else { renderDay(d); }
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

        html += '<div class="gg-row gg-task-row" data-tid="' + esc(t.id) + '">';
        html +=   '<div class="gg-name">';
        html +=     '<span class="gg-dot gg-dot-' + cls + '"></span>';
        html +=     '<span class="gg-ico">' + esc(t.icon || '📋') + '</span>';
        html +=     '<span class="gg-task-name gg-expandable" data-exp-tid="' + esc(t.id) + '" title="Показать банки-участники">' +
                      '<span class="gg-caret">\u25b8</span>' + esc(t.name) + '</span>';
        html +=     '<button type="button" class="gg-edit" data-edit-tid="' + esc(t.id) + '" title="Редактировать" aria-label="Редактировать">\u270f\ufe0f</button>';
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
        /* П.3: раскрытые банки-участники под задачей (дневной режим) */
        html += participantRowsHtml(t, days, 'day', trackW, DAY_W);
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

    /* П.3: вторая таблица «Нагрузка по тер банкам» в дневном режиме */
    renderBanks(d, days, 'day', DAY_W, STAGE_COLORS, STAGE_LABELS);
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
        html += '<div class="gg-row gg-task-row" data-tid="' + esc(t.id) + '">';
        html +=   '<div class="gg-name">';
        html +=     '<span class="gg-dot gg-dot-' + (t.overdue ? 'overdue' : (t.status||'active')) + '"></span>';
        html +=     '<span class="gg-ico">' + esc(t.icon || '📋') + '</span>';
        html +=     '<span class="gg-task-name gg-expandable" data-exp-tid="' + esc(t.id) + '" title="Показать банки-участники">' +
                      '<span class="gg-caret">\u25b8</span>' + esc(t.name) + '</span>';
        html +=     '<button type="button" class="gg-edit" data-edit-tid="' + esc(t.id) + '" title="Редактировать" aria-label="Редактировать">\u270f\ufe0f</button>';
        html +=   '</div>';
        html +=   '<div class="gg-track" style="width:' + trackW + 'px">';
        /* По каждой неделе — цвет этапа, активного в понедельник (свёрнуто = x1) */
        weeks.forEach(function(w, i) {
            var st = stageAtMonday(t.stages, w.mon);
            if (!st) return;
            var col = STAGE_COLORS[st.key] || '#888';
            var wt = (st.weight != null ? st.weight : 1);
            var wtTxt = round2(wt).toString();
            var ttl = (STAGE_LABELS[st.key] || st.key) + ' · неделя ' + fmtD(w.mon) + '–' + fmtD(w.sun) + ' · нагрузка ' + wtTxt;
            html += '<div class="gg-wk-cell" style="left:' + (i * WEEK_W + 2) + 'px;width:' + (WEEK_W - 4) + 'px;background:' + col + '" title="' + esc(ttl) + '">' +
                    '<span class="gg-wk-load-c">' + wtTxt + '</span></div>';
        });
        html +=   '</div>';
        html += '</div>';
        /* П.2/П.3: раскрытые банки-участники под задачей */
        html += participantRowsHtml(t, weeks, 'week', trackW, WEEK_W);
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
    renderBanks(d, weeks, 'week', WEEK_W, STAGE_COLORS, STAGE_LABELS);
}

/* Строит таблицу "Нагрузка по тер банкам": строки — банки,
   столбцы — те же периоды (недели ИЛИ дни), значение = сумма весов
   этапов всех задач банка, активных в этом периоде, с коэффициентом
   руководителя (x2 розн / x1.5 корп у банка-руководителя). mode='week'|'day'.
   Фильтры уже применены на бэке. */
function renderBanks(d, periods, mode, cellW, STAGE_COLORS, STAGE_LABELS) {
    var titleEl = document.getElementById('banksTitle');
    var box = document.getElementById('banksBox');
    var banks = d.banks || [];
    var tasks = d.tasks || [];

    if (!banks.length || !periods.length) {
        titleEl.style.display = 'none';
        box.style.display = 'none';
        return;
    }
    titleEl.style.display = 'block';
    box.style.display = 'block';

    var isWeek = (mode === 'week');
    var todayMon = d.today ? mondayOf(d.today) : '';
    var today = d.today || '';
    var trackW = periods.length * cellW;

    /* ключ периода -> дата для расчёта активного этапа (пн недели / сам день) */
    function pMon(p) { return isWeek ? p.mon : p; }

    /* Матрица: load[bankId][idx] = сумма весов с коэффициентом */
    var load = {};
    banks.forEach(function(b) {
        load[b.id] = [];
        for (var i = 0; i < periods.length; i++) load[b.id].push(0);
    });
    tasks.forEach(function(t) {
        var dids = t.dept_ids || [];
        if (!dids.length) return;
        /* Задача типа «Другое»: нет этапов, вместо веса этапа — коэффициент
           нагрузки, действующий на всём интервале [start_date; deadline]. */
        if ((t.task_kind || 'audit') === 'other') {
            var lc = (t.load_coef != null ? +t.load_coef : 0) || 0;
            if (lc <= 0) return;
            var sd = t.start_date || '';
            var dl = t.deadline || '';
            periods.forEach(function(p, i) {
                var day = pMon(p);
                if (sd && day < sd) return;
                if (dl && day > dl) return;
                dids.forEach(function(did) {
                    if (load[did]) load[did][i] += lc;
                });
            });
            return;
        }
        periods.forEach(function(p, i) {
            var mon = pMon(p);
            var st = stageAtMonday(t.stages, mon);
            if (!st) return;
            var wt = (st.weight != null ? st.weight : 1);
            dids.forEach(function(did) {
                if (load[did]) load[did][i] += wt * leadCoef(t, did);
            });
        });
    });

    var html = '<div class="gantt-inner gg-mode-' + (isWeek ? 'week' : 'day') + '">';
    html += '<div class="gg-header"' + (isWeek ? ' style="height:70px;"' : '') + '>';
    html += '<div class="gg-corner">Тер банк</div>';

    if (isWeek) {
        /* двухслойная шапка: месяцы + недели */
        var monthSpans = [];
        periods.forEach(function(w) {
            var mi = parseInt(w.mon.split('-')[1], 10) - 1;
            var yr = w.mon.split('-')[0];
            var key = yr + '-' + mi;
            var last = monthSpans[monthSpans.length - 1];
            if (last && last.key === key) { last.count++; }
            else { monthSpans.push({ key: key, mi: mi, yr: yr, count: 1 }); }
        });
        html += '<div class="gg-wk-head">';
        html += '<div class="gg-wk-months">';
        monthSpans.forEach(function(m) {
            var col = MONTH_COLORS[m.mi % MONTH_COLORS.length];
            html += '<div class="gg-wk-month" style="width:' + (m.count * cellW) + 'px;background:' + col + '">' + MONTH_NAMES[m.mi] + '</div>';
        });
        html += '</div>';
        html += '<div class="gg-wk-weeks">';
        periods.forEach(function(w) {
            var cls = 'gg-wk-week' + (w.mon === todayMon ? ' today' : '');
            html += '<div class="' + cls + '" style="width:' + cellW + 'px" title="' + w.mon + ' — ' + w.sun + '">' + fmtD(w.mon) + '–<br>' + fmtD(w.sun) + '</div>';
        });
        html += '</div></div></div>';
    } else {
        /* однослойная шапка по дням */
        html += '<div class="gg-days">';
        periods.forEach(function(dk) {
            var dt = new Date(dk + 'T00:00:00');
            var wd = dt.getDay();
            var cls = 'gg-day';
            if (wd === 0 || wd === 6) cls += ' weekend';
            if (dk === today) cls += ' today';
            html += '<div class="' + cls + '" style="width:' + cellW + 'px">';
            html += '<span class="gg-dow">' + DOW[wd] + '</span>';
            html += '<span class="gg-date">' + fmtD(dk) + '</span>';
            html += '</div>';
        });
        html += '</div></div>';
    }

    /* Тело — строки банков */
    html += '<div class="gg-body">';
    banks.forEach(function(b) {
        html += '<div class="gg-row">';
        html +=   '<div class="gg-name">';
        html +=     '<span class="gg-ico">🏦</span>';
        html +=     '<span class="gg-task-name" title="' + esc(b.name) + '">' + esc(b.name) + '</span>';
        html +=   '</div>';
        html +=   '<div class="gg-track" style="width:' + trackW + 'px">';
        periods.forEach(function(p, i) {
            var key = pMon(p);
            var off = (!isWeek && isOffDay(key));
            var v = load[b.id][i];
            var txt = round2(v).toString();
            var lvl = 0;
            if (!off && v > 0) { lvl = v >= 3 ? 3 : (v < 2 ? 1 : 2); }
            var lbl = isWeek ? ('неделя ' + fmtD(p.mon) + '–' + fmtD(p.sun)) : fmtD(p);
            html += '<div class="gg-bank-cell lvl' + lvl + (off ? ' gg-offday' : '') + '" style="left:' + (i * cellW + 2) + 'px;width:' + (cellW - 4) + 'px" title="' + esc(b.name) + ' · ' + lbl + (off ? ' · выходной/праздник' : (' · нагрузка ' + txt)) + '">' + (!off && v > 0 ? txt : '') + '</div>';
        });
        html +=   '</div>';
        html += '</div>';
    });
    html += '</div></div>';

    box.innerHTML = html;
}

/* --- Запуск --- */
document.getElementById('fApply').addEventListener('click', load);
document.getElementById('fTeam').addEventListener('change', load);
document.getElementById('fStatus').addEventListener('change', load);
document.getElementById('fView').addEventListener('change', load);
document.getElementById('fType').addEventListener('change', load);

document.getElementById('ggTaskClose').addEventListener('click', ggTaskClose);
document.getElementById('ggTaskCancel').addEventListener('click', ggTaskClose);
document.getElementById('ggTaskSave').addEventListener('click', ggTaskSave);
document.getElementById('ggTaskMask').addEventListener('click', function(ev){ if (ev.target === this) ggTaskClose(); });
document.getElementById('ggDeptChecks').addEventListener('change', function(){ var keepAsg = ggTaskSelectedChecks('ggAssignChecks'); ggTaskBuildAssignChecks(keepAsg); ggTaskRebuildLeadOptions(false); });
document.getElementById('ggFLeadDept').addEventListener('change', function(){ ggTaskRebuildLeadOptions(false); });
document.addEventListener('click', function(ev) {
    var ed = ev.target.closest ? ev.target.closest('.gg-edit[data-edit-tid]') : null;
    if (!ed) return;
    ev.preventDefault(); ev.stopPropagation();
    ggTaskOpen(ed.getAttribute('data-edit-tid'));
});

msInit();
msRenderPanel('kind'); msUpdateBtn('kind');
initDates();
loadMeta();
load();

/* П.2/П.3: клик по названию проверки раскрывает/сворачивает банки-участники.
   Делегированный обработчик — строки перерисовываются при каждом load(). */
document.addEventListener('click', function(ev) {
    var el = ev.target.closest ? ev.target.closest('.gg-expandable') : null;
    if (!el) return;
    ev.preventDefault();
    ev.stopPropagation();
    var tid = el.getAttribute('data-exp-tid');
    if (!tid) return;
    if (ggExpanded[tid]) delete ggExpanded[tid];
    else ggExpanded[tid] = true;
    if (window.__ggLastData) render(window.__ggLastData);
});

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

        # Мультивыбор: department/pocket приходят либо повторами параметра
        # (?department=a&department=b), либо одним CSV (?department=a,b).
        def _multi(name):
            vals = request.args.getlist(name)
            out_v = []
            for v in vals:
                for part in (v or '').split(','):
                    part = part.strip()
                    if part and part not in out_v:
                        out_v.append(part)
            return out_v
        dept_sel = _multi('department')      # список выбранных банков (пусто = все)
        team = request.args.get('team', '').strip()
        status = request.args.get('status', '').strip()
        f_type = request.args.get('task_type', '').strip()
        pocket_sel = _multi('pocket')        # список выбранных карманов (пусто = все)
        # Вид задачи: мультивыбор ('audit'|'other'). Если параметр не передан —
        # по умолчанию показываем только аудиторские проверки.
        kind_sel = _multi('task_kind')
        if not kind_sel:
            kind_sel = ['audit']
        kind_set = set(kind_sel)

        data = db.load_all()

        team_ids = None
        if team:
            tm = next((x for x in data.get('teams', []) if x['id'] == team), None)
            if tm:
                team_ids = set(tm.get('member_ids') or [])
                if tm.get('manager_id'):
                    team_ids.add(tm['manager_id'])

        # Сотрудники выбранного банка — нужны для fallback-привязки
        # (задача без прямой привязки task_departments относится к банку
        # через отделы своих исполнителей — как в app._task_matches_dept).
        dept_sel_set = set(dept_sel)
        dept_emp_ids = set()
        if dept_sel_set:
            dept_emp_ids = set(e['id'] for e in data.get('employees', [])
                               if e.get('department_id') in dept_sel_set)

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
            if ((t.get('task_kind') or 'audit')) not in kind_set:
                continue
            if f_type and (t.get('task_type') or '') != f_type:
                continue
            if pocket_sel and (t.get('pocket') or '') not in pocket_sel:
                continue
            assigns = t.get('assignees') or []
            if team_ids is not None and not (set(assigns) & team_ids):
                continue
            if dept_sel_set:
                t_dep_ids = t.get('department_ids') or []
                # OR: задача проходит, если хоть один выбранный банк в прямой привязке,
                # либо (нет прямой привязки) — по отделам исполнителей.
                if dept_sel_set & set(t_dep_ids):
                    pass  # прямая привязка к одному из выбранных банков
                elif not t_dep_ids and (set(assigns) & dept_emp_ids):
                    pass  # fallback: нет прямой привязки -> по отделам исполнителей
                else:
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
            _direct = [d for d in (t.get('department_ids') or []) if d]
            if _direct:
                t_dept_ids = sorted(set(_direct))
            else:
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
                'task_kind': t.get('task_kind') or 'audit',
                'load_coef': (lambda v: (float(v) if v not in (None, '') else 0.0))(t.get('load_coef')),
                'dept_ids': t_dept_ids,
                # П.2: руководитель проверки — для коэффициента нагрузки и 👑
                'lead_department': t.get('lead_department') or '',
                'lead_employee': t.get('lead_employee') or '',
            })

        out.sort(key=lambda x: (x['start_date'], x['deadline'], x['name'].lower()))
        pockets = sorted({(_t.get('pocket') or '').strip()
                          for _t in data.get('tasks', [])
                          if (_t.get('pocket') or '').strip()})
        # Тер банки для второй таблицы ("Нагрузка по банкам").
        # Вариант A: если банки выбраны в фильтре — строки = ТОЛЬКО выбранные
        # (и только те из них, что реально встречаются в выборке задач);
        # если фильтр банков пуст — все банки, присутствующие в выборке.
        present = {did for _o in out for did in _o['dept_ids']}
        if dept_sel_set:
            present = present & dept_sel_set
        bank_ids = sorted(present)
        banks = [{'id': bid, 'name': dept_name.get(bid, bid)} for bid in bank_ids]
        return jsonify({
            'success': True,
            'days': days,
            'tasks': out,
            'today': today,
            'pockets': pockets,
            'banks': banks,
            'dept_names': dept_name,
            'holidays': data.get('holidays') or {},
        })

    def on_startup(**ctx):
        print('[gantt] готов — «📅 План проверок» в шапке')

    hooks.on('on_startup', on_startup)


/* plugin_theme.js — самодостаточная тема для страниц-плагинов.
   Вставляет CSS-переменные и правила как <style> в <head>,
   не зависит от app.css. Читает тему из localStorage.tracker_theme. */
(function() {
    'use strict';

    var STYLE_ID = 'trk-plugin-theme-style';

    var CSS = [
        ':root {',
        '  --pg-bg: linear-gradient(135deg, #0a0a0a 0%, #131313 100%);',
        '  --pg-text: #e8e8e8;',
        '  --pg-text-strong: #f5f5f5;',
        '  --pg-meta: #a0a0a0;',
        '  --pg-desc: #c8c8c8;',
        '  --pg-card-bg: #1a1a1a;',
        '  --pg-card-bg-soft: #1c1c1c;',
        '  --pg-card-border: rgba(245,215,110,0.22);',
        '  --pg-card-border-soft: rgba(245,215,110,0.12);',
        '  --pg-input-bg: #232323;',
        '  --pg-input-border: rgba(245,215,110,0.26);',
        '  --pg-accent: #f5d76e;',
        '  --pg-accent-2: #e6a81a;',
        '  --pg-accent-bg: rgba(245,215,110,0.14);',
        '  --pg-inner-bg: #212121;',
        '  --pg-inner-bg-soft: #2a2a2a;',
        '  --pg-ok: #58d68d;',
        '  --pg-err: #ec7063;',
        '  --pg-warn: #f7dc6f;',
        '  --pg-info: #6dc2f0;',
        '  --pg-shadow: 0 8px 32px rgba(0,0,0,0.5);',
        '  color-scheme: dark;',
        '}',
        'body.trk-theme-light {',
        '  --pg-bg: linear-gradient(135deg, #f5f7f9 0%, #e8ecef 100%);',
        '  --pg-text: #212121;',
        '  --pg-text-strong: #111111;',
        '  --pg-meta: #5a6a72;',
        '  --pg-desc: #37474f;',
        '  --pg-card-bg: #ffffff;',
        '  --pg-card-bg-soft: #ffffff;',
        '  --pg-card-border: rgba(0,0,0,0.14);',
        '  --pg-card-border-soft: rgba(0,0,0,0.08);',
        '  --pg-input-bg: #ffffff;',
        '  --pg-input-border: rgba(0,0,0,0.20);',
        '  --pg-accent: #00695c;',
        '  --pg-accent-2: #ef6c00;',
        '  --pg-accent-bg: rgba(0,137,123,0.12);',
        '  --pg-inner-bg: #f0f2f4;',
        '  --pg-inner-bg-soft: #e8ecef;',
        '  --pg-ok: #2e7d32;',
        '  --pg-err: #c62828;',
        '  --pg-warn: #b7950b;',
        '  --pg-info: #0277bd;',
        '  --pg-shadow: 0 8px 24px rgba(0,0,0,0.10);',
        '  color-scheme: light;',
        '}',
        'body.plugin-page { background: var(--pg-bg) !important; background-attachment: fixed; color: var(--pg-text) !important; }',
        'body.plugin-page h1, body.plugin-page .h h1 { color: var(--pg-accent) !important; background: none !important; -webkit-text-fill-color: var(--pg-accent) !important; font-weight: 800; }',
        'body.plugin-page h2 { color: var(--pg-accent) !important; border-color: var(--pg-card-border) !important; }',
        'body.plugin-page .head, body.plugin-page .h { background: var(--pg-card-bg) !important; border: 1px solid var(--pg-card-border) !important; border-radius: 16px; box-shadow: var(--pg-shadow); }',
        'body.plugin-page .back { color: var(--pg-desc) !important; border-color: var(--pg-card-border) !important; text-decoration: none; }',
        'body.plugin-page .back:hover { background: var(--pg-accent-bg) !important; color: var(--pg-accent) !important; border-color: var(--pg-accent) !important; }',
        'body.plugin-page .sec, body.plugin-page .card, body.plugin-page .team-card, body.plugin-page .k, body.plugin-page .s, body.plugin-page .sum-card { background: var(--pg-card-bg) !important; border-color: var(--pg-card-border) !important; color: var(--pg-text) !important; }',
        'body.plugin-page .rank-block, body.plugin-page .ov-tasks, body.plugin-page .row, body.plugin-page .tah-row, body.plugin-page .kpi-cell, body.plugin-page .ex-cell { background: var(--pg-inner-bg) !important; border-color: var(--pg-card-border-soft) !important; color: var(--pg-text) !important; }',
        'body.plugin-page .kpi-cell, body.plugin-page .ex-cell { border: 1px solid var(--pg-card-border-soft) !important; }',
        'body.plugin-page .k .v, body.plugin-page .s .v, body.plugin-page .sum-val, body.plugin-page .sum-card .v, body.plugin-page .kpi-v, body.plugin-page .ex-v, body.plugin-page .rank-val, body.plugin-page .h, body.plugin-page .pill { color: var(--pg-accent) !important; }',
        'body.plugin-page .nm, body.plugin-page .name, body.plugin-page .row .nm, body.plugin-page .kpi-l, body.plugin-page .ex-l, body.plugin-page .team-name, body.plugin-page .rank-name { color: var(--pg-text) !important; }',
        'body.plugin-page .k .l, body.plugin-page .s .l, body.plugin-page .sum-lbl, body.plugin-page .team-mgr, body.plugin-page .lbl, body.plugin-page .empty, body.plugin-page .loading, body.plugin-page .meta, body.plugin-page .mtime, body.plugin-page .tah-head, body.plugin-page .dept, body.plugin-page .ot-dl, body.plugin-page .rank-title, body.plugin-page .sec-t, body.plugin-page .legend { color: var(--pg-meta) !important; }',
        'body.plugin-page .row.danger, body.plugin-page .row.warn, body.plugin-page .row.info { background: var(--pg-inner-bg) !important; }',
        'body.plugin-page .ov-tasks { background: rgba(231,76,60,0.10) !important; }',
        'body.trk-theme-light .plugin-page .ov-tasks { background: rgba(198,40,40,0.08) !important; }',
        'body.plugin-page .cover-bar, body.plugin-page .bar { background: var(--pg-inner-bg) !important; }',
        'body.plugin-page input, body.plugin-page select, body.plugin-page .period { background: var(--pg-input-bg) !important; border-color: var(--pg-input-border) !important; color: var(--pg-text) !important; }',
        'body.plugin-page input:focus, body.plugin-page select:focus { border-color: var(--pg-accent) !important; outline: none; }',
        'body.plugin-page .presets button { background: transparent !important; color: var(--pg-desc) !important; border: 1px solid var(--pg-card-border) !important; }',
        'body.plugin-page .presets button:hover { color: var(--pg-accent) !important; border-color: var(--pg-accent) !important; }',
        'body.plugin-page .presets button.active { background: var(--pg-accent-bg) !important; color: var(--pg-accent) !important; border-color: var(--pg-accent) !important; }',
        'body.plugin-page .dl { color: var(--pg-info) !important; border-color: rgba(52,152,219,0.4) !important; }',
        'body.trk-theme-light .plugin-page .dl { color: #01579b !important; border-color: rgba(1,87,155,0.35) !important; }',
        'body.plugin-page ::-webkit-scrollbar { width: 10px; height: 10px; }',
        'body.plugin-page ::-webkit-scrollbar-track { background: var(--pg-inner-bg-soft); }',
        'body.plugin-page ::-webkit-scrollbar-thumb { background: var(--pg-card-border); border-radius: 5px; }',
        'body.plugin-page ::-webkit-scrollbar-thumb:hover { background: var(--pg-accent); }',
        '.plugin-theme-btn { padding: 6px 12px; border-radius: 20px; background: transparent; border: 1px solid var(--pg-card-border); color: var(--pg-desc); font-size: 0.82rem; font-weight: 600; font-family: inherit; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.15s; margin-left: auto; }',
        '.plugin-theme-btn:hover { background: var(--pg-accent-bg); border-color: var(--pg-accent); color: var(--pg-accent); }',
        'body.trk-theme-light .plugin-page .h, body.trk-theme-light .plugin-page .head { background: #ffffff !important; border-color: rgba(0,0,0,0.14) !important; box-shadow: 0 4px 16px rgba(0,0,0,0.08); }',
        'body.trk-theme-light .plugin-page .row.danger { background: rgba(198,40,40,0.05) !important; }',
        'body.trk-theme-light .plugin-page .row.warn { background: rgba(230,168,26,0.08) !important; }',
        'body.trk-theme-light .plugin-page .row.info { background: rgba(2,119,189,0.06) !important; }',
        'body.trk-theme-light .plugin-page .rank-val, body.trk-theme-light .plugin-page .h, body.trk-theme-light .plugin-page .pill { background: rgba(0,137,123,0.12) !important; color: #00695c !important; }',
        'body.trk-theme-light .plugin-page .kpi-v, body.trk-theme-light .plugin-page .sum-val, body.trk-theme-light .plugin-page .sum-card .v, body.trk-theme-light .plugin-page .k .v, body.trk-theme-light .plugin-page .s .v { color: #00695c !important; }',
        'body.trk-theme-light .plugin-page .kpi-v[style*="ec7063"], body.trk-theme-light .plugin-page .s.danger .v { color: #c62828 !important; }',
        'body.trk-theme-light .plugin-page .rank-avatar, body.trk-theme-light .plugin-page .dot { box-shadow: inset 0 0 0 1px rgba(0,0,0,0.15); }',
        'body.trk-theme-light .plugin-page .trend-bar { background: linear-gradient(180deg, #00897b, #00695c); }'
    ].join('\n');

    function injectStyle() {
        if (document.getElementById(STYLE_ID)) return;
        var s = document.createElement('style');
        s.id = STYLE_ID;
        s.textContent = CSS;
        (document.head || document.documentElement).appendChild(s);
    }

    function getTheme() {
        try { return localStorage.getItem('reestr_tracker_theme') || 'dark'; }
        catch (e) { return 'dark'; }
    }

    function applyTheme(theme) {
        theme = (theme === 'light') ? 'light' : 'dark';
        document.documentElement.setAttribute('data-trk-theme', theme);
        var b = document.body;
        if (!b) return;
        b.classList.remove('trk-theme-dark', 'trk-theme-light');
        b.classList.add('trk-theme-' + theme);
        b.classList.add('plugin-page');
        document.querySelectorAll('.plugin-theme-btn').forEach(function(btn) {
            var ic = btn.querySelector('.ptb-icon');
            var lb = btn.querySelector('.ptb-label');
            if (ic) ic.textContent = theme === 'dark' ? '☀️' : '🌙';
            if (lb) lb.textContent = theme === 'dark' ? 'Светлая' : 'Тёмная';
        });
    }

    function toggle() {
        var cur = getTheme();
        var next = cur === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem('reestr_tracker_theme', next); } catch (e) {}
        applyTheme(next);
    }

    function injectBtn() {
        var head = document.querySelector('.head, .h');
        if (!head) return;
        if (head.querySelector('.plugin-theme-btn')) return;
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'plugin-theme-btn';
        b.innerHTML = '<span class="ptb-icon">☀️</span><span class="ptb-label">Светлая</span>';
        b.addEventListener('click', function(e) { e.preventDefault(); toggle(); });
        head.appendChild(b);
    }

    injectStyle();
    applyTheme(getTheme());

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            injectStyle();
            applyTheme(getTheme());
            injectBtn();
            setTimeout(injectBtn, 400);
        });
    } else {
        injectBtn();
        setTimeout(injectBtn, 400);
    }

    /* Наблюдаем за изменениями DOM — некоторые страницы рендерят шапку позже */
    setTimeout(injectBtn, 800);
    setTimeout(injectBtn, 1500);

    window.__trkPluginTheme = { apply: applyTheme, toggle: toggle, get: getTheme };
})();

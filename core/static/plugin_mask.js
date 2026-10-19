/* ============================================================
   PATCH 1.0.4 — маскирование ФИО для плагинов
   Флаг: localStorage.reestr_tracker_mask (тот же, что в трекере).
   ============================================================ */
(function () {
    'use strict';
    if (window.__trkPluginMaskLoaded) return;
    window.__trkPluginMaskLoaded = true;

    function _enabled() {
        try { return localStorage.getItem('reestr_tracker_mask') === '1'; }
        catch (e) { return false; }
    }

    window.__trkMaskEnabled = _enabled();

    window.__trkMaskName = function (name) {
        var s = String(name == null ? '' : name);
        if (!window.__trkMaskEnabled) return s;
        if (!s) return s;
        return s.split(/\s+/).map(function (w) {
            if (w.length <= 1) return w;
            return w[0] + new Array(w.length).join('*');
        }).join(' ');
    };

    window.__trkEscName = function (name) {
        var s = window.__trkMaskName(name);
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    };

    window.addEventListener('storage', function (e) {
        if (e.key === 'reestr_tracker_mask') {
            var now = _enabled();
            if (now !== window.__trkMaskEnabled) {
                window.__trkMaskEnabled = now;
                setTimeout(function () { location.reload(); }, 50);
            }
        }
    });
})();

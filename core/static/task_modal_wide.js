/* ============================================================
   v1.0.7 — Перестройка карточки задачи: DOM-раскладка
   ============================================================ */
(function () {
    'use strict';
    if (window.__trkTaskModalWideV17) return;
    window.__trkTaskModalWideV17 = true;

    function byField(id) {
        var el = document.getElementById(id);
        return el ? el.closest('.form-group') : null;
    }

    function restructure() {
        var m = document.getElementById('taskModal');
        if (!m) return;
        if (m._trkTaskModalWideApplied) return;
        var content = m.querySelector('.modal-content');
        if (!content) return;

        var gIcon = byField('taskIconPickBtn');
        var gDesc = byField('task_description');
        var gFolder = byField('task_folder');
        var gOrder = byField('task_order_ref');
        var gCompleted = byField('task_completed_at');
        var gTags = byField('taskTagsBox');
        var gDepts = byField('taskDepartmentsList');
        var gAssignees = byField('taskAssigneesList');

        var row3 = content.querySelector('.form-row-3');

        if (gIcon) {
            var rowIcon = gIcon.closest('.form-row');
            if (rowIcon) rowIcon.classList.add('task-row-icon-name');
        }

        if (row3 && gCompleted) {
            row3.appendChild(gCompleted);
            row3.classList.add('task-row-4col');
        }

        if (gDesc && gTags) {
            var oldTagsRow = gTags.closest('.form-row');
            var w1 = document.createElement('div');
            w1.className = 'form-row task-row-2';
            gDesc.parentNode.insertBefore(w1, gDesc);
            w1.appendChild(gDesc);
            w1.appendChild(gTags);
            if (oldTagsRow && oldTagsRow.parentNode &&
                oldTagsRow.parentNode === content &&
                oldTagsRow.children.length === 0) {
                oldTagsRow.parentNode.removeChild(oldTagsRow);
            }
        }

        if (gFolder && gOrder && gFolder.parentNode === content) {
            var w2 = document.createElement('div');
            w2.className = 'form-row task-row-2';
            gFolder.parentNode.insertBefore(w2, gFolder);
            w2.appendChild(gFolder);
            w2.appendChild(gOrder);
        }

        if (gDepts && gAssignees && gDepts.parentNode === content) {
            var w3 = document.createElement('div');
            w3.className = 'form-row task-row-2 task-row-lists';
            gDepts.parentNode.insertBefore(w3, gDepts);
            w3.appendChild(gDepts);
            w3.appendChild(gAssignees);
        }

        m._trkTaskModalWideApplied = true;
    }

    function attachObserver() {
        var m = document.getElementById('taskModal');
        if (!m || m._trkTaskModalWideObs) return;
        m._trkTaskModalWideObs = true;
        var obs = new MutationObserver(function () {
            if (m.classList.contains('active')) {
                setTimeout(restructure, 60);
                setTimeout(restructure, 250);
            }
        });
        obs.observe(m, { attributes: true, attributeFilter: ['class'] });
    }

    function boot() {
        attachObserver();
        setTimeout(attachObserver, 500);
        setTimeout(attachObserver, 1500);
        setTimeout(restructure, 600);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }

    document.addEventListener('click', function (e) {
        if (!e.target || !e.target.closest) return;
        if (e.target.closest('#addTaskBtn') ||
            e.target.closest('#addTaskBtn2') ||
            e.target.closest('.task-card-clickable')) {
            setTimeout(restructure, 100);
            setTimeout(restructure, 350);
        }
    }, true);
})();
/* v1.1.1 — фиксация шапки/футера карточки задачи + разворот списков */
(function () {
    'use strict';
    if (window.__trkTaskModalFixedV111) return;
    window.__trkTaskModalFixedV111 = true;

    function unwrapListsRow() {
        var content = document.querySelector('#taskModal .modal-content');
        if (!content) return;
        var row = content.querySelector('.task-row-lists');
        if (!row) return;
        var groups = row.querySelectorAll(':scope > .form-group');
        var anchor = row;
        for (var i = 0; i < groups.length; i++) {
            anchor.parentNode.insertBefore(groups[i], anchor);
        }
        row.parentNode.removeChild(row);
    }

    function wrapScrollable() {
        var content = document.querySelector('#taskModal .modal-content');
        if (!content) return;
        if (content.querySelector(':scope > .task-modal-scroll')) return;

        var h2 = content.querySelector(':scope > h2');
        var actions = content.querySelector(':scope > .modal-actions');
        if (!h2 || !actions) return;

        var scroll = document.createElement('div');
        scroll.className = 'task-modal-scroll';

        var node = h2.nextSibling;
        while (node && node !== actions) {
            var next = node.nextSibling;
            scroll.appendChild(node);
            node = next;
        }
        content.insertBefore(scroll, actions);
    }

    function restructure() {
        var m = document.getElementById('taskModal');
        if (!m) return;
        unwrapListsRow();
        wrapScrollable();
    }

    function attachObserver() {
        var m = document.getElementById('taskModal');
        if (!m || m._fixedV111Obs) return;
        m._fixedV111Obs = true;
        var obs = new MutationObserver(function () {
            if (m.classList.contains('active')) {
                setTimeout(restructure, 80);
                setTimeout(restructure, 300);
            }
        });
        obs.observe(m, { attributes: true, attributeFilter: ['class'] });
    }

    function boot() {
        attachObserver();
        setTimeout(attachObserver, 500);
        setTimeout(attachObserver, 1500);
        setTimeout(restructure, 600);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else { boot(); }

    document.addEventListener('click', function (e) {
        if (!e.target || !e.target.closest) return;
        if (e.target.closest('#addTaskBtn') || e.target.closest('#addTaskBtn2')) {
            setTimeout(restructure, 200);
            setTimeout(restructure, 500);
        }
    }, true);
})();

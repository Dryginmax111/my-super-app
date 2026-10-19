(function(){
'use strict';

var csrf = window.REESTR_CSRF || '';
var state = {
    users: [],
    permission_groups: [],
    default_user: [],
    employees: [],
    current_user_id: null,
    is_admin: false,
    loaded: false,
};

function $(id){ return document.getElementById(id); }
function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function notify(msg, kind){
    var n = $('trackerNotif'); if (!n) return;
    n.textContent = msg;
    n.className = 'tracker-notification show' + (kind === 'error' ? ' error' : '');
    clearTimeout(n._t);
    n._t = setTimeout(function(){ n.classList.remove('show'); }, 4500);
}

var _pendingReqs = 0;
function _showLoader() {
    _pendingReqs++;
    var l = document.getElementById('globalLoader');
    if (l) l.classList.add('active');
}
function _hideLoader() {
    _pendingReqs = Math.max(0, _pendingReqs - 1);
    if (_pendingReqs === 0) {
        var l = document.getElementById('globalLoader');
        if (l) l.classList.remove('active');
    }
}
function api(url, opts){
    opts = opts || {};
    opts.headers = Object.assign({}, opts.headers || {});
    if (csrf && opts.method && opts.method !== 'GET') opts.headers['X-CSRF-Token'] = csrf;
    opts.credentials = 'same-origin';
    _showLoader();
    return fetch(url, opts).then(function(r){
        if (r.status === 401) { location.href = '/login'; return new Promise(function(){}); }
        if (!r.ok) return r.text().then(function(t){
            var m = 'HTTP ' + r.status;
            try { var j = JSON.parse(t); if (j.error) m += ' — ' + j.error; }
            catch(e){ if (t) m += ' — ' + t.slice(0,200); }
            throw new Error(m);
        });
        return r.json();
    }).finally(_hideLoader);
}

document.querySelectorAll('.settings-tab').forEach(function(tab){
    tab.addEventListener('click', function(){
        var id = this.getAttribute('data-tab');
        document.querySelectorAll('.settings-tab').forEach(function(t){ t.classList.toggle('active', t === tab); });
        document.querySelectorAll('.settings-panel').forEach(function(p){
            p.classList.toggle('active', p.id === 'sp-' + id);
        });
        if (id === 'holidays') loadHolidays();
        if (id === 'db') loadDbInfo();
        if (id === 'audit') loadAudit();
        if (id === 'plugins') loadPluginsManager();
        if (id === 'about') loadAbout();
    });
});

function loadUsers(){
    return api('/api/settings/users').then(function(d){
        state.users = d.users || [];
        state.permission_groups = d.permission_groups || [];
        state.default_user = d.default_user || [];
        state.current_user_id = d.current_user_id;
        state.is_admin = !!d.is_admin;
        state.loaded = true;
        renderUsers();
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
}

function renderUsers(){
    var wrap = $('usersList'); if (!wrap) return;
    if (!state.users.length) { wrap.innerHTML = '<div class="dict-empty">Нет пользователей</div>'; return; }
    var html = '';
    state.users.forEach(function(u){
        var roleCls = u.role === 'admin' ? 'admin' : 'user';
        var roleLbl = u.role === 'admin' ? 'ADMIN' : 'USER';
        var canEdit = state.is_admin;
        var canDelete = state.is_admin && u.id !== state.current_user_id;
        var empName = u.employee_id
            ? ((state.employees.find(function(e){return e.id===u.employee_id;})||{}).name || u.employee_id)
            : '';
        html += '<div class="settings-user' + (u.is_active ? '' : ' inactive') + '" data-id="' + u.id + '">'
            + '<div class="su-main">'
            +   '<div class="su-name">' + esc(u.display_name || u.username)
            +     (u.is_active ? '' : ' <span style="color:#e74c3c;font-size:0.75rem;">(отключён)</span>')
            +   '</div>'
            +   '<div class="su-sub">Логин: <b>' + esc(u.username) + '</b>'
            +     (empName ? ' · Сотрудник: ' + esc(empName) : '')
            +     (u.last_login ? ' · Последний вход: ' + esc(u.last_login) : '')
            +   '</div>'
            + '</div>'
            + '<span class="su-role ' + roleCls + '">' + roleLbl + '</span>'
            + (canEdit ? '<button class="dict-action-btn" data-act="edit" title="Редактировать">✏️</button>' : '')
            + (canDelete ? '<button class="dict-action-btn danger" data-act="delete" title="Удалить">🗑</button>' : '')
            + '</div>';
    });
    wrap.innerHTML = html;
    wrap.querySelectorAll('.settings-user').forEach(function(row){
        var id = parseInt(row.getAttribute('data-id'), 10);
        var eb = row.querySelector('[data-act="edit"]');
        var db = row.querySelector('[data-act="delete"]');
        if (eb) eb.addEventListener('click', function(){
            var u = state.users.find(function(x){ return x.id === id; });
            if (u) openUserModal(u);
        });
        if (db) db.addEventListener('click', function(){ deleteUser(id); });
    });
}

function renderPermsTree(selected){
    var tree = $('permsTree'); if (!tree) return;
    selected = selected || {};
    var defaults = (state.default_user || []);
    var html = '';
    (state.permission_groups || []).forEach(function(grp){
        html += '<div class="perms-group">'
             +  '<div class="perms-group-title">' + esc(grp.title) + '</div>'
             +  '<div class="perms-list">';
        grp.items.forEach(function(it){
            var v;
            if (Object.prototype.hasOwnProperty.call(selected, it.key)) {
                v = !!selected[it.key];
            } else {
                v = defaults.indexOf(it.key) !== -1;
            }
            var checked = v ? ' checked' : '';
            html += '<label class="perms-item">'
                 +  '<input type="checkbox" data-perm="' + esc(it.key) + '"' + checked + '>'
                 +  '<span>' + esc(it.label) + '</span>'
                 +  '</label>';
        });
        html += '</div></div>';
    });
    tree.innerHTML = html;
}

function openUserModal(u){
    u = u || null;
    $('userModalTitle').textContent = u ? ('Пользователь: ' + u.username) : 'Новый пользователь';
    $('user_id').value = u ? u.id : '';
    $('user_username').value = u ? u.username : '';
    $('user_kody').value = '';
    $('pwd_hint').textContent = u ? '(оставьте пустым — не менять)' : '(обязательно)';
    $('user_display_name').value = u ? (u.display_name || '') : '';
    $('user_role').value = u ? u.role : 'user';
    $('user_is_active').checked = u ? u.is_active : true;
    $('user_username').disabled = !!u;

    var sel = $('user_employee');
    sel.innerHTML = '<option value="">— не привязан —</option>';
    state.employees.forEach(function(e){
        var opt = document.createElement('option');
        opt.value = e.id;
        opt.textContent = e.name + (e.fired ? ' 🚪' : '');
        sel.appendChild(opt);
    });
    sel.value = u ? (u.employee_id || '') : '';

    renderPermsTree(u ? u.permissions : {});
    syncRoleUI();
    $('userModal').classList.add('active');
}

function syncRoleUI(){
    var role = $('user_role').value;
    $('permsWrap').style.display = (role === 'admin') ? 'none' : '';
}

$('user_role').addEventListener('change', syncRoleUI);

function collectPerms(){
    var out = {};
    $('permsTree').querySelectorAll('input[data-perm]').forEach(function(cb){
        out[cb.getAttribute('data-perm')] = cb.checked;
    });
    return out;
}

function saveUser(){
    var payload = {
        id: $('user_id').value ? parseInt($('user_id').value, 10) : null,
        username: $('user_username').value.trim(),
        kody: $('user_kody').value,
        display_name: $('user_display_name').value.trim(),
        role: $('user_role').value,
        employee_id: $('user_employee').value || '',
        is_active: $('user_is_active').checked,
        permissions: collectPerms(),
    };
    if (!payload.username) { notify('❌ Укажите логин', 'error'); return; }
    if (!payload.id && !payload.kody) { notify('❌ Укажите parol для нового пользователя', 'error'); return; }
    api('/api/settings/users/save', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload),
    }).then(function(d){
        if (!d.success) throw new Error(d.error || 'Ошибка');
        notify('✅ Сохранено', 'success');
        $('userModal').classList.remove('active');
        return loadUsers();
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
}

function deleteUser(id){
    var u = state.users.find(function(x){ return x.id === id; });
    if (!u) return;
    if (!confirm('Удалить пользователя «' + u.username + '»?\n\nДействие необратимо.')) return;
    api('/api/settings/users/delete', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ id: id }),
    }).then(function(d){
        if (!d.success) throw new Error(d.error || 'Ошибка');
        notify('✅ Удалено', 'success');
        return loadUsers();
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
}

function loadHolidays(){
    return api('/api/tracker/state').then(function(d){
        state.holidays = d.holidays || {};
        renderHolidays();
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
}
function renderHolidays(){
    var wrap = $('holidaysList'); if (!wrap) return;
    var keys = Object.keys(state.holidays || {}).sort();
    if (!keys.length) { wrap.innerHTML = '<div class="dict-empty">Нет праздников</div>'; return; }
    var html = '';
    keys.forEach(function(k){
        html += '<div class="settings-user" data-date="' + esc(k) + '">'
            + '<div class="su-main"><div class="su-name">🎉 ' + esc(state.holidays[k]) + '</div>'
            + '<div class="su-sub">' + esc(k) + '</div></div>'
            + (state.is_admin ? '<button class="dict-action-btn danger" data-act="del">🗑</button>' : '')
            + '</div>';
    });
    wrap.innerHTML = html;
    wrap.querySelectorAll('[data-act="del"]').forEach(function(b){
        b.addEventListener('click', function(){
            var dk = this.closest('.settings-user').getAttribute('data-date');
            if (!confirm('Удалить праздник ' + dk + '?')) return;
            api('/api/tracker/holiday/delete', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ date: dk })
            }).then(function(){ loadHolidays(); });
        });
    });
}
$('holAddBtn').addEventListener('click', function(){
    var dk = $('hol_date').value, name = $('hol_name').value.trim();
    if (!dk) { notify('❌ Укажите дату', 'error'); return; }
    if (!name) name = 'Праздник';
    api('/api/tracker/holiday/save', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ date: dk, name: name })
    }).then(function(){
        notify('✅ Сохранено', 'success');
        $('hol_name').value = '';
        loadHolidays();
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
});

function loadDbInfo(){
    api('/api/settings/db_info').then(function(d){
        var info = $('db_info_block');
        if (info) {
            var sizeTxt = d.db_size != null ? (Math.round(d.db_size / 1024) + ' KB') : '—';
            info.innerHTML = '<div><b>Путь:</b> <code>' + esc(d.db_path) + '</code></div>'
                + '<div><b>Размер:</b> ' + sizeTxt + '</div>'
                + '<div><b>Сервер:</b> ' + esc(d.host) + ':' + esc(String(d.port)) + '</div>';
        }
        var inp = $('db_path_input');
        if (inp) inp.value = d.db_path || '';
    }).catch(function(e){
        var info = $('db_info_block');
        if (info) info.textContent = '❌ ' + e.message;
    });
    api('/api/settings/plugins').then(function(d){
        var el = $('plugins_list');
        if (!el) return;
        var plugins = d.plugins || [];
        if (!plugins.length) { el.innerHTML = '<i>Плагины не загружены</i>'; return; }
        el.innerHTML = plugins.map(function(p){
            var mark = p.enabled ? '' : ' <span style="color:#e74c3c;">(отключён)</span>';
            return '<div>📦 <b>' + esc(p.name) + '</b> v' + esc(p.version)
                + (p.description ? ' — ' + esc(p.description) : '') + mark + '</div>';
        }).join('');
    }).catch(function(){});
}
$('dbPathSaveBtn').addEventListener('click', function(){
    var p = $('db_path_input').value.trim();
    if (!p) { notify('❌ Укажите путь', 'error'); return; }
    if (!confirm('Сохранить новый путь к БД?\n\nИзменения применятся после перезапуска сервера.')) return;
    api('/api/settings/db_path/save', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ db_path: p })
    }).then(function(d){
        if (!d.success) throw new Error(d.error || 'Ошибка');
        notify('✅ Сохранено. Перезапустите сервер.', 'success');
        loadDbInfo();
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
});

function loadPluginsManager(){
    var wrap = $('pluginsManagerList');
    if (wrap) wrap.innerHTML = '<div class="dict-empty">Загрузка...</div>';
    return api('/api/settings/plugins').then(function(d){
        if (!d.success) throw new Error(d.error || 'Ошибка');
        renderPluginsManager(d.plugins || []);
    }).catch(function(e){
        if (wrap) wrap.innerHTML = '<div class="dict-empty" style="color:#e74c3c;">' + esc(e.message || 'Ошибка') + '</div>';
    });
}

function renderPluginsManager(plugins){
    var wrap = $('pluginsManagerList');
    if (!wrap) return;
    if (!plugins.length) {
        wrap.innerHTML = '<div class="dict-empty">В папке plugins/ нет ни одного .py-плагина</div>';
        return;
    }
    var canToggle = !!state.is_admin;
    var html = '';
    plugins.forEach(function(p){
        var stateCls = p.enabled ? 'on' : 'off';
        var loadedMark = p.loaded ? '' : ' <span class="plug-not-loaded">не загружен</span>';
        html += '<div class="plugin-card ' + stateCls + '" data-name="' + esc(p.name) + '">'
            + '<div class="plugin-main">'
            +   '<div class="plugin-name">'
            +     '<span class="plugin-icon">🧩</span>'
            +     '<b>' + esc(p.name) + '</b>'
            +     ' <span class="plugin-ver">v' + esc(p.version || '—') + '</span>'
            +     loadedMark
            +   '</div>'
            +   (p.description ? '<div class="plugin-desc">' + esc(p.description) + '</div>' : '')
            +   (p.updated_at ? '<div class="plugin-meta">изменён: ' + esc(p.updated_at) + '</div>' : '')
            + '</div>'
            + '<label class="plugin-switch" title="' + (canToggle ? 'Вкл/выкл' : 'Только для админа') + '">'
            +   '<input type="checkbox" ' + (p.enabled ? 'checked' : '') + (canToggle ? '' : ' disabled') + ' data-plug="' + esc(p.name) + '">'
            +   '<span class="plugin-switch-track"><span class="plugin-switch-knob"></span></span>'
            + '</label>'
            + '</div>';
    });
    wrap.innerHTML = html;
    wrap.querySelectorAll('input[data-plug]').forEach(function(cb){
        cb.addEventListener('change', function(){
            var name = this.getAttribute('data-plug');
            var enabled = this.checked;
            var self = this;
            api('/api/settings/plugins/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name, enabled: enabled}),
            }).then(function(d){
                if (!d.success) throw new Error(d.error || 'Ошибка');
                notify('✅ ' + (enabled ? 'Включён' : 'Отключён') + ': ' + name + ' — перезапустите сервер', 'success');
                var card = self.closest('.plugin-card');
                if (card) {
                    card.classList.toggle('on', enabled);
                    card.classList.toggle('off', !enabled);
                }
            }).catch(function(e){
                self.checked = !enabled;
                notify('❌ ' + (e.message || 'Ошибка'), 'error');
            });
        });
    });
}

function loadAudit(){    var kind = $('auditKindFilter') ? $('auditKindFilter').value : '';
    var url = '/api/settings/audit?limit=500';
    if (kind) url += '&kind=' + encodeURIComponent(kind);
    api(url).then(function(d){
        renderAuditV2(d.items || []);
    }).catch(function(e){
        var wrap = $('auditList');
        if (wrap) wrap.innerHTML = '<div class="dict-empty" style="color:#e74c3c;">❌ ' + esc(e.message || 'Ошибка') + '</div>';
    });
}

var AUDIT_KIND = {
    create: { icon: '➕', label: 'Создание', cls: 'k-create' },
    update: { icon: '✏️', label: 'Изменение', cls: 'k-update' },
    delete: { icon: '🗑', label: 'Удаление', cls: 'k-delete' },
    login:  { icon: '🔑', label: 'Вход',     cls: 'k-login'  }
};
var AUDIT_ENTITY = {
    employee:   'Сотрудник',
    task:       'Задача',
    user:       'Пользователь',
    department: 'Отдел',
    team:       'Команда',
    holiday:    'Праздник',
    log:        'Отметка',
    log_copy:   'Копирование дня',
    log_clear:  'Очистка дня',
    config:     'Настройки',
    vacation:   'Отсутствие',
    plugin:     'Плагин'
};
var AUDIT_WD = ['вс','пн','вт','ср','чт','пт','сб'];

function _auditDayKey(ts){
    return (ts || '').slice(0, 10);
}
function _auditTimePart(ts){
    var t = (ts || '').split(' ');
    return t.length > 1 ? t[1] : '';
}
function _auditDayHuman(iso){
    try {
        var p = iso.split('-');
        var y = parseInt(p[0],10), m = parseInt(p[1],10), d = parseInt(p[2],10);
        var dt = new Date(y, m-1, d);
        return String(d).padStart(2,'0') + '.' + String(m).padStart(2,'0') + '.' + y +
            ' · ' + AUDIT_WD[dt.getDay()];
    } catch(e) { return iso; }
}
function _auditDetails(item){
    var raw = item.details || '';
    if (!raw) return null;
    try { var o = JSON.parse(raw); return (o && typeof o === 'object' && !Array.isArray(o)) ? o : null; }
    catch(e) { return null; }
}
function _auditSummary(item){
    var ent = AUDIT_ENTITY[item.entity] || item.entity || '';
    var eid = item.entity_id || '';
    var label = (AUDIT_KIND[item.kind] || {}).label || item.kind || '';
    return {
        action: label,
        entityLabel: ent ? (ent + (eid ? ' · ' + eid : '')) : ''
    };
}
function renderAuditV2(items){
    var wrap = $('auditList');
    if (!wrap) return;
    if (!items.length) {
        wrap.innerHTML = '<div class="dict-empty">Нет событий за выбранный фильтр</div>';
        return;
    }
    var groups = {};
    var order = [];
    items.forEach(function(it){
        var dk = _auditDayKey(it.ts);
        if (!groups[dk]) { groups[dk] = []; order.push(dk); }
        groups[dk].push(it);
    });
    order.sort(function(a,b){ return b.localeCompare(a); });
    var html = '';
    order.forEach(function(dk){
        var arr = groups[dk];
        html += '<div class="audit-day-group">';
        html += '<div class="audit-day-head">'
              +   '<span class="audit-day-date">' + esc(_auditDayHuman(dk)) + '</span>'
              +   '<span class="audit-day-count">' + arr.length + ' ' + (arr.length === 1 ? 'событие' : (arr.length < 5 ? 'события' : 'событий')) + '</span>'
              + '</div>';
        html += '<div class="audit-day-items">';
        arr.forEach(function(it){
            var k = AUDIT_KIND[it.kind] || { icon: '•', label: it.kind, cls: 'k-other' };
            var sum = _auditSummary(it);
            var det = _auditDetails(it);
            var detHtml = '';
            if (det) {
                detHtml = '<div class="audit-details" hidden>'
                    + '<table class="audit-details-table">'
                    + Object.keys(det).map(function(key){
                        var v = det[key];
                        if (v == null) v = '';
                        if (typeof v === 'object') v = JSON.stringify(v, null, 0);
                        return '<tr><td class="ad-key">' + esc(key) + '</td>'
                             + '<td class="ad-val">' + esc(String(v)) + '</td></tr>';
                    }).join('')
                    + '</table></div>';
                }
            html += '<div class="audit-row ' + k.cls + (det ? ' expandable' : '') + '" data-id="' + (it.id || '') + '">'
                  +   '<span class="audit-kind-icon ' + k.cls + '" title="' + esc(k.label) + '">' + k.icon + '</span>'
                  +   '<div class="audit-main">'
                  +     '<div class="audit-line1">'
                  +       '<span class="audit-user">' + esc(it.username || '—') + '</span>'
                  +       '<span class="audit-sep">·</span>'
                  +       '<span class="audit-action">' + esc(sum.action) + '</span>'
                  +       (sum.entityLabel ? '<span class="audit-entity">' + esc(sum.entityLabel) + '</span>' : '')
                  +     '</div>'
                  +     '<div class="audit-line2">'
                  +       '<span class="audit-time">' + esc(_auditTimePart(it.ts || '')) + '</span>'
                  +     '</div>'
                  +   '</div>'
                  +   (det ? '<span class="audit-expand">▾</span>' : '')
                  + '</div>'
                  + detHtml;
        });
        html += '</div></div>';
    });
    wrap.innerHTML = html;
    wrap.querySelectorAll('.audit-row.expandable').forEach(function(row){
        row.addEventListener('click', function(){
            var det = this.nextElementSibling;
            if (!det || !det.classList.contains('audit-details')) return;
            var hidden = det.hasAttribute('hidden');
            if (hidden) det.removeAttribute('hidden');
            else det.setAttribute('hidden', '');
            this.classList.toggle('expanded', hidden);
        });
    });
}$('auditRefreshBtn').addEventListener('click', loadAudit);if ($('pluginsRefreshBtn')) $('pluginsRefreshBtn').addEventListener('click', loadPluginsManager);
$('auditKindFilter').addEventListener('change', loadAudit);

$('pwdSaveBtn').addEventListener('click', function(){
    var oldp = $('pwd_old').value, np = $('pwd_new').value, np2 = $('pwd_new2').value;
    if (!oldp || !np) { notify('❌ Заполните все поля', 'error'); return; }
    if (np !== np2) { notify('❌ Пароли не совпадают', 'error'); return; }
    if (np.length < 6) { notify('❌ parol минимум 6 символов', 'error'); return; }
    api('/api/settings/kody', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ old_kody: oldp, new_kody: np })
    }).then(function(d){
        if (!d.success) throw new Error(d.error || 'Ошибка');
        notify('✅ parol изменён', 'success');
        $('pwd_old').value = $('pwd_new').value = $('pwd_new2').value = '';
    }).catch(function(e){ notify('❌ ' + e.message, 'error'); });
});

function loadAbout(){
    api('/api/settings/db_info').then(function(d){
        var el = $('aboutInfo');
        if (!el) return;
        el.innerHTML = ''
            + '<div><b>Версия:</b> 1.4</div>'
            + '<div><b>База данных:</b> <code>' + esc(d.db_path) + '</code></div>'
            + '<div><b>Сервер:</b> ' + esc(d.host) + ':' + esc(String(d.port)) + '</div>'
            + '<div style="margin-top:8px;color:var(--trk-meta);font-size:0.82rem;">'
            + 'SQLite. При размещении на сетевой папке — journal_mode=DELETE и busy_timeout=30s.'
            + '</div>';
    }).catch(function(e){
        var el = $('aboutInfo'); if (el) el.textContent = '❌ ' + e.message;
    });
}

document.querySelectorAll('[data-close]').forEach(function(b){
    b.addEventListener('click', function(){
        var m = $(this.getAttribute('data-close')); if (m) m.classList.remove('active');
    });
});
document.querySelectorAll('.modal').forEach(function(m){
    m.addEventListener('click', function(e){
        if (e.target === m) m.classList.remove('active');
    });
});
document.addEventListener('keydown', function(e){
    if (e.key === 'Escape') document.querySelectorAll('.modal.active').forEach(function(m){ m.classList.remove('active'); });
});

$('addUserBtn').addEventListener('click', function(){ openUserModal(null); });
$('saveUserBtn').addEventListener('click', saveUser);

/* PATCH v1.0.4: экспорт для патчей, которым нужен прямой доступ */
window.__trkOpenUserModal = openUserModal;
window.__trkDeleteUser = deleteUser;
window.__trkGetUsersState = function(){ return state.users; };
window.addEventListener('DOMContentLoaded', function(){
    loadUsers().then(function(){
        return api('/api/tracker/state').then(function(d){
            state.employees = d.employees || [];
            renderUsers();
        });
    });
});

})();
/* ============================================================
   PATCH 2026-10-06 — Админка: enhancement (аватары, KPI)
   ============================================================ */
(function(){
    'use strict';

    function initialsFromText(text) {
        var clean = String(text || '').replace(/\(отключён\)/g, '').replace(/[\*]+/g, '').trim();
        var parts = clean.split(/\s+/).filter(Boolean);
        if (!parts.length) return '?';
        var s = (parts[0][0] || '?');
        if (parts[1] && parts[1][0]) s += parts[1][0];
        return s.toUpperCase();
    }

    function enhanceUsers(list) {
        if (!list) return;

        list.querySelectorAll('.settings-user').forEach(function(row){
            if (row.querySelector('.su-avatar')) return;
            var nameEl = row.querySelector('.su-name');
            var txt = nameEl ? nameEl.textContent : '';
            var av = document.createElement('div');
            av.className = 'su-avatar';
            av.textContent = initialsFromText(txt);
            row.insertBefore(av, row.firstChild);
        });

        var all = list.querySelectorAll('.settings-user').length;
        var active = list.querySelectorAll('.settings-user:not(.inactive)').length;
        var admins = list.querySelectorAll('.settings-user .su-role.admin').length;

        var parent = list.parentNode;
        var kpi = parent ? parent.querySelector('.su-kpi') : null;
        if (!kpi && parent) {
            kpi = document.createElement('div');
            kpi.className = 'su-kpi';
            parent.insertBefore(kpi, list);
        }
        if (!kpi) return;
        kpi.innerHTML =
            '<div class="su-kpi-card"><div class="su-kpi-value">' + all + '</div><div class="su-kpi-label">Всего</div></div>'
          + '<div class="su-kpi-card"><div class="su-kpi-value">' + active + '</div><div class="su-kpi-label">Активных</div></div>'
          + '<div class="su-kpi-card"><div class="su-kpi-value">' + admins + '</div><div class="su-kpi-label">Админов</div></div>';
    }

    function hook(list) {
        var obs = new MutationObserver(function(){ enhanceUsers(list); });
        obs.observe(list, { childList: true, subtree: true });
        enhanceUsers(list);
    }

    function boot() {
        var list = document.getElementById('usersList');
        if (list) { hook(list); return; }
        var rootObs = new MutationObserver(function(){
            var t = document.getElementById('usersList');
            if (t) { rootObs.disconnect(); hook(t); }
        });
        rootObs.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
/* ============================================================
   PATCH 2026-10-06 — Пользователи: клик по карточке = редактирование
   ============================================================ */
(function(){
    'use strict';

    document.addEventListener('click', function(e){
        var card = e.target && e.target.closest && e.target.closest('#usersList .settings-user');
        if (!card) return;
        if (e.target.closest('.dict-action-btn[data-act="delete"]')) return;
        if (e.target.closest('a, input, select, textarea')) return;
        var id = parseInt(card.getAttribute('data-id'), 10);
        if (!id) return;
        e.preventDefault();
        e.stopPropagation();
        // PATCH v1.0.4: прямой вызов openUserModal вместо click по скрытой кнопке
        var _users = (typeof window.__trkGetUsersState === 'function') ? window.__trkGetUsersState() : null;
        var _u = _users ? _users.find(function(x){ return x.id === id; }) : null;
        if (_u && typeof window.__trkOpenUserModal === 'function') {
            window.__trkOpenUserModal(_u);
        } else {
            var editBtn = card.querySelector('.dict-action-btn[data-act="edit"]');
            if (editBtn) editBtn.click();
        }
    }, true);

    function mark() {
        var wrap = document.getElementById('usersList');
        if (!wrap) return;
        wrap.querySelectorAll('.settings-user').forEach(function(card){
            if (card.querySelector('.dict-action-btn[data-act="edit"]')) {
                card.classList.add('su-clickable');
            } else {
                card.classList.remove('su-clickable');
            }
        });
    }

    function attachObserver() {
        var wrap = document.getElementById('usersList');
        if (!wrap || wrap._suClickObserver) return;
        wrap._suClickObserver = new MutationObserver(mark);
        wrap._suClickObserver.observe(wrap, { childList: true, subtree: true });
        mark();
    }

    function boot() {
        attachObserver();
        setTimeout(attachObserver, 800);
        setTimeout(mark, 1500);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
/* ============================================================
   PATCH 32 — Резервные копии БД в админке
   ============================================================ */
(function(){
    'use strict';
    function _fmtSize(n){
        n = Number(n) || 0;
        if (n < 1024) return n + ' Б';
        if (n < 1024*1024) return Math.round(n/1024) + ' КБ';
        return (n/1024/1024).toFixed(2) + ' МБ';
    }
    function renderList(items){
        var wrap = document.getElementById('dbBackupList');
        if (!wrap) return;
        if (!items || !items.length) {
            wrap.innerHTML = '<div class="dict-empty">Бэкапов пока нет</div>';
            return;
        }
        wrap.innerHTML = items.map(function(it){
            return '<div class="db-backup-row">'
                 + '<span class="db-backup-name">' + it.name + '</span>'
                 + '<span class="db-backup-meta">' + it.mtime + ' · ' + _fmtSize(it.size) + '</span>'
                 + '<a class="db-backup-dl" href="/api/settings/db_backup/download?name=' + encodeURIComponent(it.name) + '" download>⬇ Скачать</a>'
                 + '</div>';
        }).join('');
    }
    function loadList(){
        var csrf = window.REESTR_CSRF || '';
        fetch('/api/settings/db_backup/list', {
            credentials: 'same-origin',
            headers: csrf ? {'X-CSRF-Token': csrf} : {}
        }).then(function(r){ return r.json(); }).then(function(d){
            if (d && d.success) renderList(d.items || []);
        }).catch(function(){});
    }
    function createNow(){
        var csrf = window.REESTR_CSRF || '';
        var btn = document.getElementById('dbBackupNowBtn');
        if (btn) btn.disabled = true;
        fetch('/api/settings/db_backup', {
            method: 'POST',
            credentials: 'same-origin',
            headers: Object.assign({'Content-Type': 'application/json'}, csrf ? {'X-CSRF-Token': csrf} : {})
        }).then(function(r){ return r.json().then(function(j){ return {ok: r.ok, d: j}; }); })
        .then(function(res){
            if (btn) btn.disabled = false;
            if (res.ok && res.d && res.d.success) {
                if (typeof notify === 'function') notify('✅ Бэкап создан', 'success');
                loadList();
            } else {
                if (typeof notify === 'function') notify('❌ ' + ((res.d && res.d.error) || 'Ошибка'), 'error');
            }
        }).catch(function(e){
            if (btn) btn.disabled = false;
            if (typeof notify === 'function') notify('❌ ' + (e.message || 'Ошибка'), 'error');
        });
    }
    function boot(){
        var b = document.getElementById('dbBackupNowBtn');
        if (b && !b._bkHooked) {
            b._bkHooked = true;
            b.addEventListener('click', createNow);
        }
        var r = document.getElementById('dbBackupRefreshBtn');
        if (r && !r._bkHooked) {
            r._bkHooked = true;
            r.addEventListener('click', loadList);
        }
        loadList();
    }
    document.addEventListener('click', function(e){
        if (e.target && e.target.closest && e.target.closest('.settings-tab[data-tab="db"]')) {
            setTimeout(boot, 200);
        }
    });
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ setTimeout(boot, 500); });
    else setTimeout(boot, 500);
})();

/* ============================================================
   PATCH v1.0.16 — надёжные клики в админке пользователей
   Дубль-страховка: если v1.0.4-обработчик не сработал,
   этот ловит клики и вызывает экспортированные функции.
   ============================================================ */
(function(){
'use strict';
if (window.__trkUsersClickHardening) return;
window.__trkUsersClickHardening = true;

function _findUser(id) {
    var get = window.__trkGetUsersState;
    var users = (typeof get === 'function') ? (get() || []) : [];
    for (var i = 0; i < users.length; i++) {
        if (users[i] && users[i].id === id) return users[i];
    }
    return null;
}

function _openUserModal(u) {
    var open = window.__trkOpenUserModal;
    if (typeof open !== 'function') {
        console.error('[users-hardening] __trkOpenUserModal не определён');
        return false;
    }
    try { open(u); return true; } catch (e) {
        console.error('[users-hardening] openUserModal упал:', e);
        return false;
    }
}

function _deleteUser(id) {
    var del = window.__trkDeleteUser;
    if (typeof del !== 'function') {
        console.error('[users-hardening] __trkDeleteUser не определён');
        return false;
    }
    try { del(id); return true; } catch (e) {
        console.error('[users-hardening] deleteUser упал:', e);
        return false;
    }
}

function _isUserModalOpen() {
    var m = document.getElementById('userModal');
    return !!(m && m.classList.contains('active'));
}

document.addEventListener('click', function(e){
    if (!e.target || !e.target.closest) return;

    // 1) Кнопка «Добавить пользователя»
    if (e.target.closest('#addUserBtn')) {
        if (_isUserModalOpen()) return;
        e.preventDefault();
        e.stopPropagation();
        _openUserModal(null);
        return;
    }

    // 2) Кнопка «Удалить» на карточке
    var delBtn = e.target.closest('#usersList .settings-user .dict-action-btn[data-act=\"delete\"]');
    if (delBtn) {
        var row = delBtn.closest('.settings-user');
        var id = row ? parseInt(row.getAttribute('data-id'), 10) : 0;
        if (!id) return;
        e.preventDefault();
        e.stopPropagation();
        _deleteUser(id);
        return;
    }

    // 3) Клик по карточке (не по кнопке удаления, не по inputs)
    var card = e.target.closest('#usersList .settings-user');
    if (card) {
        if (e.target.closest('a, input, select, textarea')) return;
        if (e.target.closest('button:not([data-act=\"edit\"])')) return;
        var id2 = parseInt(card.getAttribute('data-id'), 10);
        if (!id2) return;
        if (_isUserModalOpen()) return;
        e.preventDefault();
        e.stopPropagation();
        var u = _findUser(id2);
        if (u) _openUserModal(u);
        return;
    }
}, true);

})();


/* ============================================================
   PATCH v1.0.27 — предупреждение при смене пути к БД
   Если сервер вернул 409 (в новом файле уже есть данные),
   спрашиваем про перезапись и повторяем с force_empty=true.
   ============================================================ */
(function(){
'use strict';
if (window.__trkDbPathV127) return;
window.__trkDbPathV127 = true;

var _orig = window.fetch;
if (typeof _orig !== 'function') return;

window.fetch = function(url, opts) {
    var isDbPathSave = (typeof url === 'string' && url.indexOf('/api/settings/db_path/save') !== -1);
    if (!isDbPathSave || !opts || (opts.method || 'GET').toUpperCase() !== 'POST') {
        return _orig.apply(this, arguments);
    }
    var self = this;
    return _orig.apply(this, arguments).then(function(r){
        if (r.status !== 409) return r;
        return r.clone().json().then(function(d){
            if (!d || !d.exists_with_data) return r;
            var ok = confirm(
                'По новому пути уже лежит БД с данными (' + (d.users_count||0) + ' пользователей).\n\n' +
                'Перезаписать её текущей базой?\n' +
                '(Старая база по новому пути будет потеряна.)'
            );
            if (!ok) {
                return new Response(JSON.stringify({success:false, error:'cancelled'}), {
                    status: 200, headers: {'Content-Type':'application/json'}
                });
            }
            var payload;
            try { payload = JSON.parse(opts.body || '{}'); } catch(e) { payload = {}; }
            payload.force_empty = true;
            payload.copy_data = true;
            var newOpts = Object.assign({}, opts, { body: JSON.stringify(payload) });
            return _orig.call(self, url, newOpts);
        });
    });
};
})();

/* ============================================================
   PATCH 1.0.3-fix — Управление путём к сетевой папке обновлений
   -------------------------------------------------------------
   Автономный IIFE. Использует fetch напрямую, потому что api()
   и notify() из первого IIFE settings.js недоступны в этой области
   видимости (они локальные, не в window).
   ============================================================ */
(function(){
    'use strict';
    if (window.__trkNetUpdatePathV103Fix) return;
    window.__trkNetUpdatePathV103Fix = true;

    function _toast(msg, kind){
        if (typeof window.__trackerNotify === 'function') {
            try { window.__trackerNotify(msg, kind); return; } catch(e){}
        }
        var n = document.getElementById('trackerNotif');
        if (!n) {
            n = document.createElement('div');
            n.id = 'trackerNotif';
            n.className = 'tracker-notification';
            document.body.appendChild(n);
        }
        n.textContent = msg;
        n.className = 'tracker-notification show' + (kind === 'error' ? ' error' : '');
        clearTimeout(n._t);
        n._t = setTimeout(function(){ n.classList.remove('show'); }, 4000);
    }

    function _csrf(){ return window.REESTR_CSRF || ''; }

    function _load(){
        var h = {};
        if (_csrf()) h['X-CSRF-Token'] = _csrf();
        fetch('/api/settings/net_update_path', {
            credentials: 'same-origin',
            headers: h,
        }).then(function(r){
            if (!r.ok) return r.text().then(function(t){
                throw new Error('HTTP ' + r.status + ': ' + t.slice(0, 200));
            });
            return r.json();
        }).then(function(d){
            if (!d || !d.success) return;
            var inp = document.getElementById('net_update_path_input');
            if (inp) inp.value = d.path || '';
            var note = document.getElementById('netUpdatePathNote');
            if (note) {
                var base = 'Абсолютный путь к папке с JSON-файлами патчей. Изменения вступают в силу без перезапуска сервера.';
                if (typeof d.enabled === 'boolean') {
                    note.textContent = base + (d.enabled ? ' Сейчас: включено.' : ' Сейчас: ОТКЛЮЧЕНО.');
                }
            }
        }).catch(function(e){
            console.error('[net_update_path] load failed:', e);
        });
    }

    function _save(){
        var inp = document.getElementById('net_update_path_input');
        if (!inp) return;
        var p = (inp.value || '').trim();
        if (!p) { _toast('❌ Укажите путь', 'error'); return; }
        if (!confirm('Сохранить новый путь к обновлениям?\n\nИзменения вступают в силу без перезапуска сервера.')) return;
        var h = {'Content-Type': 'application/json'};
        if (_csrf()) h['X-CSRF-Token'] = _csrf();
        fetch('/api/settings/net_update_path', {
            method: 'POST',
            credentials: 'same-origin',
            headers: h,
            body: JSON.stringify({path: p}),
        }).then(function(r){
            if (!r.ok) return r.text().then(function(t){
                var m = 'HTTP ' + r.status;
                try { var j = JSON.parse(t); if (j.error) m += ' — ' + j.error; } catch(e){}
                throw new Error(m);
            });
            return r.json();
        }).then(function(d){
            if (!d || !d.success) throw new Error((d && d.error) || 'Ошибка');
            _toast('✅ Путь сохранён', 'success');
            _load();
        }).catch(function(e){
            _toast('❌ ' + (e.message || 'Ошибка'), 'error');
        });
    }

    function _wire(){
        var btn = document.getElementById('netUpdatePathSaveBtn');
        if (btn && !btn._nuHooked) {
            btn._nuHooked = true;
            btn.addEventListener('click', _save);
        }
        var inp = document.getElementById('net_update_path_input');
        if (inp && !inp._nuHooked) {
            inp._nuHooked = true;
            inp.addEventListener('keydown', function(e){
                if (e.key === 'Enter') { e.preventDefault(); _save(); }
            });
        }
    }

    document.addEventListener('click', function(e){
        if (e.target && e.target.closest && e.target.closest('.settings-tab[data-tab="db"]')) {
            setTimeout(function(){ _wire(); _load(); }, 150);
        }
    });

    function _boot(){
        setTimeout(function(){ _wire(); _load(); }, 300);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _boot);
    } else {
        _boot();
    }
})();



/* ============================================================
   PATCH 1.0.5 — флаг stats_ignore_future
   Автономный IIFE: fetch напрямую, свой тост.
   ============================================================ */
(function(){
    'use strict';
    if (window.__trkStatsIgnoreFutureV105) return;
    window.__trkStatsIgnoreFutureV105 = true;

    function _csrf(){ return window.REESTR_CSRF || ''; }
    function _toast(msg, kind){
        var n = document.getElementById('trackerNotif');
        if (!n) return;
        n.textContent = msg;
        n.className = 'tracker-notification show' + (kind === 'error' ? ' error' : '');
        clearTimeout(n._t);
        n._t = setTimeout(function(){ n.classList.remove('show'); }, 4000);
    }

    function _load(){
        var h = {};
        if (_csrf()) h['X-CSRF-Token'] = _csrf();
        fetch('/api/settings/stats_ignore_future', {credentials: 'same-origin', headers: h})
            .then(function(r){ return r.ok ? r.json() : null; })
            .then(function(d){
                if (!d || !d.success) return;
                var cb = document.getElementById('statsIgnoreFutureCb');
                if (cb) cb.checked = !!d.value;
            })
            .catch(function(){});
    }

    function _save(v){
        var h = {'Content-Type': 'application/json'};
        if (_csrf()) h['X-CSRF-Token'] = _csrf();
        fetch('/api/settings/stats_ignore_future', {
            method: 'POST', credentials: 'same-origin', headers: h,
            body: JSON.stringify({value: !!v})
        }).then(function(r){
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }).then(function(d){
            if (!d || !d.success) throw new Error((d && d.error) || 'Ошибка');
            _toast('✅ Настройка сохранена');
        }).catch(function(e){ _toast('❌ ' + (e.message || 'Ошибка'), 'error'); });
    }

    function _wire(){
        var cb = document.getElementById('statsIgnoreFutureCb');
        if (!cb || cb._v105Wired) return;
        cb._v105Wired = true;
        cb.addEventListener('change', function(){ _save(this.checked); });
        _load();
    }

    document.addEventListener('click', function(e){
        if (e.target && e.target.closest && e.target.closest('.settings-tab[data-tab="db"]')) {
            setTimeout(_wire, 150);
        }
    });
    function _boot(){ setTimeout(_wire, 300); }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _boot);
    } else { _boot(); }
})();

/* ============================================================
   PATCH 1.0.7 — флаг excel_mask_names
   ============================================================ */
(function(){
    'use strict';
    if (window.__trkExcelMaskNamesV107) return;
    window.__trkExcelMaskNamesV107 = true;

    function _csrf(){ return window.REESTR_CSRF || ''; }
    function _toast(msg, kind){
        var n = document.getElementById('trackerNotif');
        if (!n) return;
        n.textContent = msg;
        n.className = 'tracker-notification show' + (kind === 'error' ? ' error' : '');
        clearTimeout(n._t);
        n._t = setTimeout(function(){ n.classList.remove('show'); }, 4000);
    }

    function _load(){
        var h = {};
        if (_csrf()) h['X-CSRF-Token'] = _csrf();
        fetch('/api/settings/excel_mask_names', {credentials: 'same-origin', headers: h})
            .then(function(r){ return r.ok ? r.json() : null; })
            .then(function(d){
                if (!d || !d.success) return;
                var cb = document.getElementById('excelMaskNamesCb');
                if (cb) cb.checked = !!d.value;
            })
            .catch(function(){});
    }

    function _save(v){
        var h = {'Content-Type': 'application/json'};
        if (_csrf()) h['X-CSRF-Token'] = _csrf();
        fetch('/api/settings/excel_mask_names', {
            method: 'POST', credentials: 'same-origin', headers: h,
            body: JSON.stringify({value: !!v})
        }).then(function(r){
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        }).then(function(d){
            if (!d || !d.success) throw new Error((d && d.error) || 'Ошибка');
            _toast('✅ Настройка сохранена');
        }).catch(function(e){ _toast('❌ ' + (e.message || 'Ошибка'), 'error'); });
    }

    function _wire(){
        var cb = document.getElementById('excelMaskNamesCb');
        if (!cb || cb._v107Wired) return;
        cb._v107Wired = true;
        cb.addEventListener('change', function(){ _save(this.checked); });
        _load();
    }

    document.addEventListener('click', function(e){
        if (e.target && e.target.closest && e.target.closest('.settings-tab[data-tab="db"]')) {
            setTimeout(_wire, 150);
        }
    });
    function _boot(){ setTimeout(_wire, 300); }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _boot);
    } else { _boot(); }
})();

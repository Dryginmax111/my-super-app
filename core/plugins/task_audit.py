"""plugins/task_audit.py — история изменений задачи."""
__version__ = '1.1'
__description__ = 'Task Audit: хронология изменений задач, вкладка «История»'

import json
from datetime import datetime
from flask import jsonify, Response, request

TRACKED = ['name', 'status', 'deadline', 'start_date', 'completed_at',
           'tags', 'assignees', 'department_ids']

# Сколько последних записей хранить на задачу (обрезка при переполнении)
KEEP_PER_TASK = 100
# Гистерезис: чистим, когда записей станет больше KEEP_PER_TASK + буфер
CLEANUP_AT = KEEP_PER_TASK + 50


def _ensure_table(db):
    try:
        db.exec('''
            CREATE TABLE IF NOT EXISTS task_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                changes TEXT
            )''')
        db.exec('CREATE INDEX IF NOT EXISTS idx_task_audit_task ON task_audit (task_id)')
    except Exception as e:
        print('[task_audit] ensure table failed: ' + str(e))


def _snapshot(db, task_id):
    try:
        t = db.query_one('SELECT * FROM tasks WHERE id=?', (task_id,))
        if not t:
            return None
        tags = [r.get('tag') for r in db.query('SELECT tag FROM task_tags WHERE task_id=?', (task_id,))]
        assigns = [r.get('employee_id') for r in db.query('SELECT employee_id FROM task_assignees WHERE task_id=?', (task_id,))]
        deps = [r.get('department_id') for r in db.query('SELECT department_id FROM task_departments WHERE task_id=?', (task_id,))]
        t['tags'] = sorted([x for x in tags if x])
        t['assignees'] = sorted([x for x in assigns if x])
        t['department_ids'] = sorted([x for x in deps if x])
        return t
    except Exception as e:
        print('[task_audit] snapshot failed: ' + str(e))
        return None


def _slim(t):
    return {k: t.get(k) for k in TRACKED}


def _diff(old, new):
    if not old:
        return {'created': True}
    out = {}
    for k in TRACKED:
        ov = old.get(k)
        nv = new.get(k)
        if k in ('tags', 'assignees', 'department_ids'):
            ov = sorted(ov or [])
            nv = sorted(nv or [])
            if ov != nv:
                out[k] = {'old': ov, 'new': nv}
        else:
            if (ov or '') != (nv or ''):
                out[k] = {'old': ov, 'new': nv}
    return out


def _log(db, task_id, user, changes):
    if not changes:
        return
    try:
        db.exec(
            'INSERT INTO task_audit (task_id, ts, user_id, username, changes) VALUES (?,?,?,?,?)',
            (task_id,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             (user or {}).get('id'),
             (user or {}).get('username', '') or (user or {}).get('display_name', ''),
             json.dumps(changes, ensure_ascii=False)[:4000]),
        )
    except Exception as e:
        print('[task_audit] log failed: ' + str(e))


def _maybe_cleanup(db, task_id):
    """Обрезает старые записи истории для задачи, если их накопилось много."""
    try:
        row = db.query_one('SELECT COUNT(*) AS n FROM task_audit WHERE task_id=?', (task_id,))
        n = row.get('n') if row else 0
        if n <= CLEANUP_AT:
            return
        db.exec(
            'DELETE FROM task_audit WHERE task_id=? AND id NOT IN '
            '(SELECT id FROM task_audit WHERE task_id=? ORDER BY id DESC LIMIT ?)',
            (task_id, task_id, KEEP_PER_TASK),
        )
    except Exception as e:
        print('[task_audit] cleanup failed: ' + str(e))


def register(app, db, hooks):
    print('[task_audit] v' + __version__ + ' · ' + __description__)
    _ensure_table(db)

    def on_task_save(user=None, task_id=None, created=False, **ctx):
        if not task_id:
            return
        try:
            new = _snapshot(db, task_id)
            if not new:
                return

            # При создании сразу сохраняем полный снимок — иначе первое
            # изменение после создания не даст diff и запишется как baseline.
            if created:
                _log(db, task_id, user, {
                    'created': True,
                    'name': new.get('name', ''),
                    'after': _slim(new),
                })
                return

            # Ищем предыдущий снимок
            prev = db.query_one(
                'SELECT changes FROM task_audit WHERE task_id=? ORDER BY id DESC LIMIT 1',
                (task_id,),
            )
            prev_snap = None
            if prev:
                try:
                    p = json.loads(prev.get('changes') or '{}')
                    prev_snap = p.get('after')
                except Exception:
                    pass

            if not prev_snap:
                # Не было снимка — пишем baseline, чтобы со следующего save был diff
                _log(db, task_id, user, {'baseline': True, 'after': _slim(new)})
                return

            changes = _diff(prev_snap, new)
            if not changes:
                # Ничего не изменилось — не создаём шум
                return
            _log(db, task_id, user, {'after': _slim(new), 'diff': changes})
            _maybe_cleanup(db, task_id)
        except Exception as e:
            print('[task_audit] hook failed: ' + str(e))

    hooks.on('on_task_save', on_task_save)

    def _check_auth():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u:
                return None
            if user_has(db, u, 'tab.summary') or user_has(db, u, 'action.task.edit'):
                return u
        except Exception:
            return None
        return None

    @app.route('/api/plugins/task_audit/history', methods=['GET'])
    def _history():
        if not _check_auth():
            return jsonify({'success': False, 'error': 'forbidden'}), 403
        tid = (request.args.get('task') or '').strip()
        if not tid:
            return jsonify({'success': False, 'error': 'no task'}), 400
        rows = db.query(
            'SELECT * FROM task_audit WHERE task_id=? ORDER BY id DESC LIMIT 200',
            (tid,),
        )
        items = []
        for r in rows:
            try:
                ch = json.loads(r.get('changes') or '{}')
            except Exception:
                ch = {}
            items.append({
                'id': r.get('id'),
                'ts': r.get('ts'),
                'username': r.get('username') or '—',
                'changes': ch,
            })
        return jsonify({'success': True, 'items': items})

    _JS = r'''
(function(){
'use strict';

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function fmtVal(v){if(Array.isArray(v))return v.length?v.join(', '):'—';return (v===''||v==null)?'—':String(v);}
function fmtChange(key,ch){
    var labels={status:'Статус',deadline:'Дедлайн',start_date:'Начало',completed_at:'Завершено',tags:'Теги',assignees:'Исполнители',department_ids:'Отделы',name:'Название'};
    var lbl=labels[key]||key;
    return '<b>'+lbl+'</b>: <span style="color:#ec7063;">'+esc(fmtVal(ch.old))+'</span> → <span style="color:#58d68d;">'+esc(fmtVal(ch.new))+'</span>';
}
function render(items){
    if(!items.length)return '<div class="tah-empty">Изменений пока нет</div>';
    return items.map(function(it){
        var ch=it.changes||{};
        var body='';
        if(ch.created){body='<div class="tah-line">➕ Задача создана</div>';}
        else if(ch.baseline){body='<div class="tah-line">📌 Первая запись</div>';}
        else if(ch.diff){
            var keys=Object.keys(ch.diff);
            if(!keys.length)return '';
            body=keys.map(function(k){return '<div class="tah-line">'+fmtChange(k,ch.diff[k])+'</div>';}).join('');
        } else {body='<div class="tah-line" style="opacity:0.7;">изменение</div>';}
        return '<div class="tah-row"><div class="tah-head"><span class="tah-ts">'+esc(it.ts)+'</span><span class="tah-user">'+esc(it.username)+'</span></div><div class="tah-body">'+body+'</div></div>';
    }).join('');
}

/* --- Захват id задачи при открытии карточки --- */
(function installTaskIdHook(){
    var orig = window.__trkOpenTaskCardModal;
    if (typeof orig !== 'function' || orig._tahTaskIdHooked) return;
    var w = function(taskId){
        window.__trkLastTaskCardId = taskId || '';
        return orig.apply(this, arguments);
    };
    w._tahTaskIdHooked = true;
    window.__trkOpenTaskCardModal = w;
})();

function currentTaskId(){
    return window.__trkLastTaskCardId || '';
}

function inject(){
    var m=document.getElementById('taskCardModal');
    if(!m||m._tahHooked)return;
    m._tahHooked=true;
    var body=m.querySelector('.modal-content');
    if(!body)return;
    var listWrap=document.getElementById('taskCardEmployees');
    if(!listWrap||!listWrap.parentNode)return;
    if(document.getElementById('taskCardHistory'))return;
    var tabs=document.createElement('div');
    tabs.className='tah-tabs';
    tabs.innerHTML='<button class="tah-tab active" data-tab="team">👥 Исполнители</button><button class="tah-tab" data-tab="history">📜 История</button>';
    var hist=document.createElement('div');
    hist.id='taskCardHistory';
    hist.style.display='none';
    listWrap.parentNode.insertBefore(tabs,listWrap);
    listWrap.parentNode.insertBefore(hist,listWrap.nextSibling);
    tabs.addEventListener('click',function(e){
        var b=e.target.closest('.tah-tab');if(!b)return;
        var t=b.getAttribute('data-tab');
        tabs.querySelectorAll('.tah-tab').forEach(function(x){x.classList.toggle('active',x===b);});
        if(t==='history'){
            listWrap.style.display='none';
            hist.style.display='';
            loadHistory();
        } else {
            listWrap.style.display='';
            hist.style.display='none';
        }
    });
}

function loadHistory(){
    var hist=document.getElementById('taskCardHistory');
    if(!hist)return;
    hist.innerHTML='<div class="tah-empty">Загрузка…</div>';
    var tid=currentTaskId();
    if(!tid){hist.innerHTML='<div class="tah-empty">Не удалось определить задачу</div>';return;}
    fetch('/api/plugins/task_audit/history?task='+encodeURIComponent(tid),{credentials:'same-origin'})
        .then(function(r){return r.json();})
        .then(function(d){
            if(!d.success){hist.innerHTML='<div class="tah-empty">Ошибка</div>';return;}
            hist.innerHTML=render(d.items||[]);
        })
        .catch(function(){hist.innerHTML='<div class="tah-empty">Ошибка соединения</div>';});
}

function tryInstall(){
    var orig = window.__trkOpenTaskCardModal;
    if (typeof orig === 'function' && !orig._tahTaskIdHooked) {
        var w = function(taskId){
            window.__trkLastTaskCardId = taskId || '';
            return orig.apply(this, arguments);
        };
        w._tahTaskIdHooked = true;
        window.__trkOpenTaskCardModal = w;
    }
}
tryInstall();
setTimeout(tryInstall, 500);
setTimeout(tryInstall, 1500);
setTimeout(tryInstall, 3000);

setTimeout(inject,800);
setTimeout(inject,1800);
document.addEventListener('click',function(e){
    if(e.target&&e.target.closest&&e.target.closest('.task-card, .dict-item[data-act]'))setTimeout(inject,200);
});
})();
'''

    @app.route('/plugins-assets/task_audit.js', methods=['GET'])
    def _ta_js():
        return app.response_class(_JS, mimetype='application/javascript')

    def on_startup(**ctx):
        print('[task_audit] готов — вкладка «История» в карточке задачи')

    hooks.on('on_startup', on_startup)


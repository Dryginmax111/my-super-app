"""plugins/weekly_report.py — недельный HTML-отчёт по отделам."""
__version__ = '1.0'
__description__ = 'Недельный отчёт: HTML по отделам в share/reports/, планировщик + ручной запуск'

import json
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from flask import request, jsonify, Response, redirect, send_file

CFG = Path(__file__).parent / 'weekly_report.json'
DEFAULTS = {'enabled': True, 'weekday': 4, 'hour': 18, 'keep': 26, 'first_run_after_seconds': 120}


def _cfg():
    if not CFG.exists():
        CFG.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2), encoding='utf-8')
        return dict(DEFAULTS)
    try:
        c = dict(DEFAULTS)
        c.update(json.loads(CFG.read_text(encoding='utf-8')) or {})
        return c
    except Exception:
        return dict(DEFAULTS)


def _reports_dir(base):
    d = Path(base) / 'share' / 'reports'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_html(db):
    data = db.load_all()
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    monday_iso = monday.strftime('%Y-%m-%d')
    today_iso = today.strftime('%Y-%m-%d')

    def hours_by_emp():
        m = {}
        for l in data.get('log', []):
            ld = l.get('date') or ''
            if ld < monday_iso or ld > today_iso:
                continue
            eid = l.get('employee_id')
            if not eid:
                continue
            try:
                m[eid] = m.get(eid, 0.0) + float(l.get('hours') or 0)
            except Exception:
                pass
        return m

    hours = hours_by_emp()
    deps = data.get('departments', [])
    emps = data.get('employees', [])
    tasks = {t['id']: t for t in data.get('tasks', [])}

    def emp_stats(eid):
        logs = [l for l in data.get('log', []) if l.get('employee_id') == eid
                and monday_iso <= (l.get('date') or '') <= today_iso]
        done = set(l.get('task_id') for l in logs if l.get('status') == 'done')
        overdue = 0
        for t in data.get('tasks', []):
            if eid not in (t.get('assignees') or []):
                continue
            if t.get('status') not in ('active', 'paused'):
                continue
            dl = t.get('deadline') or ''
            if dl and dl < today_iso:
                has_done = any(l.get('task_id') == t['id'] and l.get('employee_id') == eid and l.get('status') == 'done' for l in data.get('log', []))
                if not has_done:
                    overdue += 1
        return {'hours': round(hours.get(eid, 0) * 4) / 4, 'done': len(done), 'overdue': overdue}

    html = ['<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">']
    html.append('<title>Недельный отчёт ' + monday_iso + ' — ' + today_iso + '</title>')
    html.append('<style>body{font-family:system-ui,sans-serif;background:#fff;color:#212121;padding:24px;max-width:1100px;margin:0 auto}h1{color:#00695c;font-size:1.6rem;margin-bottom:8px}h2{color:#00695c;font-size:1.2rem;margin-top:28px;border-bottom:2px solid #00897b;padding-bottom:6px}table{width:100%;border-collapse:collapse;margin:10px 0}th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #e0e0e0}th{background:#eceff1;font-size:0.78rem;text-transform:uppercase;color:#37474f}.num{text-align:right;font-weight:700}.ok{color:#2e7d32}.err{color:#c62828}.lbl{color:#607d8b;font-size:0.8rem}</style>')
    html.append('</head><body>')
    html.append('<h1>📊 Недельный отчёт</h1>')
    html.append('<div class="lbl">Период: ' + monday_iso + ' — ' + today_iso + ' · Сформирован: ' + datetime.now().strftime('%Y-%m-%d %H:%M') + '</div>')

    total_hours = 0.0
    total_done = 0
    total_overdue = 0
    rows_count = 0
    for dep in deps:
        dep_emps = [e for e in emps if e.get('department_id') == dep['id'] and not e.get('fired')]
        if not dep_emps:
            continue
        html.append('<h2>🏢 ' + (dep.get('name') or dep['id']) + '</h2>')
        html.append('<table><thead><tr><th>Сотрудник</th><th class="num">Часов</th><th class="num">Закрыто</th><th class="num">Просрочено</th></tr></thead><tbody>')
        dep_hours = 0.0
        for e in dep_emps:
            st = emp_stats(e['id'])
            dep_hours += st['hours']
            total_hours += st['hours']
            total_done += st['done']
            total_overdue += st['overdue']
            rows_count += 1
            ov_cls = ' class="num err"' if st['overdue'] else ' class="num"'
            html.append('<tr><td>' + (e.get('name') or e['id']) + '</td>'
                        + '<td class="num">' + str(st['hours']) + '</td>'
                        + '<td class="num ok">' + str(st['done']) + '</td>'
                        + '<td' + ov_cls + '>' + str(st['overdue']) + '</td></tr>')
        html.append('<tr style="background:#f5f5f5;font-weight:700"><td>Итого</td><td class="num">' + str(round(dep_hours * 4) / 4) + '</td><td></td><td></td></tr>')
        html.append('</tbody></table>')

    html.append('<h2>📈 Итоги недели</h2>')
    html.append('<table><tbody>')
    html.append('<tr><td>Всего часов</td><td class="num">' + str(round(total_hours * 4) / 4) + '</td></tr>')
    html.append('<tr><td>Закрыто задач</td><td class="num ok">' + str(total_done) + '</td></tr>')
    html.append('<tr><td>Просрочено</td><td class="num err">' + str(total_overdue) + '</td></tr>')
    html.append('<tr><td>Сотрудников в отчёте</td><td class="num">' + str(rows_count) + '</td></tr>')
    html.append('</tbody></table>')
    html.append(_mask_script_html())
    html.append('</body></html>')
    return ''.join(html)


def _mask_script_html():
    """PATCH 1.0.6 — клиентский скрипт маскирования ФИО в отчёте.
    Читает localStorage.reestr_tracker_mask, при включённом флаге маскирует
    первую колонку всех таблиц и показывает кнопку переключения."""
    return (
        '<style>'
        '#maskToggleBtn{position:fixed;top:16px;right:16px;z-index:100;'
        'padding:8px 14px;border-radius:10px;border:1px solid #00897b;'
        'background:#ffffff;color:#00695c;font-family:system-ui,sans-serif;'
        'font-size:0.85rem;font-weight:700;cursor:pointer;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.10);}'
        '#maskToggleBtn:hover{background:#e0f2f1;}'
        'td.masked-name{font-family:monospace;letter-spacing:0.5px;}'
        '</style>'
        '<button id="maskToggleBtn" type="button">👁 Показать ФИО</button>'
        '<script>'
        '(function(){'
        'var KEY="reestr_tracker_mask";'
        'function _enabled(){try{return localStorage.getItem(KEY)==="1";}catch(e){return false;}}'
        'function _mask(s){'
        '    return String(s||"").split(/\\s+/).map(function(w){'
        '        if(w.length<=1)return w;'
        '        return w[0]+new Array(w.length).join("*");'
        '    }).join(" ");'
        '}'
        'var _orig={};'
        'function _scan(){'
        '    document.querySelectorAll("table tbody tr").forEach(function(tr,ri){'
        '        var td=tr.querySelector("td:first-child");'
        '        if(!td)return;'
        '        if(td.hasAttribute("data-orig"))return;'
        '        var txt=td.textContent||"";'
        '        if(txt.trim()==="Итого")return;'
        '        td.setAttribute("data-orig",txt);'
        '        var key=td.getAttribute("data-orig");'
        '        _orig[key]=txt;'
        '    });'
        '}'
        'function _applyMask(on){'
        '    document.querySelectorAll("td[data-orig]").forEach(function(td){'
        '        var orig=td.getAttribute("data-orig");'
        '        if(on){'
        '            td.textContent=_mask(orig);'
        '            td.classList.add("masked-name");'
        '        }else{'
        '            td.textContent=orig;'
        '            td.classList.remove("masked-name");'
        '        }'
        '    });'
        '    var btn=document.getElementById("maskToggleBtn");'
        '    if(btn)btn.textContent=on?"🙈 Скрыть ФИО":"👁 Показать ФИО";'
        '}'
        'function _boot(){'
        '    _scan();'
        '    var on=_enabled();'
        '    _applyMask(on);'
        '    var btn=document.getElementById("maskToggleBtn");'
        '    if(!btn)return;'
        '    btn.addEventListener("click",function(){'
        '        var now=!(_enabled());'
        '        try{localStorage.setItem(KEY,now?"1":"0");}catch(e){}'
        '        _applyMask(now);'
        '    });'
        '}'
        'if(document.readyState==="loading"){'
        '    document.addEventListener("DOMContentLoaded",_boot);'
        '}else{_boot();}'
        '})();'
        '</script>'
    )


def _generate(db, base_dir):
    rdir = _reports_dir(base_dir)
    today = date.today()
    iso_week = today.strftime('%G-W%V')
    fname = 'report_' + iso_week + '.html'
    content = _build_html(db)
    path = rdir / fname
    path.write_text(content, encoding='utf-8')
    # Чистка старых
    cfg = _cfg()
    files = sorted(rdir.glob('report_*.html'), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[cfg.get('keep', 26):]:
        try: old.unlink()
        except Exception: pass
    return fname


def _worker(db, base_dir, stop):
    cfg = _cfg()
    stop.wait(int(cfg.get('first_run_after_seconds', 120)))
    while not stop.is_set():
        try:
            cfg = _cfg()
            if cfg.get('enabled'):
                now = datetime.now()
                if now.weekday() == int(cfg.get('weekday', 4)) and now.hour == int(cfg.get('hour', 18)):
                    _generate(db, base_dir)
                    print('[weekly_report] отчёт сформирован: ' + now.strftime('%Y-%m-%d %H:%M'))
                    stop.wait(3600)
        except Exception as e:
            print('[weekly_report] ошибка: ' + str(e))
        stop.wait(600)


def _page(csrf_token=''):
    # PATCH v1.0.13: CSRF-токен прокидывается в HTML, чтобы fetch(POST)
    # проходил before_request-проверку в app.py (иначе 400 csrf).
    return r'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Недельные отчёты</title>
<script>window.REESTR_CSRF = "__CSRF__";</script>
<script src="/static/plugin_theme.js"></script>
<script src="/static/plugin_mask.js"></script>
<style>body{font-family:system-ui,sans-serif;background:#0d0d0d;color:#e8e8e8;padding:24px;max-width:900px;margin:0 auto}h1{color:#f5d76e;font-size:1.4rem}a.back{color:#c8c8c8;text-decoration:none;font-size:0.85rem;padding:6px 14px;border:1px solid rgba(245,215,110,0.22);border-radius:20px;display:inline-block;margin-bottom:16px}.toolbar{display:flex;gap:8px;align-items:center;margin:16px 0}button{padding:8px 16px;border-radius:10px;background:linear-gradient(135deg,#f5d76e,#e6a81a);color:#0a0a0a;font-weight:700;border:none;cursor:pointer;font-family:inherit}button:hover{transform:scale(1.02)}.row{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;padding:10px 14px;background:rgba(20,20,20,0.6);border:1px solid rgba(245,215,110,0.18);border-radius:10px;margin-bottom:6px}.name{font-family:monospace;font-weight:700}.mtime{font-size:0.75rem;color:#8a8a8a}.dl{font-size:0.8rem;color:#6dc2f0;text-decoration:none;padding:4px 10px;border:1px solid rgba(52,152,219,0.4);border-radius:8px}.empty{text-align:center;padding:40px;color:#8a8a8a;font-style:italic}</style></head><body>
<a class="back" href="/">← К трекеру</a>
<h1>📊 Недельные отчёты</h1>
<div class="toolbar"><button id="genBtn">🔄 Сформировать сейчас</button><span id="msg" style="font-size:0.85rem;color:#8a8a8a;"></span></div>
<div id="list"><div class="empty">Загрузка…</div></div>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function load(){fetch('/api/plugins/weekly_report/list',{credentials:'same-origin'}).then(function(r){return r.json();}).then(function(d){var el=document.getElementById('list');if(!d.success||!d.items.length){el.innerHTML='<div class="empty">Отчётов пока нет</div>';return;}el.innerHTML=d.items.map(function(it){return '<div class="row"><span class="name">'+esc(it.name)+'</span><span class="mtime">'+esc(it.mtime)+'</span><a class="dl" href="/api/plugins/weekly_report/download?name='+encodeURIComponent(it.name)+'">⬇ Скачать</a></div>';}).join('');});}
document.getElementById('genBtn').addEventListener('click',function(){
    var b=this;
    b.disabled=true;
    document.getElementById('msg').textContent='Генерация…';
    // PATCH v1.0.13: X-CSRF-Token для POST-запроса
    var _hdrs = {};
    if (window.REESTR_CSRF) _hdrs['X-CSRF-Token'] = window.REESTR_CSRF;
    fetch('/api/plugins/weekly_report/generate',{
        method:'POST',
        credentials:'same-origin',
        headers:_hdrs
    })
    .then(function(r){return r.json();})
    .then(function(d){
        b.disabled=false;
        if (d && d.success) {
            document.getElementById('msg').textContent='Готово: '+d.name;
        } else {
            document.getElementById('msg').textContent='Ошибка: '+((d&&d.error)||'?');
        }
        load();
    })
    .catch(function(){b.disabled=false;document.getElementById('msg').textContent='Ошибка соединения';});
});
load();
</script></body></html>'''


def register(app, db, hooks):
    print('[weekly_report] v' + __version__ + ' · ' + __description__)
    base_dir = Path(app.root_path)
    stop = threading.Event()

    def _auth():
        try:
            from auth import current_user, user_has
            u = current_user(db)
            if not u: return None
            if not user_has(db, u, 'plugin.weekly.use'): return None
            return u
        except Exception:
            return None

    @app.route('/plugins/weekly_report/', methods=['GET'])
    def _wr_page():
        if not _auth(): return redirect('/login')
        # PATCH v1.0.13: прокидываем CSRF в страницу
        try:
            from auth import ensure_csrf
            _tok = ensure_csrf() or ''
        except Exception:
            _tok = ''
        _html = _page(_tok).replace('__CSRF__', _tok)
        return Response(_html, mimetype='text/html')

    @app.route('/api/plugins/weekly_report/list', methods=['GET'])
    def _wr_list():
        if not _auth(): return jsonify({'success': False}), 403
        rdir = _reports_dir(base_dir)
        items = []
        for f in sorted(rdir.glob('report_*.html'), key=lambda x: x.stat().st_mtime, reverse=True)[:26]:
            items.append({'name': f.name, 'size': f.stat().st_size, 'mtime': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})
        return jsonify({'success': True, 'items': items})

    @app.route('/api/plugins/weekly_report/generate', methods=['POST'])
    def _wr_gen():
        if not _auth(): return jsonify({'success': False}), 403
        try:
            name = _generate(db, base_dir)
            return jsonify({'success': True, 'name': name})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/plugins/weekly_report/download', methods=['GET'])
    def _wr_dl():
        if not _auth(): return jsonify({'success': False}), 403
        name = str(request.args.get('name', '')).strip()
        if not name or '/' in name or '\\' in name or '..' in name:
            return jsonify({'success': False}), 400
        p = _reports_dir(base_dir) / name
        if not p.exists(): return jsonify({'success': False}), 404
        return send_file(str(p), as_attachment=True, download_name=name)

    def on_startup(**ctx):
        t = threading.Thread(target=_worker, args=(db, base_dir, stop), daemon=True)
        t.start()
        print('[weekly_report] планировщик запущен')

    def on_shutdown(**ctx):
        stop.set()

    hooks.on('on_startup', on_startup)
    hooks.on('on_shutdown', on_shutdown)

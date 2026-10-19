"""Минимальный загрузчик плагинов. Изолирует ошибки, не роняет основной процесс.

Плагин — .py файл в папке plugins/ со следующей структурой:

    __version__ = '0.1'
    __description__ = 'Что делает плагин'

    def register(app, db, hooks):
        # hooks.on('<событие>', fn)
        app.route('/my-plugin/hello')(lambda: 'hi')

Доступные события (эмитятся из app.py):
    on_startup       — при старте приложения (ctx: app, db)
    on_log_save      — после сохранения отметки (ctx: user, log_id, created)
    on_task_save     — после сохранения задачи  (ctx: user, task_id, created)

Ошибки изолированы — исключение в плагине не валит основной процесс.
"""
import importlib.util
import json
import os
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path


STATE_FILE_NAME = '.plugins_state.json'

# PATCH: сериализация записи state, чтобы параллельные toggle не теряли данные
_STATE_LOCK = threading.RLock()


def _state_path(plugins_dir):
    return Path(plugins_dir) / STATE_FILE_NAME


def read_plugin_state(plugins_dir):
    p = _state_path(plugins_dir)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        # PATCH: при ошибке чтения возвращаем {} НО не даём затереть файл в set_*
        # (см. write_plugin_state + маркер _read_error)
        return {'_read_error': True}


def write_plugin_state(plugins_dir, state):
    """Атомарная запись: tempfile + os.replace. Безопасно на сетевых шарах."""
    p = _state_path(plugins_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    # PATCH: убираем служебный маркер до записи
    if isinstance(state, dict) and '_read_error' in state:
        state = {k: v for k, v in state.items() if k != '_read_error'}
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=STATE_FILE_NAME + '.', dir=str(p.parent), text=False)
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        # os.replace атомарен на одной ФС (в т.ч. Windows/UNC)
        os.replace(tmp_name, str(p))
    except Exception:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass
        raise


def set_plugin_enabled(plugins_dir, name, enabled):
    """Включает/выключает плагин. Потокобезопасно."""
    with _STATE_LOCK:
        state = read_plugin_state(plugins_dir)
        # PATCH: если файл битый — начинаем заново, но не теряем «enabled»
        if isinstance(state, dict) and state.pop('_read_error', False):
            print('[plugins] state-файл повреждён, пересоздаём')
        info = state.get(name, {}) or {}
        info['enabled'] = bool(enabled)
        info['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        state[name] = info
        write_plugin_state(plugins_dir, state)
        return state


class HookRegistry:
    """Реестр обработчиков событий."""

    def __init__(self):
        self._hooks = {}

    def on(self, name, fn):
        if not callable(fn):
            return
        self._hooks.setdefault(name, []).append(fn)

    def emit(self, name, **ctx):
        for fn in self._hooks.get(name, []):
            try:
                fn(**ctx)
            except Exception:
                print(f'[plugins] hook "{name}" failed:')
                traceback.print_exc()


def load_plugins(plugins_dir, app, db, registry):
    """Обходит plugins_dir/*.py, импортирует модули с register().

    Возвращает список словарей: [{'name', 'file', 'version', 'description'}, ...]
    """
    plugins_dir = Path(plugins_dir)
    if not plugins_dir.exists():
        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return []

    state = read_plugin_state(plugins_dir)
    if isinstance(state, dict) and state.get('_read_error'):
        print('[plugins] state-файл повреждён, использую дефолты')
        state = {}

    loaded = []
    for f in sorted(plugins_dir.glob('*.py')):
        if f.name.startswith('_'):
            continue
        name = f.stem
        info = state.get(name, {}) if isinstance(state, dict) else {}
        if info.get('enabled') is False:
            print(f'[plugins] {name} — отключён (state)')
            continue
        try:
            spec = importlib.util.spec_from_file_location(f'plugin_{name}', str(f))
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if not hasattr(mod, 'register'):
                print(f'[plugins] {f.name}: нет register() — пропуск')
                continue
            mod.register(app, db, registry)
            loaded.append({
                'name': name,
                'file': f.name,
                'version': str(getattr(mod, '__version__', '—')),
                'description': str(getattr(mod, '__description__', '')),
            })
            print(f'[plugins] ✓ {name} загружен')
        except Exception:
            print(f'[plugins] ✗ ошибка в {f.name}:')
            traceback.print_exc()
    return loaded


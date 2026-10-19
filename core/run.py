"""Standalone launcher трекера задач."""
import json
import sys
import webbrowser
import threading
from pathlib import Path

# --- FIX: embedded Python не добавляет папку скрипта в sys.path ---
_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / 'config.json'


def _load_config():
    if not CONFIG_PATH.exists():
        print(f'[!] Не найден {CONFIG_PATH}. Создайте файл config.json')
        sys.exit(1)
    try:
        return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[!] Ошибка чтения config.json: {e}')
        sys.exit(1)


def main():
    cfg = _load_config()
    from app import create_app
    try:
        app = create_app()
    except Exception as e:
        print(f'[!] Не удалось запустить приложение: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    host = cfg.get('host', '0.0.0.0')
    port = int(cfg.get('port', 5431))
    debug = bool(cfg.get('debug', False))
    url = f'http://{"127.0.0.1" if host in ("0.0.0.0", "::") else host}:{port}/'

    print('=' * 60)
    print('  Трекер задач — standalone')
    print('=' * 60)
    print(f'  БД:   {cfg.get("db_path")}')
    print(f'  URL:  {url}')
    print('  Ctrl+C для остановки')
    print('=' * 60)

    if not debug and cfg.get('open_browser', True):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()


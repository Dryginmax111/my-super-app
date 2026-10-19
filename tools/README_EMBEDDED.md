# Embedded Python для Tracker (Flask + openpyxl)

> 📌 Подробная пошаговая инструкция «где и что лежит + как запустить»: [README_ЗАПУСК_ПОДРОБНО.md](README_ЗАПУСК_ПОДРОБНО.md)

Всё в папке `tools\`. Работает с путями проекта: скрипты сами находят
`runtime\embedded\python313` относительно своего расположения.

## Вариант A — онлайн-сборка с нуля (нужен интернет на целевой машине)

Запустить `tools\setup_embedded.bat`. Скрипт:
1. скачает `python-3.13.2-embed-amd64.zip` с python.org;
2. распакует в `runtime\embedded\python313`;
3. перепишет `python313._pth` (раскомментирует `import site`, добавит `Lib\site-packages`) — **без этого pip в embedded не работает**;
4. установит get-pip.py;
5. поставит `flask` и `openpyxl` со всеми зависимостями:
   - Flask → werkzeug, jinja2, itsdangerous, click, blinker, MarkupSafe
   - openpyxl → et-xmlfile
6. проверит импорт.

Аналог в PowerShell: `powershell -ExecutionPolicy Bypass -File tools\build_embedded.ps1`

## Вариант B — офлайн-установка (без интернета и без pip)

Готовые `.whl` уже лежат в `tools\wheels\` (собраны командой ниже).
Достаточно распаковать официальный embeddable-архив Python в
`runtime\embedded\python313` и запустить `tools\install_offline.bat` —
он распакует wheels напрямую в `Lib\site-packages`.

Обновить набор wheels на машине с интернетом:

```bat
pip download --only-binary=:all: --platform win_amd64 --python-version 313 --implementation cp -d tools\wheels flask openpyxl
```

## Важные нюансы embedded-дистрибутива

| Проблема | Решение |
|---|---|
| В `python3xx._pth` строка `#import site` закомментирована | раскомментировать + добавить `Lib\site-packages` |
| `pip install` ругается «not a supported wheel» | качать wheels строго под нужную версию/платформу (см. команду выше). `MarkupSafe` — единственный бинарный пакет (cp313-win_amd64), остальные pure-python |
| PEP 668 (`externally-managed-environment`) | не актуально для embedded, но если ставите системный python — используйте venv |
| Антивирус блокирует `get-pip.py` | используйте вариант B (офлайн) |
| Перенос папки на другую машину | сборка portable: копируйте весь корень проекта целиком |

## Проверка готовности

```powershell
powershell -ExecutionPolicy Bypass -File tools\check_embedded.ps1
```

или вручную:

```bat
runtime\embedded\python313\python.exe -c "import flask, openpyxl; print(flask.__version__, openpyxl.__version__)"
```

После успешной проверки запускайте `START.bat`.

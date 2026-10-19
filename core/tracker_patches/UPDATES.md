# Обновления трекера

## Порядок применения (клиенты с baseline 1.0.0 «как в архиве»)

```bat
runtime\embedded\python313\python.exe core\patcher.py core\tracker_patches_new\0.0.0.json --dry
runtime\embedded\python313\python.exe core\patcher.py core\tracker_patches_new\0.0.0.json

runtime\embedded\python313\python.exe core\patcher.py core\tracker_patches_new\1.0.0.json --dry
runtime\embedded\python313\python.exe core\patcher.py core\tracker_patches_new\1.0.0.json
```

Перезапуск сервера после каждого успешного apply.

## 0.0.0 — фундамент

- `password` / `password_hash` вместо `kody` / `kody_hash`
- UI: «пароль» вместо «parol»
- миграция колонки в SQLite
- login без `KeyError` / `no such column`

**Не смешивать** с фичами. Один раз.

## 1.0.0 — бандл функций

| Блок | Суть |
|------|------|
| Уведомления | Вертикаль manager+head; create→инфо; done→confirm; админ fallback |
| Календарь | Рефреш после создания задачи; «🩶» до 200; сотрудник — только свои |
| Импорт отпусков | Новый сотрудник → user + базовые права + пароль `123456` |
| Карточка задачи | Лента всех отметок (не только с комментарием) |
| UI | Кнопки «Закрыть»; после «+» на назначенной — закрыть модалки |
| Экспорт | Dropdown: полный календарь / кто не заполнил отчёт; без дубля Excel |

## Важно

- Сначала **всегда** `--dry`.
- Если dry: только `✓` и `· пропуск` — можно apply.
- Если `✗` — **не** apply, пришлите лог.
- Старые файлы `1.0.1`…`1.0.20`, `revert_kody`, `fix_login` на клиентах можно удалить после перехода на `0.0.0` + `1.0.0`.

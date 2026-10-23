PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  kody_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  display_name TEXT DEFAULT '',
  employee_id TEXT DEFAULT '',
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_login TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_permissions (
  user_id INTEGER NOT NULL,
  perm_key TEXT NOT NULL,
  allowed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, perm_key)
);

CREATE TABLE IF NOT EXISTS departments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  color TEXT DEFAULT '#00897b',
  head_employee_id TEXT DEFAULT '',
  headcount INTEGER DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  color TEXT DEFAULT '#00897b',
  role TEXT DEFAULT '',
  department_id TEXT DEFAULT '',
  fired INTEGER NOT NULL DEFAULT 0,
  fired_date TEXT DEFAULT '',
  dir_corp REAL NOT NULL DEFAULT 0,
  dir_retail REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_vacations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id TEXT NOT NULL,
  date_from TEXT NOT NULL,
  date_to TEXT NOT NULL,
  vtype TEXT NOT NULL DEFAULT 'vacation',
  comment TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS teams (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  department_id TEXT DEFAULT '',
  manager_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS team_members (
  team_id TEXT NOT NULL,
  employee_id TEXT NOT NULL,
  PRIMARY KEY (team_id, employee_id)
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  icon TEXT DEFAULT '📋',
  description TEXT DEFAULT '',
  status TEXT DEFAULT 'active',
  start_date TEXT DEFAULT '',
  deadline TEXT DEFAULT '',
  completed_at TEXT DEFAULT '',
  folder TEXT DEFAULT '',
  order_ref TEXT DEFAULT '',
  -- Тип задачи: 'розничная' | 'корпоративная' (может быть пустым)
  task_type TEXT DEFAULT '',
  -- Карман: свободный текст, редактируется админом
  pocket TEXT DEFAULT '',
  -- Вид задачи: 'audit' (аудиторская проверка, по умолчанию) | 'other' (другое)
  task_kind TEXT DEFAULT 'audit',
  -- Коэффициент нагрузки (обязателен только для task_kind='other')
  load_coef REAL DEFAULT 0,
  -- Даты начала этапов (конец вычисляется: начало следующего непустого - 1 день;
  -- у последнего этапа 'оценка_тб' конец = deadline задачи)
  stage_подготовка_start TEXT DEFAULT '',
  stage_проверка_нжя_start TEXT DEFAULT '',
  stage_проверка_соглЦА_start TEXT DEFAULT '',
  stage_ос_проф_start TEXT DEFAULT '',
  stage_реализация_возражения_start TEXT DEFAULT '',
  stage_реализация_согласования_start TEXT DEFAULT '',
  stage_запас_start TEXT DEFAULT '',
  stage_оценка_тб_start TEXT DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_tags (
  task_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (task_id, tag)
);

CREATE TABLE IF NOT EXISTS task_assignees (
  task_id TEXT NOT NULL,
  employee_id TEXT NOT NULL,
  PRIMARY KEY (task_id, employee_id)
);

CREATE TABLE IF NOT EXISTS task_departments (
  task_id TEXT NOT NULL,
  department_id TEXT NOT NULL,
  PRIMARY KEY (task_id, department_id)
);

CREATE TABLE IF NOT EXISTS work_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id TEXT NOT NULL,
  task_id TEXT NOT NULL,
  date TEXT NOT NULL,
  hours REAL NOT NULL DEFAULT 0,
  comment TEXT DEFAULT '',
  status TEXT DEFAULT 'in_progress',
  link TEXT DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS holidays (
  date TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user_id INTEGER,
  username TEXT,
  kind TEXT NOT NULL,
  entity TEXT,
  entity_id TEXT,
  details TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  to_user_id INTEGER NOT NULL,
  from_user_id INTEGER,
  from_username TEXT DEFAULT '',
  kind TEXT NOT NULL,
  task_id TEXT DEFAULT '',
  employee_id TEXT DEFAULT '',
  message TEXT DEFAULT '',
  status TEXT DEFAULT 'new',
  read_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_notif_to_user ON notifications (to_user_id);
CREATE INDEX IF NOT EXISTS idx_notif_status ON notifications (status);

CREATE INDEX IF NOT EXISTS idx_logs_emp_date ON work_logs (employee_id, date);
CREATE INDEX IF NOT EXISTS idx_logs_task ON work_logs (task_id);
CREATE INDEX IF NOT EXISTS idx_assignees_emp ON task_assignees (employee_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log (ts);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (user_id);

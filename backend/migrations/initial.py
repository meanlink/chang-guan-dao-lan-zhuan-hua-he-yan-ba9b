"""多馆隔离结构迁移。

设计要点：
- 幂等且可中断重跑：所有结构变更先检查是否已存在；数据回填按“是否已有归属”判断，
  已归馆的行不再改动。迁移进行到一半停机，再次启动只会补齐未完成部分，
  原有关联（外键）和唯一归属（每条业务数据恰好属于一个馆）保持完整。
- 兼容全新库与旧版单馆库：旧数据统一迁入“原馆”，分析与归档一并归馆；
  尚未归馆的内容在应用层隐藏（所有查询都强制带 branch_id 过滤）。
- 同时适配 PostgreSQL（部署）与 SQLite（本地开发默认）。
"""
import time

from sqlalchemy import text

from src.config.database import engine, Base
from src import models  # noqa: F401  注册全部模型

ORIGIN_BRANCH_CODE = 'origin'
ORIGIN_BRANCH_NAME = '拾光科学馆（原馆）'


def _is_pg(conn):
    return engine.dialect.name == 'postgresql'


def _table_exists(conn, table):
    if _is_pg(conn):
        return bool(conn.execute(text(
            "SELECT 1 FROM information_schema.tables WHERE table_name=:t"),
            {'t': table}).first())
    return bool(conn.execute(text(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
        {'t': table}).first())


def _column_exists(conn, table, column):
    if _is_pg(conn):
        return bool(conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=:t AND column_name=:c"),
            {'t': table, 'c': column}).first())
    cols = {row[1] for row in conn.execute(text(f'PRAGMA table_info({table})'))}
    return column in cols


def _constraint_exists(conn, name):
    if _is_pg(conn):
        return bool(conn.execute(text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name=:n"), {'n': name}).first())
    # SQLite：约束内嵌在建表 SQL 中，按名匹配
    rows = conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")).all()
    return any(name in (row[0] or '') for row in rows)


def _index_exists(conn, name):
    if _is_pg(conn):
        return bool(conn.execute(text(
            "SELECT 1 FROM pg_indexes WHERE indexname=:n"), {'n': name}).first())
    return bool(conn.execute(text(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=:n"),
        {'n': name}).first())


def _rebuild_sqlite_datasets(conn):
    """SQLite 不支持 DROP CONSTRAINT。旧库 datasets.name 带全局唯一约束，
    按官方表重建流程换成新结构（含 branch_id、去掉名称全局唯一），
    数据逐列拷贝，主键 id 与 jobs.dataset_id 等关联保持不变。"""
    row = conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'")).first()
    if not row or 'branch_id' in (row[0] or ''):
        return  # 已是新结构
    conn.execute(text(
        "CREATE TABLE datasets_new ("
        "id INTEGER NOT NULL PRIMARY KEY, branch_id INTEGER, "
        "name VARCHAR(160) NOT NULL, source VARCHAR(200) NOT NULL, "
        "records JSON NOT NULL, checksum VARCHAR(64) NOT NULL, "
        "created_at FLOAT NOT NULL, "
        "FOREIGN KEY(branch_id) REFERENCES branches (id))"))
    conn.execute(text(
        "INSERT INTO datasets_new "
        "(id, branch_id, name, source, records, checksum, created_at) "
        "SELECT id, NULL, name, source, records, checksum, created_at FROM datasets"))
    conn.execute(text("DROP TABLE datasets"))
    conn.execute(text("ALTER TABLE datasets_new RENAME TO datasets"))


def _schema(conn):
    # 1. 新表（全新库直接由 metadata 建立；旧库只补缺失表）
    Base.metadata.create_all(engine)

    # SQLite 旧库先重建 datasets，去掉名称全局唯一约束（PG 走 DROP CONSTRAINT）
    if not _is_pg(conn):
        _rebuild_sqlite_datasets(conn)

    # 2. 旧库补列（create_all 不会改动已存在的表）
    additions = {
        'datasets': [('branch_id', 'INTEGER')],
        'jobs': [('branch_id', 'INTEGER')],
        'reports': [('branch_id', 'INTEGER')],
        'deliveries': [('branch_id', 'INTEGER')],
        'audits': [('branch_id', 'INTEGER')],
    }
    for table, cols in additions.items():
        if not _table_exists(conn, table):
            continue
        for column, ddl_type in cols:
            if not _column_exists(conn, table, column):
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))

    # 3. 旧的批次名全局唯一约束改为“馆内唯一”，保留同名批次跨馆独立建立的能力
    if _is_pg(conn):
        if _table_exists(conn, 'datasets') and _constraint_exists(conn, 'datasets_name_key'):
            conn.execute(text('ALTER TABLE datasets DROP CONSTRAINT datasets_name_key'))
    if not _index_exists(conn, 'uq_dataset_branch_name'):
        conn.execute(text(
            'CREATE UNIQUE INDEX uq_dataset_branch_name ON datasets (branch_id, name)'))


def _ensure_origin_branch(conn):
    row = conn.execute(text(
        "SELECT id FROM branches WHERE code=:c"), {'c': ORIGIN_BRANCH_CODE}).first()
    if row:
        return row[0]
    now = time.time()
    conn.execute(text(
        "INSERT INTO branches (code, name, created_at) VALUES (:c, :n, :t)"),
        {'c': ORIGIN_BRANCH_CODE, 'n': ORIGIN_BRANCH_NAME, 't': now})
    return conn.execute(text(
        "SELECT id FROM branches WHERE code=:c"),
        {'c': ORIGIN_BRANCH_CODE}).scalar_one()


def _backfill(conn, branch_id):
    """把旧数据全部归入原馆。逐表按 branch_id IS NULL 回填，
    已归馆的行不会被重复处理——中断重跑时天然续跑。"""
    for table in ('datasets', 'jobs', 'reports', 'deliveries', 'audits'):
        if not _table_exists(conn, table):
            continue
        conn.execute(text(
            f'UPDATE {table} SET branch_id=:b WHERE branch_id IS NULL'),
            {'b': branch_id})

    # 旧用户按其历史全局角色在原馆获得对应职责；撤销资格即删除 membership 行。
    if _table_exists(conn, 'users') and _column_exists(conn, 'users', 'role'):
        rows = conn.execute(text(
            "SELECT id, role FROM users WHERE NOT EXISTS ("
            "SELECT 1 FROM branch_memberships m "
            "WHERE m.user_id=users.id AND m.branch_id=:b)"),
            {'b': branch_id}).all()
        role_map = {'admin': 'owner', 'analyst': 'analyst', 'viewer': 'viewer'}
        for user_id, old_role in rows:
            conn.execute(text(
                "INSERT INTO branch_memberships (user_id, branch_id, role) "
                "VALUES (:u, :b, :r)"),
                {'u': user_id, 'b': branch_id,
                 'r': role_map.get(old_role, 'viewer')})


def migrate():
    with engine.begin() as conn:
        _schema(conn)
        origin = _ensure_origin_branch(conn)
        _backfill(conn, origin)
    return origin


if __name__ == '__main__':
    branch_id = migrate()
    print(f'migration ok; origin branch id={branch_id}')

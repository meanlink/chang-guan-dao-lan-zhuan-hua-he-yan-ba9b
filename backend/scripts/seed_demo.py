"""多馆演示数据。

两个馆：
- 拾光科学馆（原馆 origin）：迁移旧数据的归属馆。
- 星河探索馆（星河 branch）：第二个分馆，用于验证隔离与同名批次独立建立。

同一账号在不同馆职责不同，例如 analyst 在原馆是 analyst、在星河馆仅 viewer。
所有 seed 都按自然键幂等，可重复执行；迁移半途中断后重跑只会补齐缺口。
"""
import time
import json

from sqlalchemy import select

from src.config.database import Session
from migrations.initial import migrate, ORIGIN_BRANCH_CODE, ORIGIN_BRANCH_NAME
from src.models import (User, Branch, BranchMembership, Dataset, Job, Report,
                        Delivery, Audit)
from src.services.business import metadata, seed_records, analyze
from src.services.reports import deliver
from src.utils.security import hash_password
from src.utils.serialization import checksum

DEMO_PASSWORD = 'Demo123!'

# (email, 姓名, 原馆职责, 星河馆职责或 None 表示无资格)
DEMO_USERS = [
    ('admin@demo.local', '林知 · 业务负责人', 'owner', 'owner'),
    ('analyst@demo.local', '陈舟 · 分析员', 'analyst', 'viewer'),
    ('viewer@demo.local', '周禾 · 观察员', 'viewer', None),
]

BRANCHES = [
    (ORIGIN_BRANCH_CODE, ORIGIN_BRANCH_NAME),
    ('xinghe', '星河探索馆'),
]


def _ensure_branch(db, code, name):
    b = db.scalar(select(Branch).where(Branch.code == code))
    if not b:
        b = Branch(code=code, name=name, created_at=time.time())
        db.add(b)
        db.flush()
    return b


def _ensure_user(db, email, name):
    u = db.scalar(select(User).where(User.email == email))
    if not u:
        u = User(email=email, name=name, password=hash_password(DEMO_PASSWORD))
        db.add(u)
        db.flush()
    return u


def _ensure_membership(db, user_id, branch_id, role):
    m = db.scalar(select(BranchMembership).where(
        BranchMembership.user_id == user_id, BranchMembership.branch_id == branch_id))
    if not m:
        db.add(BranchMembership(user_id=user_id, branch_id=branch_id, role=role))
    elif m.role != role:
        m.role = role
    db.flush()


def _ensure_dataset(db, branch_id, name, source):
    d = db.scalar(select(Dataset).where(
        Dataset.branch_id == branch_id, Dataset.name == name))
    if not d:
        rows = seed_records()
        d = Dataset(branch_id=branch_id, name=name, source=source, records=rows,
                    checksum=checksum(rows), created_at=time.time())
        db.add(d)
        db.flush()
    return d


def _ensure_baseline(db, branch, dataset, owner_user):
    job_name = '基线复核 · ' + metadata()['name']
    j = db.scalar(select(Job).where(
        Job.branch_id == branch.id, Job.name == job_name))
    if not j:
        params = {p['key']: p['default'] for p in metadata().get('parameters', [])}
        result = analyze(dataset.records, params)
        json.dumps(result, ensure_ascii=False, allow_nan=False)
        j = Job(branch_id=branch.id, name=job_name, dataset_id=dataset.id, params=params,
                status='completed', result=result, created_by=owner_user.id,
                created_at=time.time() - 3600, finished_at=time.time() - 3595,
                approved=True)
        db.add(j)
        db.flush()
        r = Report(branch_id=branch.id, name='每日业务复核简报', job_id=j.id,
                   destination=branch.name + ' · 本地收件箱', interval_seconds=86400,
                   next_run=time.time() + 86400, enabled=True)
        db.add(r)
        db.flush()
        deliver(db, r)
        db.add(Audit(branch_id=branch.id, actor='seed', action='demo.baseline',
                     detail={'dataset': dataset.id}, at=time.time()))
    return j


def seed():
    migrate()
    with Session() as db:
        branch_map = {code: _ensure_branch(db, code, name) for code, name in BRANCHES}
        db.flush()

        users = {}
        for email, name, _r1, _r2 in DEMO_USERS:
            users[email] = _ensure_user(db, email, name)
        db.flush()

        for email, _name, origin_role, xinghe_role in DEMO_USERS:
            uid = users[email].id
            _ensure_membership(db, uid, branch_map[ORIGIN_BRANCH_CODE].id, origin_role)
            if xinghe_role:
                _ensure_membership(db, uid, branch_map['xinghe'].id, xinghe_role)

        m = metadata()
        # 两个馆建立“同名”批次，验证同名批次可在不同馆独立建立。
        for code, _name in BRANCHES:
            branch = branch_map[code]
            dataset = _ensure_dataset(
                db, branch.id, m['dataset_name'], m['short'] + '-202611.csv')
            _ensure_baseline(db, branch, dataset, users['admin@demo.local'])

        db.commit()
        from sqlalchemy import func
        counts = {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                  for model in [User, Branch, BranchMembership, Dataset, Job, Report,
                                Delivery, Audit]}
        print(json.dumps(counts, ensure_ascii=False))
        return counts


if __name__ == '__main__':
    seed()

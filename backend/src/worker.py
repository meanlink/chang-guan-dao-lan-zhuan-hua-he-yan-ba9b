import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report
from src.services.business import analyze
from src.services.reports import deliver
from src.services.audit import record

logging.basicConfig(level=logging.INFO)


def execute(job_id):
    with Session() as db:
        j = db.get(Job, job_id)
        if not j or j.status != 'queued':
            return
        j.status = 'running'
        db.commit()
        try:
            d = db.get(Dataset, j.dataset_id)
            # 唯一归属保持：任务与其批次必须同馆，否则判失败而非混用别馆数据。
            if d is None or d.branch_id != j.branch_id:
                raise ValueError('数据批次与任务不属于同一馆，拒绝计算')
            result = analyze(d.records, j.params)
            json.dumps(result, allow_nan=False)
            j.result = result
            j.status = 'completed'
            j.finished_at = time.time()
            record(db, 'worker', 'job.completed', {'id': j.id}, branch_id=j.branch_id)
        except Exception as e:
            logging.exception('Analysis failed')
            j.status = 'failed'
            j.error = str(e)[:990]
            j.finished_at = time.time()
            record(db, 'worker', 'job.failed',
                   {'id': j.id, 'error': j.error}, branch_id=j.branch_id)
        db.commit()


def tick():
    # 排队分析与定时分发按实体自身的归属馆执行，与任何账号的当前馆无关；
    # 账号切馆不会改变这些后台工作的归属。
    with Session() as db:
        queued = list(db.scalars(select(Job.id).where(Job.status == 'queued').limit(3)))
    for job_id in queued:
        execute(job_id)
    with Session() as db:
        for r in db.scalars(select(Report).where(
                Report.enabled == True, Report.next_run <= time.time())):  # noqa: E712
            d = deliver(db, r)
            if d:
                record(db, 'worker', 'report.delivered',
                       {'id': r.id, 'delivery': d.id}, branch_id=r.branch_id)
        db.commit()


def main():
    r = Redis.from_url(REDIS_URL, socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status == 'running')):
            j.status = 'queued'
            record(db, 'worker', 'job.recovered', {'id': j.id}, branch_id=j.branch_id)
        db.commit()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item = r.blpop('analysis:queue', timeout=1)
            if item:
                execute(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry')
            time.sleep(2)


if __name__ == '__main__':
    main()

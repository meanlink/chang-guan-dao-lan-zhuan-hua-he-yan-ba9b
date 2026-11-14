import time

from src.models import Audit


def record(db, actor, action, detail=None, branch_id=None):
    db.add(Audit(branch_id=branch_id, actor=actor, action=action,
                 detail=detail or {}, at=time.time()))

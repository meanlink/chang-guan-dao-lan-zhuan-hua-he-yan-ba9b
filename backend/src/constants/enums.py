from enum import Enum


class BranchRole(str, Enum):
    """馆内职责，随馆授予、按馆生效；同一账号在不同馆可以不同。"""
    owner = 'owner'      # 负责人：馆内全部维护权限（批准、分发等）
    analyst = 'analyst'  # 分析：接入数据、发起分析
    viewer = 'viewer'    # 只读：查看与下载


# 兼容旧引用：全局 Role 已取消，角色语义一律以 BranchRole 为准
Role = BranchRole


class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'

# 场馆导览转化核验

分类独立性检验的真实业务分析小型项目。完整模拟客户、痛点、上下游、算法公式与一天工作剧本见 [BUSINESS.md](BUSINESS.md)。

## 模块与业务流程
数据接入（JSON/CSV、字段验证、批次指纹）→ 参数化分析（异步 Python worker）→ 结果复核（指标、图形、明细、解释、批准）→ 定时分发（本地收件箱、CSV/JSON、SHA256）；另有业务总览和审计轨迹。
三个贯穿全栈的实体：Dataset 数据批次、Job 分析任务、Report 分发计划；辅助 User、Branch、BranchMembership、Audit、Delivery。
数据批次、分析任务、分发计划与归档全部按馆隔离：每个请求携带当前馆标识，服务端实时复核账号在该馆的资格，越权访问与跨馆引用一律拒绝。

## 快速启动
```bash
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```
访问 http://localhost:18204；后端文档 http://localhost:19204/docs；数据库宿主端口 17704。
`SEED_DEMO=true` 自动幂等 seed；不覆盖用户修改。手动 seed 命令可重复执行。

## 演示账号与馆内职责
职责随馆授予，同一账号在不同馆可以不同；登录后侧栏切馆，页面随时显示当前馆与职责。
|账号|密码|拾光科学馆（原馆）|星河探索馆|
|---|---|---|---|
|admin@demo.local|Demo123!|负责人 owner|负责人 owner|
|analyst@demo.local|Demo123!|分析 analyst（接入、执行、读取下载）|只读 viewer|
|viewer@demo.local|Demo123!|只读 viewer（读取与下载）|无资格（不可进入）|
- owner 馆内负责人：批准、分发、暂停及全部读写；analyst：接入数据与发起分析，不能批准或安排分发；viewer：只读与下载。
- 令牌只证明身份，馆内职责每次请求按 branch_memberships 实时判定；撤销某馆资格后，旧登录凭据立即失去该馆访问权。
- 排队分析与定时分发在发起/创建时固化归属馆，不随账号切馆改变；worker 按实体自身的 branch_id 执行。
- 批次名唯一性按馆判定，同名批次可在不同馆独立建立；尚未归馆（branch_id 为空）的内容对所有列表隐藏。

## 技术与本地开发
Python 3.12 / FastAPI / SQLAlchemy / NumPy / SciPy / scikit-learn；PostgreSQL 16；Redis 7；Nginx；原生 HTML CSS JavaScript ES modules（用户指定）。后端所有校验、持久化和算法在服务端。无前端打包步骤。
后端：安装 backend/requirements.txt，设置 DATABASE_URL、REDIS_URL、JWT_SECRET、ARTIFACT_DIR 后在 backend/ 执行 `python -m migrations.initial`、`python -m scripts.seed_demo`、`uvicorn src.main:app`，另开 `python -m src.worker`。前端使用带 /api 反向代理的 Nginx，直接打开 index.html 不支持 API。

## 目录与工程约定
backend/src/{models,schemas,services,routes,controllers,middlewares,constants,config,utils}；backend/scripts/seed_demo.py；backend/migrations/initial.py。
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants}。
BranchRole 枚举：owner/analyst/viewer（馆内职责，非全局角色）；JobStatus：queued/running/completed/failed。后端 backend/src/constants/enums.py，前端 frontend/src/constants/enums.js。请求用 X-Branch-Id 声明当前馆，路由在 middlewares/auth.py 按馆实时授权；页面按相同馆内职责控制操作入口。

## 多馆迁移（可中断重跑）
`migrations/initial.py` 幂等执行：补建 branches/branch_memberships 与各表 branch_id，旧数据统一归入“拾光科学馆（原馆）”，分析、简报与归档一并归馆，旧全局角色 admin/analyst/viewer 映射为原馆 owner/analyst/viewer。回填按 branch_id IS NULL 逐表进行，迁移半途停机后再次启动只补齐缺口，原有关联与唯一归属保持完整。PostgreSQL 用 DROP CONSTRAINT 解除批次名全局唯一，SQLite 用表重建处理。

## 环境变量与 Docker
COMPOSE_PROJECT_NAME=guide-chi；FRONTEND_PORT=18204；BACKEND_PORT=19204；DB_PORT=17704；DB_PASSWORD、JWT_SECRET 见 .env.example；SEED_DEMO 默认 true。共享命名产物卷供后端下载与 worker 写入，数据库/Redis 各持久卷。
恰好五服务均有健康检查。Redis 队列加 SQL 排队状态兜底；worker 按 next_run 生成本地收件箱文件。周期 60 秒至 30 天。分发结果为批准分析的固定快照；若需新数据重新计算并建立新计划。当前不连接邮件或企业聊天。
错误响应、请求编号、Redis 每 IP 每分钟 240 次限流、JWT 和数据库操作审计。演示密钥与密码仅供本机模拟；生产部署前配置独立密钥与账号。

## 数据与验收
所有数据为固定随机种子生成的模拟业务数据，不能作为实际生产决策证据。项目独立算法、输入边界及业务局限详见 BUSINESS.md。测试与截图统一存放 ../../test-artifacts/gb-1005/，源码不含日志/截图/测试报告。
清理本项目演示数据：`docker compose down -v --remove-orphans`（会删除本项目命名卷）。

## License
MIT，见 LICENSE。

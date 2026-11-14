// 馆内职责：同一账号在不同馆可以不同，页面判断一律以当前馆职责为准
export const BranchRole={owner:'负责人',analyst:'分析员',viewer:'只读'};
// 兼容旧名称
export const Role=BranchRole;
export const JobStatus={queued:'排队中',running:'计算中',completed:'已完成',failed:'执行失败'};

// 会话只保存身份令牌；当前馆与馆内职责随切馆更新。
// 服务端每次请求按 user_id + branch_id 实时复核资格，
// 因此撤销馆内资格后，本地即便保留令牌也会被后端拒绝。
export const session={
 token:localStorage.getItem('token'),
 user:JSON.parse(localStorage.getItem('user')||'null'),
 memberships:JSON.parse(localStorage.getItem('memberships')||'[]'),
 branchId:JSON.parse(localStorage.getItem('branchId')||'null'),
 role:localStorage.getItem('role')||null,
 save(data){
  this.token=data.access_token;this.user=data.user;this.memberships=data.memberships||[];
  localStorage.setItem('token',this.token);
  localStorage.setItem('user',JSON.stringify(this.user));
  localStorage.setItem('memberships',JSON.stringify(this.memberships));
  // 登录后默认进入第一个有资格的馆
  this.setBranch(this.memberships[0]?this.memberships[0].branch_id:null);
 },
 setBranch(branchId){
  const m=this.memberships.find(x=>x.branch_id===branchId)||null;
  this.branchId=m?m.branch_id:null;this.role=m?m.role:null;
  if(this.branchId==null){localStorage.removeItem('branchId');localStorage.removeItem('role');}
  else{localStorage.setItem('branchId',JSON.stringify(this.branchId));localStorage.setItem('role',this.role);}
 },
 currentBranch(){return this.memberships.find(x=>x.branch_id===this.branchId)||null;},
 clear(){
  this.token=null;this.user=null;this.memberships=[];this.branchId=null;this.role=null;
  ['token','user','memberships','branchId','role'].forEach(k=>localStorage.removeItem(k));
 }
};

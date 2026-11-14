import {session} from '../stores/session.js';
export async function api(path,options={}){
 const headers={'Content-Type':'application/json',...(session.token?{Authorization:'Bearer '+session.token}:{}),...(session.branchId!=null?{'X-Branch-Id':String(session.branchId)}:{}),...options.headers};
 const r=await fetch('/api'+path,{...options,headers});
 if(!r.ok){
  let d=await r.json().catch(()=>({detail:'连接失败，请稍后重试'}));
  if(r.status===401&&path!='/auth/login'){session.clear();location.hash='#/login';}
  // 403 且为馆资格问题：刷新本地馆清单，引导切回有权限的馆
  if(r.status===403&&path!='/auth/login'&&path!='/auth/switch-branch'){await refreshMemberships();}
  throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));
 }
 return r.json();
}
export async function refreshMemberships(){
 if(!session.token)return;
 try{
  const r=await fetch('/api/auth/branches',{headers:{Authorization:'Bearer '+session.token}});
  if(!r.ok)return;
  session.memberships=await r.json();
  localStorage.setItem('memberships',JSON.stringify(session.memberships));
  if(!session.memberships.some(m=>m.branch_id===session.branchId))session.setBranch(session.memberships[0]?session.memberships[0].branch_id:null);
 }catch{/* 网络异常时保留现状，后端仍是唯一裁决者 */}
}
export async function download(id,format){
 const r=await fetch('/api/deliveries/'+id+'/download?format='+format,{headers:{Authorization:'Bearer '+session.token,'X-Branch-Id':String(session.branchId)}});
 if(!r.ok)throw new Error('下载失败或无权访问该归档');
 const u=URL.createObjectURL(await r.blob()),a=document.createElement('a');a.href=u;a.download='分析归档-'+id+'.'+format;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);
}

import {session} from '../../stores/session.js';
import {workspace} from '../../stores/workspace.js';
import {BranchRole} from '../../constants/enums.js';
import {esc} from '../../utils/dom.js';
import {api} from '../../api/client.js';
import {notify} from '../../utils/dom.js';

export function shell(page,content){
 const m=workspace.meta,nav=[['overview','业务总览'],['datasets','数据接入'],['workbench',m.workbench_title||'分析工作台'],['results','结果复核'],['reports','分发档案']];
 const current=session.currentBranch();
 const switcher='<label class="branch-picker"><small>当前场馆</small><select id="branch-switch">'+session.memberships.map(x=>'<option value="'+x.branch_id+'" '+(x.branch_id===session.branchId?'selected':'')+'>'+esc(x.name)+' · '+esc(BranchRole[x.role]||x.role)+'</option>').join('')+'</select></label>';
 return '<div class="shell"><aside><a class="brand" href="#/overview"><span class="brand-symbol">'+esc(m.short.split('-').map(s=>s[0]).join('').toUpperCase())+'</span><span>'+esc(m.name)+'</span></a><div class="edition">DATA FIELDNOTES / 2026</div>'+switcher+'<nav>'+nav.map((n,i)=>'<a class="'+(page===n[0]?'active':'')+'" href="#/'+n[0]+'"><small>0'+(i+1)+'</small>'+esc(n[1])+'</a>').join('')+'</nav><div class="aside-note"><span>业务现场</span><p>'+esc(m.client)+'</p><span>模拟场景 · 可追溯计算</span></div><div class="account"><strong>'+esc(session.user.name)+'</strong><span>'+esc(current?current.name:'未选馆')+' · '+esc(current?BranchRole[current.role]||current.role:'—')+'</span><button id="logout" class="text-button">退出登录 ↗</button></div></aside><div class="stage"><header><span>'+esc(m.tagline)+'</span><span class="live-dot">'+esc(current?('当前馆：'+current.name)+' · 职责：'+(BranchRole[current.role]||current.role):'数据与计算已连接')+'</span></header><main>'+content+'</main><footer>'+esc(m.short.toUpperCase())+'<span>数据接入 → 计算 → 馆内复核 → 馆内分发</span></footer></div></div>';
}
export function bindShell(render){
 const sel=document.querySelector('#branch-switch');
 if(sel)sel.onchange=async()=>{
  try{
   const branchId=Number(sel.value);
   await api('/auth/switch-branch',{method:'POST',body:JSON.stringify({branch_id:branchId})});
   session.setBranch(branchId);
   workspace.datasets=[];workspace.jobs=[];workspace.reports=[];workspace.selectedJob=null;
   notify('已切换到 '+session.currentBranch().name);
   location.hash='#/overview';render();
  }catch(e){notify(e.message,true);sel.value=String(session.branchId);}
 };
}
export const heading=(over,title,description,action='')=>'<div class="page-heading"><div><p class="eyebrow">'+esc(over)+'</p><h1>'+esc(title)+'</h1><p class="description">'+esc(description)+'</p></div>'+action+'</div>';

"use strict";
let intakeMode="submissions", intakeOffset=0, intakeDetail=null, intakeListRequest=0, intakeDetailRequest=0;
const intakeStatusLabels={pending:"待审核",needs_info:"需补充",approved:"已入库",rejected:"已拒绝",unsubmitted:"未提交"};
const intakeFields={name:"姓名",email:"邮箱",native_language:"母语",gender:"性别",entity_type:"合作主体",wechat:"微信",location:"所在地",timezone:"时区",domains:"擅长领域",text_types:"文本类型",cat_tools:"CAT 工具",daily_output:"日产量"};
const intakeRateFields={translation_rate:"翻译 / 千字",review_rate:"审校 / 千字",mtpe_rate:"MTPE / 千字",lqa_rate:"LQA / 小时",lqe_rate:"LQE / 小时"};
const intakeEl=id=>document.getElementById(id);
const intakeTime=value=>value?new Date(value).toLocaleString():"—";
function intakeValue(value,field){
  const labels={gender:{male:"男",female:"女"},entity_type:{individual:"个人译员",vendor:"供应商"},cooperation_source:{our_company:"我司合作",external:"外部合作"},project_status:{current:"当前",past:"过往"}};
  const map=labels[field];return esc(map&&Object.hasOwn(map,value)?map[value]:value??"—");
}
async function intakeRequest(method,path,body){
  const response=await fetch(`/api/intake${path}`,{method,cache:"no-store",headers:{Authorization:`Bearer ${TOKEN}`,"Content-Type":"application/json"},...(body?{body:JSON.stringify(body)}:{})});
  const result=await response.json();
  if(!response.ok){const message=Array.isArray(result.detail)?result.detail.map(e=>e.msg).join("；"):result.detail||"请求失败";showToast(message,"error");throw new Error(message);}
  return result;
}
function showIntakeLink(result){
  intakeEl("intakeLink").value=result.url;intakeEl("intakePreview").href=result.url;
  intakeEl("intakeLinkHint").textContent=result.preview_only?`本地预览链接，有效至 ${intakeTime(result.expires_at)}。对外发送前需部署公开填写入口并配置其地址。`:`有效至 ${intakeTime(result.expires_at)}。请将此专属链接发送给邀请邮箱的译员。`;
  intakeEl("intakeLinkBox").hidden=false;
}
intakeEl("intakeInviteForm").addEventListener("submit",async event=>{
  event.preventDefault();if(!event.target.reportValidity()||ROLE!=="editor")return;
  const button=intakeEl("intakeCreateButton");button.disabled=true;
  const body={email:intakeEl("intakeEmail").value.trim(),expires_days:Number(intakeEl("intakeExpiry").value)};
  if(intakeEl("intakeTranslatorId").value)body.translator_id=Number(intakeEl("intakeTranslatorId").value);
  try{const result=await intakeRequest("POST","/invites",body);if(ROLE!=="editor")return;showIntakeLink(result);showToast("邀请链接已生成","success");intakeMode="invites";intakeOffset=0;await loadIntake();}catch{}finally{button.disabled=false;}
});
async function copyIntakeLink(){
  const input=intakeEl("intakeLink");
  try{await navigator.clipboard.writeText(input.value);showToast("链接已复制","success");}catch{input.focus();input.select();showToast("链接已选中，请按 Ctrl/Cmd+C 复制");}
}
function setIntakeMode(mode){intakeMode=mode;intakeOffset=0;loadIntake();}
function resetIntakePage(){intakeOffset=0;loadIntake();}
function pageIntake(direction){intakeOffset=Math.max(0,intakeOffset+direction*50);loadIntake();}
async function loadIntake(){
  if(ROLE!=="editor")return;
  const sequence=++intakeListRequest,mode=intakeMode;
  intakeEl("intakeStatus").hidden=mode!=="submissions";
  const query=new URLSearchParams({offset:intakeOffset,limit:50});
  if(mode==="submissions"&&intakeEl("intakeStatus").value)query.set("status",intakeEl("intakeStatus").value);
  try{
    const rows=await intakeRequest("GET",`/${mode}?${query}`);if(ROLE!=="editor"||sequence!==intakeListRequest)return;
    intakeEl("intakePrev").disabled=intakeOffset===0;intakeEl("intakeNext").disabled=rows.length<50;
    intakeEl("intakeListLabel").textContent=`${mode==="invites"?"邀请记录":"提交资料"} · 第 ${intakeOffset/50+1} 页 · ${rows.length} 条`;
    intakeEl("intakeRows").innerHTML=mode==="invites"?tbl(["邀请邮箱","目标译员","有效至","状态","操作"],rows.map(row=>`<tr><td>${esc(row.email)}</td><td>${row.translator_id?`#${row.translator_id}`:"新建申请"}</td><td>${esc(intakeTime(row.expires_at))}</td><td>${row.revoked_at?"已撤销":row.expired?"链接已过期":esc(intakeStatusLabels[row.status])}</td><td>${row.submission_id?`<button class="btn-link" onclick="openIntakeReview(${row.submission_id})">查看资料</button>`:""}${!row.revoked_at?`<button class="btn-link danger" onclick="revokeIntakeInvite(${row.id})">撤销链接</button>`:""}<button class="btn-link" onclick="refillIntakeInvite(${row.id})">重新邀请</button></td></tr>`).join("")):tbl(["姓名","邮箱","提交时间","状态","操作"],rows.map(row=>`<tr><td>${esc(row.name)}</td><td>${esc(row.email)}</td><td>${esc(intakeTime(row.submitted_at))}</td><td>${esc(intakeStatusLabels[row.status])}</td><td><button class="btn-link" onclick="openIntakeReview(${row.id})">${row.status==="pending"?"审核资料":"查看资料"}</button></td></tr>`).join(""));
    intakeEl("intakeRows")._rows=rows;
  }catch{if(ROLE==="editor"&&sequence===intakeListRequest)intakeEl("intakeRows").textContent="未能读取资料，请点击刷新重试。";}
}
async function revokeIntakeInvite(id){
  if(!confirm("撤销后该链接无法继续填写，待审资料也不能入库。确认撤销？"))return;
  try{await intakeRequest("POST",`/invites/${id}/revoke`,{});showToast("链接已撤销","success");await loadIntake();if(intakeDetail)await openIntakeReview(intakeDetail.id);}catch{}
}
function refillIntakeInvite(id){
  const row=intakeEl("intakeRows")._rows?.find(item=>item.id===id);if(!row)return;
  intakeEl("intakeEmail").value=row.email;intakeEl("intakeTranslatorId").value=row.translator_id||"";
  intakeEl("intakeLinkBox").hidden=true;intakeEl("intakeLink").value="";
  intakeEl("intakeInviteForm").scrollIntoView({block:"center"});intakeEl("intakeCreateButton").focus();
  showToast("已填入邀请信息。旧链接如不再使用，请先撤销。");
}
function intakeProjectTable(projects){
  return `<div class="table-scroll">${tbl(["项目","来源 / 公司","状态 / 角色","语言对","开始","结束","截止","剩余量","说明"],projects.map(project=>`<tr><td>${esc(project.project_name)}</td><td>${intakeValue(project.cooperation_source,"cooperation_source")}<br>${esc(project.external_company||"")}</td><td>${intakeValue(project.project_status,"project_status")} / ${intakeValue(project.role)}</td><td>${esc(project.source_lang||"")} → ${esc(project.target_lang||"")}</td><td>${intakeValue(project.start_date)}</td><td>${intakeValue(project.end_date)}</td><td>${intakeValue(project.deadline)}</td><td>${intakeValue(project.remaining_volume)}</td><td style="white-space:pre-wrap;min-width:180px">${esc(project.remarks||"")}</td></tr>`).join(""))}</div>`;
}
async function openIntakeReview(id,targetId){
  const sequence=++intakeDetailRequest;
  try{
    const detail=await intakeRequest("GET",`/submissions/${id}${targetId?`?target_id=${Number(targetId)}`:""}`);
    if(ROLE!=="editor"||sequence!==intakeDetailRequest)return;
    intakeDetail=detail;renderIntakeReview(detail);intakeEl("intakeReview").hidden=false;
    intakeEl("intakeReview").scrollIntoView({block:"start"});
  }catch{}
}
function closeIntakeReview(){++intakeDetailRequest;intakeDetail=null;intakeEl("intakeReview").hidden=true;intakeEl("intakeReview").replaceChildren();}
function renderIntakeReview(detail){
  const proposed=detail.payload,current=detail.current||{},pending=detail.status==="pending",editable=pending||detail.status==="needs_info";
  const basic=Object.entries(intakeFields).map(([key,label])=>`<tr><td>${label}</td><td>${intakeValue(current[key],key)}</td><td${proposed[key]!=null&&proposed[key]!==current[key]?' style="background:#eef8ee"':""}>${proposed[key]==null?'<span class="muted">未填写（保留原值）</span>':intakeValue(proposed[key],key)}</td></tr>`).join("");
  const pairs=proposed.language_pairs.map(pair=>{const old=(current.language_pairs||[]).find(value=>value.source_lang===pair.source_lang&&value.target_lang===pair.target_lang)||{};return `<tr><td>${esc(pair.source_lang)} → ${esc(pair.target_lang)}</td>${Object.keys(intakeRateFields).map(key=>`<td><small>${intakeValue(old[key])}</small> → <b>${intakeValue(pair[key])}</b></td>`).join("")}<td>${intakeValue(old.currency)} → ${intakeValue(pair.currency)}</td></tr>`;}).join("");
  const hasRates=proposed.language_pairs.some(pair=>Object.keys(intakeRateFields).some(key=>pair[key]!=null));
  const today=new Date(), dateValue=`${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-${String(today.getDate()).padStart(2,"0")}`;
  intakeEl("intakeReview").innerHTML=`<div class="toolbar"><h2 style="font-size:17px;margin:0">${esc(proposed.name)} · ${esc(intakeStatusLabels[detail.status])}</h2><span class="count">申请 #${detail.id} / 版本 ${detail.version}</span><button type="button" class="btn-ghost" onclick="closeIntakeReview()">关闭详情</button></div>${detail.revoked?'<p class="danger">邀请已撤销，不能入库。</p>':""}${!detail.bound_translator_id&&detail.candidates.length&&editable?`<div class="field" style="margin:12px 0"><label for="intakeMergeTarget">发现同名或同邮箱记录，请选择合并目标</label><select id="intakeMergeTarget" onchange="openIntakeReview(${detail.id},this.value)"><option value="">请选择已有档案</option>${detail.candidates.map(row=>`<option value="${row.id}"${detail.target_id===row.id?" selected":""}>#${row.id} ${esc(row.name)} · ${esc(row.email||"")}</option>`).join("")}</select></div>`:""}<p class="muted">${detail.target_id?`更新译员 #${detail.target_id}。`:"申请新建译员。"}空白项保留原值；绿色为本次提供的新值。补充说明只留在申请中。</p><div class="table-scroll">${tbl(["资料","目前档案","本次提交"],basic)}</div><h3>语言对与报价</h3><p class="muted">每格为“目前 → 提交”。仅在勾选下方确认项后写入报价；未提交的语言对和费率保留。</p><div class="table-scroll">${tbl(["语言对",...Object.values(intakeRateFields),"币种"],pairs)}</div><h3>本次项目经历</h3><p class="muted">仅新增，完全相同的经历自动跳过。修订或删除旧经历请在译员档案中操作。</p>${intakeProjectTable(proposed.projects||[])}${current.projects?.length?`<details><summary>查看现有项目经历（${current.projects.length} 条）</summary>${intakeProjectTable(current.projects)}</details>`:""}<h3>译员补充说明</h3><p style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(proposed.remarks||"无")}</p>${editable?`<form id="intakeReviewForm"><div class="addrow">${!detail.target_id?`<div class="field"><label for="intakeOnboarding">入库日期</label><input id="intakeOnboarding" type="date" value="${dateValue}"></div><div class="field"><label for="intakeNewStatus">初始状态</label><select id="intakeNewStatus"><option value="Probation">Probation · 试用</option><option value="Active">Active · 活跃</option><option value="Dormant">Dormant · 休眠</option><option value="Blacklisted">Blacklisted · 黑名单</option></select></div><div class="field"><label for="intakeSettlement">结算方式</label><select id="intakeSettlement"><option value="monthly">月结</option><option value="cumulative">累计结</option></select></div>`:""}</div><label style="display:flex;gap:8px;align-items:center;margin:16px 0"><input id="intakeIncludeRates" type="checkbox"${hasRates?"":" disabled"}>已核对报价和单位，同意写入本次提供的语言对费率</label><div class="field"><label for="intakeReviewNote">处理意见（会向译员显示；退回或拒绝时必填）</label><textarea id="intakeReviewNote" rows="3" maxlength="2000">${esc(detail.review_note||"")}</textarea></div><p id="intakeReviewError" class="danger" role="alert"></p><div class="toolbar" style="margin-top:12px">${pending?`<button type="submit" data-action="approve" class="btn-primary"${detail.revoked||(!detail.target_id&&detail.candidates.length)?" disabled":""}>审核通过并入库</button><button type="submit" data-action="needs_info" class="btn-ghost">退回补充</button>`:""}<button type="submit" data-action="reject" class="btn-ghost danger">拒绝申请</button></div></form>`:`<p class="muted">处理人：${esc(detail.reviewed_by||"—")} · ${esc(intakeTime(detail.reviewed_at))}</p><p style="white-space:pre-wrap">${esc(detail.review_note||"")}</p>`}`;
  intakeEl("intakeReviewForm")?.addEventListener("submit",submitIntakeReview);
}
async function submitIntakeReview(event){
  event.preventDefault();const detail=intakeDetail,action=event.submitter?.dataset.action;if(!detail||!action)return;
  const note=intakeEl("intakeReviewNote").value.trim();intakeEl("intakeReviewError").textContent="";
  if(action!=="approve"&&!note){intakeEl("intakeReviewError").textContent="请填写发给译员的处理意见。";intakeEl("intakeReviewNote").focus();return;}
  const body={action,version:detail.version,note,target_id:detail.target_id,profile_fingerprint:detail.profile_fingerprint,include_rates:intakeEl("intakeIncludeRates").checked};
  if(!detail.target_id){body.onboarding_date=intakeEl("intakeOnboarding").value||null;body.status=intakeEl("intakeNewStatus").value;body.settlement_mode=intakeEl("intakeSettlement").value;}
  const buttons=[...event.target.querySelectorAll('button[type="submit"]')].map(button=>({button,disabled:button.disabled}));buttons.forEach(({button})=>button.disabled=true);
  try{await intakeRequest("POST",`/submissions/${detail.id}/review`,body);showToast(action==="approve"?"审核通过，资料已入库":action==="needs_info"?"已退回补充，译员可用原链接修改":"申请已拒绝","success");await loadIntake();if(intakeDetail?.id===detail.id)await openIntakeReview(detail.id);}
  catch(error){if(intakeDetail?.id===detail.id&&intakeEl("intakeReviewError"))intakeEl("intakeReviewError").textContent=error.message;buttons.forEach(({button,disabled})=>button.disabled=disabled);}
}

"use strict";
const token = location.hash.slice(1);
const $ = id => document.getElementById(id);
const form = $("intakeForm");
let languages = [], dirty = false, pairSerial = 0, projectSerial = 0;
const profileFields = ["name", "email", "native_language", "gender", "entity_type", "wechat", "location", "timezone", "domains", "text_types", "cat_tools", "daily_output", "remarks"];
const rateFields = ["translation_rate", "review_rate", "mtpe_rate", "lqa_rate", "lqe_rate"];
const names = {name:"姓名 / Name",email:"邮箱 / Email",native_language:"母语 / Native language",gender:"性别 / Gender",entity_type:"合作主体 / Entity type",language_pairs:"语言对 / Languages",projects:"项目 / Projects",project_name:"项目名称 / Project name",source_lang:"源语言 / Source",target_lang:"目标语言 / Target",currency:"币种 / Currency",daily_output:"日产量 / Daily capacity",consent:"资料使用同意 / Consent"};
function esc(value) {return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function errorText(data) {
  if (Array.isArray(data.detail)) return data.detail.map(e => `${e.loc.filter(p=>p!=="body").map(p=>typeof p==="number"?p+1:(names[p]||p)).join(" · ")}: ${e.msg}`).join("\n");
  return data.detail || "暂时无法完成，请稍后重试 / Unable to complete; please retry";
}
async function request(method="GET", body) {
  const response = await fetch("/api/public/intake", {method,cache:"no-store",headers:{Authorization:`Invite ${token}`,"Content-Type":"application/json"},...(body?{body:JSON.stringify(body)}:{})});
  const data = await response.json();
  if (!response.ok) throw new Error(errorText(data));
  return data;
}
function options(values, selected="", placeholder="请选择 / Select") {
  return `<option value="">${placeholder}</option>` + values.map(([v,label])=>`<option value="${esc(v)}"${v===selected?" selected":""}>${esc(label)}</option>`).join("");
}
function languageOptions(selected) {
  const zh = new Intl.DisplayNames(["zh-CN"],{type:"language"}), en = new Intl.DisplayNames(["en"],{type:"language"});
  return options(languages.map(code=>{
    try {return [code,`${code} · ${zh.of(code)} / ${en.of(code)}`];} catch {return [code,code];}
  }), selected);
}
function pairControls() {
  const pairs = [...$("languagePairs").children];
  pairs.forEach((pair,index)=>{pair.querySelector("strong").textContent=`语言对 ${index+1} / Language pair ${index+1}`;pair.querySelector(".remove").disabled=pairs.length===1;});
  $("addPair").disabled = pairs.length >= 20;
}
function addPair(data={}, focus=false) {
  if ($("languagePairs").children.length >= 20) return;
  const row = document.createElement("div"); row.className="pair"; row.dataset.serial=++pairSerial;
  row.innerHTML=`<div class="pair-top"><strong></strong><button class="remove" type="button">移除 / Remove</button></div><div class="pair-route"><label>源语言 / Source *<select data-key="source_lang" required>${languageOptions(data.source_lang)}</select></label><span aria-hidden="true">→</span><label>目标语言 / Target *<select data-key="target_lang" required>${languageOptions(data.target_lang)}</select></label></div><div class="rates">${rateFields.map((key,i)=>`<label>${["翻译 Translation · /1,000","审校 Review · /1,000","MTPE · /1,000","LQA · /hour","LQE · /hour"][i]}<input data-key="${key}" type="number" min="0" max="99999999.99" step="0.01" value="${esc(data[key])}"></label>`).join("")}<label>币种 / Currency<select data-key="currency">${options([["CNY","CNY · 人民币"],["USD","USD · 美元"],["EUR","EUR · 欧元"]],data.currency)}</select></label></div>`;
  row.querySelector(".remove").addEventListener("click",()=>{row.remove();dirty=true;pairControls();});
  row.addEventListener("input",()=>{row.querySelector('[data-key="currency"]').required=rateFields.some(key=>row.querySelector(`[data-key="${key}"]`).value!=="");});
  $("languagePairs").append(row); pairControls();
  if (focus) row.querySelector("select").focus();
}
function addProject(data={},focus=false) {
  if ($("projects").children.length >= 30) return;
  const row=document.createElement("div");row.className="project";row.dataset.serial=++projectSerial;
  const input=(key,label,type="text",max="200")=>`<label>${label}<input data-key="${key}" type="${type}" ${type==="text"?`maxlength="${max}"`:type==="number"?'min="0" max="999999999999.99" step="0.01"':""} value="${esc(data[key])}"${key==="project_name"?" required":""}></label>`;
  row.innerHTML=`<div class="project-top"><strong>项目 / Project</strong><button class="remove" type="button">移除 / Remove</button></div><p class="current-guide" hidden>当前项目必填开始日期、剩余字数及截止或结束日期。<br>Ongoing work requires a start date, remaining volume and an end date or deadline.</p><div class="fields">${input("project_name","项目名称 / Project name *")}<label>状态 / Status *<select data-key="project_status" required>${options([["past","过往 / Past"],["current","当前 / Ongoing"]],data.project_status||"past")}</select></label><label>合作来源 / Cooperation *<select data-key="cooperation_source" required>${options([["external","外部合作 / External"],["our_company","Langlobal 合作 / With Langlobal"]],data.cooperation_source||"external")}</select></label>${input("external_company","合作公司 / Company")}<label>角色 / Role<select data-key="role">${options([["翻译","翻译 / Translation"],["审校","审校 / Review"],["MTPE","MTPE"],["LQA","LQA"],["LQE","LQE"],["一口价","一口价 / Fixed-price"],["其他","其他 / Other"]],data.role)}</select></label><label>源语言 / Source<select data-key="source_lang">${languageOptions(data.source_lang)}</select></label><label>目标语言 / Target<select data-key="target_lang">${languageOptions(data.target_lang)}</select></label>${input("start_date","开始日期 / Start date","date")}${input("end_date","结束日期 / End date","date")}${input("deadline","截止日期 / Deadline","date")}${input("remaining_volume","剩余字数 / Remaining words","number")}<label class="full">项目说明 / Project notes<textarea data-key="remarks" rows="2" maxlength="2000">${esc(data.remarks)}</textarea></label></div>`;
  function requirements(){const current=row.querySelector('[data-key="project_status"]').value==="current";row.querySelector(".current-guide").hidden=!current;["start_date","remaining_volume"].forEach(k=>row.querySelector(`[data-key="${k}"]`).required=current);row.querySelector('[data-key="deadline"]').required=current&&!row.querySelector('[data-key="end_date"]').value;}
  row.addEventListener("input",requirements);requirements();
  row.querySelector(".remove").addEventListener("click",()=>{row.remove();dirty=true;$("projectEmpty").hidden=!!$("projects").children.length;$("addProject").disabled=false;});
  $("projects").append(row);$("projectEmpty").hidden=true;$("addProject").disabled=$("projects").children.length>=30;
  if(focus)row.querySelector("input").focus();
}
function rowData(row) {const result={};row.querySelectorAll("[data-key]").forEach(el=>{const value=el.value.trim();if(value!=="")result[el.dataset.key]=el.type==="number"?Number(value):value;});return result;}
function payload() {const data={};profileFields.forEach(key=>{const el=form.elements[key],value=el.value.trim();if(value!=="")data[key]=el.type==="number"?Number(value):value;});data.language_pairs=[...$("languagePairs").children].map(rowData);data.projects=[...$("projects").children].map(rowData);data.consent=form.elements.consent.checked;return data;}
function showReceipt(row){
  dirty=false;$("workspace").hidden=true;$("receipt").hidden=false;
  const titles={pending:"资料已提交 / Profile submitted",approved:"资料已入库 / Profile approved",rejected:"申请已处理 / Application reviewed"};
  $("receiptTitle").textContent=titles[row.status]||row.status;
  $("receiptText").textContent=row.status==="pending"?"资源负责人正在等待审核您的资料。无需重复提交。\nYour profile is waiting for review. No need to submit again.":row.status==="approved"?"谢谢，资源负责人已确认您的资料。\nThank you. Your coordinator has approved your profile.":"资源负责人未通过本次申请。详情请查看下方意见。\nThis application was not approved. See the note below.";
  $("receiptMeta").textContent=`回执 / Receipt #${row.id} · ${new Date(row.submitted_at).toLocaleString()}`;
  $("receiptNote").hidden=!row.review_note;$("receiptNote").textContent=row.review_note||"";
  $("receipt").focus();
}
async function load(){
  $("loading").hidden=false;$("pageError").hidden=true;$("receipt").hidden=true;
  try{
    if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw new Error("请打开资源负责人发送的完整邀请链接。\nOpen the full invitation link sent by your coordinator.");
    const context=await request();languages=context.languages;
    if(context.submission&&context.submission.status!=="needs_info"){showReceipt(context.submission);return;}
    form.reset();$("languagePairs").replaceChildren();$("projects").replaceChildren();$("projectEmpty").hidden=false;
    $("inviteEmail").textContent=context.email;$("inviteExpiry").textContent=`有效至 / Valid until ${new Date(context.expires_at).toLocaleDateString()}`;
    $("updateNote").hidden=!context.is_update;$("reopenNote").hidden=!context.submission;
    $("reopenNote").textContent=context.submission?`请补充资料后重新提交 / Please update and resubmit\n${context.submission.review_note||""}`:"";
    const draft=context.draft||{};
    profileFields.forEach(key=>{form.elements[key].value=draft[key]??"";});form.elements.email.value=context.email;
    (draft.language_pairs||[{}]).forEach(pair=>addPair(pair));(draft.projects||[]).forEach(project=>addProject(project));
    $("workspace").hidden=false;dirty=false;
  }catch(error){$("pageError").textContent=error.message;$("pageError").hidden=false;$("workspace").hidden=true;}
  finally{$("loading").hidden=true;}
}
form.addEventListener("input",()=>dirty=true);
form.addEventListener("submit",async event=>{event.preventDefault();if(!form.reportValidity())return;const button=$("submitButton");button.disabled=true;button.textContent="正在提交 / Submitting…";$("formError").hidden=true;try{showReceipt(await request("POST",payload()));}catch(error){$("formError").textContent=error.message;$("formError").hidden=false;$("formError").scrollIntoView({block:"center"});}finally{button.disabled=false;button.textContent="提交资料 / Submit profile →";}});
$("addPair").addEventListener("click",()=>{addPair({},true);dirty=true;});
$("addProject").addEventListener("click",()=>{addProject({},true);dirty=true;});
$("refreshStatus").addEventListener("click",load);
$("brandLink").addEventListener("click",event=>{event.preventDefault();window.scrollTo({top:0});});
document.querySelectorAll("nav a").forEach(link=>link.addEventListener("click",event=>{event.preventDefault();document.querySelector(link.getAttribute("href")).scrollIntoView({block:"start"});}));
window.addEventListener("beforeunload",event=>{if(dirty){event.preventDefault();event.returnValue="";}});
load();

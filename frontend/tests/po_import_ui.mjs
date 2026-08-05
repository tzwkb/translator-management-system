import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /id="poImportFile"[^>]+type="file"[^>]+accept="\.xlsx"/);
assert.match(html, /导入标准 PO Excel/);
assert.match(html, /<button class="btn-ghost edit-only" onclick="exportPOLog\(\)">导出 PO Log<\/button>/);
assert.match(html, /body\.viewer \.edit-only \{ display:none !important; \}/);
assert.match(html, /id="projectlistPOState"/);
assert.match(html, /导入 Projectlist/);
assert.match(html, /function importProjectlistFile/);
assert.match(html, /function renderProjectlistPreview/);
assert.match(html, /function poImportPath/);
assert.match(html, /projectlist_po_state/);
assert.match(html, /function importPOFile/);
assert.match(html, /\/api\/import\/po/);
assert.match(html, /确认写入以上有效行/);
assert.match(html, /跳过已结算/);
assert.match(html, /已有 PO 导入正在处理/);
assert.match(html, /没有可写入的有效行/);
assert.match(html, /skipped_dup_po/);
assert.match(html, /invalid_rows/);

{
  const source=html.match(/function exportPOLog\(\) \{[\s\S]*?\n\}/)?.[0];
  assert.ok(source,"PO Log export function should exist");
  const calls=[];
  const context={downloadAuth:(...args)=>{calls.push(args);}};
  vm.createContext(context);
  vm.runInContext(source,context);
  await context.exportPOLog();
  assert.deepEqual(calls,[["/api/export/po-log","PO_Log.xlsx"]]);
}

const importSource=html.slice(
  html.indexOf("function projectlistImportState"),
  html.indexOf("function selectedPOMonth"),
);
assert.ok(importSource.length>0,"PO import functions should be extractable");

function createHarness({confirmResult=true,responses,previewGate}={}) {
  const elements=new Map([
    ["projectlistPOState",{value:"unchecked"}],
    ["poImportResult",{textContent:"",title:""}],
  ]);
  const events=[];
  const queuedResponses=responses||[
    {
      preview:true,source_format:"projectlist",projectlist_po_state:"unchecked",
      ready:2,selected_rows:4,checked_rows:1,unchecked_rows:3,
      skipped_settled:1,skipped_dup_po:0,invalid_rows:[{row:9,error:"译员未匹配"}],
      preview_rows:[{source_row:8,translator_name:"译员甲",project:"项目 A",expected_amount:50,currency:"USD",action:"import"}],
    },
    {
      preview:false,source_format:"projectlist",projectlist_po_state:"unchecked",
      imported:2,skipped_settled:1,skipped_dup_po:1,
      invalid_rows:[{sheet:"Projectlist",row:9,error:"译员未匹配"}],
    },
  ];
  let requestCount=0;
  class FakeFormData {
    constructor(){this.values=new Map();}
    append(key,value){this.values.set(key,value);}
    get(key){return this.values.get(key);}
  }
  const context={
    console:{warn(){},log(){},error(){}},URLSearchParams,encodeURIComponent,FormData:FakeFormData,
    document:{getElementById:id=>elements.get(id)},
    showToast(message,type){events.push({kind:"toast",message,type});},
    failField(message){events.push({kind:"failure",message});return false;},
    confirm(message){
      events.push({kind:"confirm",message});
      elements.get("projectlistPOState").value="checked";
      return confirmResult;
    },
    async apiForm(method,path,form){
      events.push({kind:"request",method,path,file:form.get("file")});
      const firstRequest=requestCount++===0;
      if(firstRequest&&previewGate)await previewGate.promise;
      return queuedResponses.shift();
    },
    loadPO(){events.push({kind:"load"});},
    PO_IMPORT_FILE:null,
  };
  vm.createContext(context);
  vm.runInContext(importSource,context);
  return {context,elements,events};
}

{
  const {context,elements,events}=createHarness();
  const file={name:"Projectlist.xlsx"};
  const input={files:[file],value:"Projectlist.xlsx"};
  await context.importPOFile(input);
  const requests=events.filter(event=>event.kind==="request");
  assert.equal(requests.length,2,"confirmation should be followed by the formal import");
  const confirmIndex=events.findIndex(event=>event.kind==="confirm");
  assert.ok(events.indexOf(requests[0])<confirmIndex,"preview should finish before confirmation");
  assert.ok(confirmIndex<events.indexOf(requests[1]),"formal import should start after confirmation");
  const previewUrl=new URL(requests[0].path,"http://local");
  const importUrl=new URL(requests[1].path,"http://local");
  assert.equal(previewUrl.searchParams.get("preview"),"true");
  assert.equal(importUrl.searchParams.has("preview"),false);
  assert.equal(previewUrl.searchParams.get("projectlist_po_state"),"unchecked");
  assert.equal(importUrl.searchParams.get("projectlist_po_state"),"unchecked","preview and write must use the same state snapshot even if the selector changes during confirmation");
  assert.equal(requests[0].file,file);
  assert.equal(requests[1].file,file);
  assert.equal(input.value,"");
  assert.match(elements.get("poImportResult").textContent,/导入 2 行，跳过已结算 1 行，跳过重复 1 行，来源冲突 0 行，其他错误 1 行/);
  assert.match(elements.get("poImportResult").title,/Projectlist 第 9 行：译员未匹配/);
  assert.equal(events.at(-1).kind,"load");
}

{
  const {context,events}=createHarness({confirmResult:false});
  await context.importProjectlistFile({files:[{name:"Projectlist.xlsx"}],value:"Projectlist.xlsx"});
  assert.equal(events.filter(event=>event.kind==="request").length,1,"cancelled confirmation must not write");
  assert.equal(events.some(event=>event.kind==="load"),false);
}

{
  let releasePreview;
  const previewGate={promise:new Promise(resolve=>{releasePreview=resolve;})};
  const {context,events}=createHarness({confirmResult:false,previewGate});
  const firstFile={name:"first.xlsx"};
  const firstInput={files:[firstFile],value:"first.xlsx"};
  const firstImport=context.importPOFile(firstInput);
  const secondInput={files:[{name:"second.xlsx"}],value:"second.xlsx"};
  await context.importProjectlistFile(secondInput);
  assert.equal(events.filter(event=>event.kind==="request").length,1,"a second same-page import must not start while preview is pending");
  assert.deepEqual(
    events.filter(event=>event.kind==="failure").map(event=>event.message),
    ["已有 PO 导入正在处理，请稍候"],
  );
  assert.equal(secondInput.value,"","the blocked file input should be reset");
  assert.equal(context.PO_IMPORT_FILE,firstFile,"the active import lock must remain owned by the first file");
  releasePreview();
  await firstImport;
  assert.equal(context.PO_IMPORT_FILE,null,"the import lock should release when the first flow ends");
  assert.equal(firstInput.value,"");
}

{
  const zeroReadyPreview={
    preview:true,source_format:"projectlist",projectlist_po_state:"unchecked",
    ready:0,selected_rows:3,checked_rows:0,unchecked_rows:3,
    skipped_settled:0,skipped_dup_po:3,invalid_rows:[],preview_rows:[],
  };
  const {context,elements,events}=createHarness({responses:[zeroReadyPreview]});
  const input={files:[{name:"already-imported.xlsx"}],value:"already-imported.xlsx"};
  await context.importProjectlistFile(input);
  assert.equal(events.filter(event=>event.kind==="request").length,1,"ready=0 must stop after preview");
  assert.equal(events.some(event=>event.kind==="confirm"),false,"ready=0 must not ask for write confirmation");
  assert.equal(events.some(event=>event.kind==="load"),false,"ready=0 must not reload PO data as if a write occurred");
  assert.match(elements.get("poImportResult").textContent,/已预览：可导入 0 行，跳过 3 行，错误 0 行/);
  assert.ok(events.some(event=>event.kind==="toast"&&event.message==="预览完成，没有可写入的有效行"));
  assert.equal(context.PO_IMPORT_FILE,null);
  assert.equal(input.value,"");
}

console.log("PO import UI is wired");

import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");

assert.match(html, /const TRF = \[[\s\S]*"gender","entity_type"/);
assert.match(html, /id="f-gender"[\s\S]*value="male">男/);
assert.match(html, /id="f-entity_type"[\s\S]*value="individual">个人译员/);
assert.match(html, /<th>姓名<\/th><th>主体<\/th><th>性别<\/th>/);
assert.match(html, /function genderZh/);
assert.match(html, /function entityTypeZh/);

assert.match(html, /const SUBS = \[\["projects","项目经历"\]/);
assert.match(html, /function subProjects/);
assert.match(html, /function openProjectEditor/);
assert.match(html, /function saveProjectExperience/);
assert.match(html, /function deleteProjectExperience/);
assert.match(html, /当前项目/);
assert.match(html, /过往项目/);
assert.match(html, /与我司合作/);
assert.match(html, /与别家合作/);
assert.match(html, /method[\s\S]*"PUT"[\s\S]*project-experiences/);
assert.match(html, /api\("DELETE", `\/api\/translators\/\$\{CUR\.id\}\/project-experiences\/\$\{projectId\}`/);
assert.match(html, /current_projects/);
assert.match(html, /class="project-tags"/);

for (const id of ["pe-start", "pe-end", "pe-deadline"]) {
  assert.match(html, new RegExp(`id="${id}"[^>]+type="date"`));
}
assert.match(html, /id="pe-volume" type="number" min="0"/);

console.log("project experience and profile fields have a complete UI loop");

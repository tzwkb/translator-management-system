import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import test from "node:test";

test("build bundles the finished Chinese workbench", async () => {
  const assetNames = await readdir(new URL("../dist/client/assets/", import.meta.url));
  const workbenchName = assetNames.find((name) => name.startsWith("workbench-") && name.endsWith(".js"));
  assert.ok(workbenchName);
  const [worker, workbench] = await Promise.all([
    readFile(new URL("../dist/server/index.js", import.meta.url), "utf8"),
    readFile(new URL(`../dist/client/assets/${workbenchName}`, import.meta.url), "utf8"),
  ]);
  assert.match(worker, /Lingua Control/);
  assert.match(workbench, /受控 Demo/);
  assert.match(workbench, /总览/);
  assert.match(workbench, /译员/);
  assert.match(workbench, /费率/);
  assert.match(workbench, /PO/);
  assert.match(workbench, /审核/);
  assert.doesNotMatch(worker + workbench, /codex-preview|SkeletonPreview|react-loading-skeleton/);
});

test("build packages Sites hosting metadata, D1 migration, worker, and social image", async () => {
  const migrationNames = (await readdir(new URL("../dist/.openai/drizzle/", import.meta.url)))
    .filter((name) => name.endsWith(".sql"));
  assert.equal(migrationNames.length, 1);
  await Promise.all([
    access(new URL("../dist/server/index.js", import.meta.url)),
    access(new URL("../dist/.openai/hosting.json", import.meta.url)),
    access(new URL(`../dist/.openai/drizzle/${migrationNames[0]}`, import.meta.url)),
    access(new URL("../dist/client/og.png", import.meta.url)),
  ]);
  const hosting = JSON.parse(await readFile(new URL("../dist/.openai/hosting.json", import.meta.url), "utf8"));
  assert.deepEqual(hosting, {
    project_id: "appgprj_6a5db4834ed08191af5037da162d68f6",
    d1: "DB",
    r2: null,
  });
  await assert.rejects(access(new URL("../app/_sites-preview", import.meta.url)));
  const packageJson = await readFile(new URL("../package.json", import.meta.url), "utf8");
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});

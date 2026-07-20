import assert from "node:assert/strict";
import test from "node:test";
import { GET } from "../app/api/health/route";

test("health endpoint returns a machine-readable success response", async () => {
  const response = await GET();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "application/json");
  assert.deepEqual(await response.json(), {
    status: "ok",
    service: "lingua-control-demo",
  });
});

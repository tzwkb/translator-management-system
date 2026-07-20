import { env } from "cloudflare:workers";
import type { D1DatabaseLike } from "./repository";

export function getDatabase(): D1DatabaseLike {
  if (!env.DB) {
    throw new Error("Cloudflare D1 binding DB is unavailable");
  }
  return env.DB as unknown as D1DatabaseLike;
}

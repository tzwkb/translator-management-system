import { getDatabase } from "../../../db";
import { loadWorkspace } from "../../../db/repository";
import { errorResponse, json } from "../../../lib/api";

export async function GET(): Promise<Response> {
  try {
    return json(await loadWorkspace(getDatabase()));
  } catch (error) {
    return errorResponse(error);
  }
}

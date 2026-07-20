import { getDatabase } from "../../../db";
import { loadWorkspace } from "../../../db/repository";
import { errorResponse } from "../../../lib/api";
import { buildExportSheets, createXlsx } from "../../../lib/excel";

export async function GET(): Promise<Response> {
  try {
    const workspace = await loadWorkspace(getDatabase());
    const bytes = createXlsx(
      buildExportSheets(workspace.translators, workspace.purchaseOrders),
    );
    return new Response(bytes as BodyInit, {
      status: 200,
      headers: {
        "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "content-disposition": 'attachment; filename="lingua-control-demo.xlsx"',
        "cache-control": "no-store",
      },
    });
  } catch (error) {
    return errorResponse(error);
  }
}

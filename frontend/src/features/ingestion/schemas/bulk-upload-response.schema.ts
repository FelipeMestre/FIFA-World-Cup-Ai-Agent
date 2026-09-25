import { z } from "zod";

import type { BulkUploadFileResult } from "@/features/ingestion/types";

const bulkFileResultSchema = z.object({
  filename: z.string(),
  table_name: z.string().nullable(),
  accepted: z.boolean(),
  reason: z.string().nullable(),
});

/** `POST /admin/ingestion/bulk-synthetic-upload`'s 201 body: at least one
 * file resolved to a known table, so a job was created.
 */
export const bulkUploadSuccessSchema = z.object({
  job_id: z.number().int(),
  status: z.string(),
  files: z.array(bulkFileResultSchema),
});

/** The `detail` object FastAPI's `HTTPException` wraps its 400 body in when
 * zero uploaded files resolved to a known table -- no job was created.
 */
export const bulkUploadRejectionDetailSchema = z.object({
  message: z.string(),
  files: z.array(bulkFileResultSchema),
});

export function toBulkUploadFileResult(
  row: z.infer<typeof bulkFileResultSchema>,
): BulkUploadFileResult {
  return {
    filename: row.filename,
    tableName: row.table_name,
    accepted: row.accepted,
    reason: row.reason,
  };
}

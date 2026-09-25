import {
  bulkUploadRejectionDetailSchema,
  bulkUploadSuccessSchema,
  toBulkUploadFileResult,
} from "@/features/ingestion/schemas/bulk-upload-response.schema";
import type { BulkUploadResult } from "@/features/ingestion/types";
import { ApiError } from "@/lib/api/client";

/** Uploads a batch of synthetic dataset CSVs as `multipart/form-data` to our
 * own Route Handler. Not built on `fetchJson` like the feature's other API
 * clients: a 400 here (zero files accepted) is not a bare error string, it's
 * a structured per-file rejection list the caller renders as a real result,
 * so this parses both the 201 and 400 bodies itself instead of collapsing
 * the 400 into a thrown `ApiError`.
 */
export async function uploadBulkSyntheticCsvs(files: File[]): Promise<BulkUploadResult> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch("/api/admin/ingestion/bulk-synthetic-upload", {
    method: "POST",
    body: formData,
  });
  const payload: unknown = await response.json().catch(() => null);

  if (response.ok) {
    const parsed = bulkUploadSuccessSchema.parse(payload);
    return {
      jobId: parsed.job_id,
      status: parsed.status,
      files: parsed.files.map(toBulkUploadFileResult),
    };
  }

  if (response.status === 400 && payload !== null && typeof payload === "object") {
    const detail = bulkUploadRejectionDetailSchema.safeParse((payload as { detail?: unknown }).detail);
    if (detail.success) {
      return {
        jobId: null,
        status: null,
        files: detail.data.files.map(toBulkUploadFileResult),
      };
    }
  }

  const detailMessage =
    payload !== null && typeof payload === "object" && typeof (payload as { detail?: unknown }).detail === "string"
      ? (payload as { detail: string }).detail
      : `Request failed with status ${response.status}`;
  throw new ApiError(detailMessage, response.status);
}

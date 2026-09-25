import { describe, expect, it } from "vitest";

import {
  bulkUploadRejectionDetailSchema,
  bulkUploadSuccessSchema,
  toBulkUploadFileResult,
} from "@/features/ingestion/schemas/bulk-upload-response.schema";

describe("bulkUploadSuccessSchema / toBulkUploadFileResult", () => {
  it("maps a 201 response's snake_case files to the camelCase domain shape", () => {
    const parsed = bulkUploadSuccessSchema.parse({
      job_id: 12,
      status: "queued",
      files: [
        { filename: "teams.csv", table_name: "team", accepted: true, reason: null },
        {
          filename: "unknown.csv",
          table_name: null,
          accepted: false,
          reason: "unrecognized filename 'unknown.csv': does not match any known table",
        },
      ],
    });

    expect(parsed.job_id).toBe(12);
    expect(parsed.files.map(toBulkUploadFileResult)).toEqual([
      { filename: "teams.csv", tableName: "team", accepted: true, reason: null },
      {
        filename: "unknown.csv",
        tableName: null,
        accepted: false,
        reason: "unrecognized filename 'unknown.csv': does not match any known table",
      },
    ]);
  });
});

describe("bulkUploadRejectionDetailSchema", () => {
  it("parses the 400 body's nested detail object when zero files were accepted", () => {
    const detail = bulkUploadRejectionDetailSchema.parse({
      message: "no uploaded file resolved to a known synthetic dataset table",
      files: [
        {
          filename: "random.csv",
          table_name: null,
          accepted: false,
          reason: "unrecognized filename 'random.csv': does not match any known table",
        },
      ],
    });

    expect(detail.message).toBe("no uploaded file resolved to a known synthetic dataset table");
    expect(detail.files.map(toBulkUploadFileResult)).toEqual([
      {
        filename: "random.csv",
        tableName: null,
        accepted: false,
        reason: "unrecognized filename 'random.csv': does not match any known table",
      },
    ]);
  });
});

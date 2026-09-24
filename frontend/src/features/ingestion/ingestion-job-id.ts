const JOB_ID_PATTERN = /^\d+$/;

/** `ingestion_job.id` is a plain integer primary key. */
export function isIngestionJobId(value: string): boolean {
  return JOB_ID_PATTERN.test(value);
}

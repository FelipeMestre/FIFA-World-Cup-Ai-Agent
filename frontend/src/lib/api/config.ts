/**
 * Server-only backend configuration. Never imported from a client component --
 * the browser talks to our own Route Handlers (see `app/api/*`), never to the
 * FastAPI backend directly, so this URL is never exposed to client JS.
 */
export const BACKEND_API_URL =
  process.env.BACKEND_API_URL ?? "http://localhost:8000/api/v1";

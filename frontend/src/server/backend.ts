import "server-only";

const API_URL = process.env.APEX_API_URL ?? "http://localhost:8000/api/v1";

type CallOptions = {
  method?: string;
  body?: string;
  accessToken?: string;
  contentType?: string | null;
  locale?: string;
};

/**
 * One server-to-server call to FastAPI. Because this only ever runs on the
 * Next.js server, the browser never talks to the backend directly — which is
 * why the backend needs no CORS configuration.
 */
export function callBackend(
  path: string,
  { method = "GET", body, accessToken, contentType, locale }: CallOptions = {},
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (locale) headers["Accept-Language"] = locale;
  if (body !== undefined)
    headers["Content-Type"] = contentType ?? "application/json";

  return fetch(`${API_URL}${path}`, {
    method,
    body,
    headers,
    cache: "no-store",
  });
}

/** Unwrap a `ResultWithData` success body, or null on any failure. */
export async function backendData<T>(res: Response): Promise<T | null> {
  if (!res.ok) return null;
  try {
    const envelope = (await res.json()) as { data?: T | null };
    return envelope.data ?? null;
  } catch {
    return null;
  }
}

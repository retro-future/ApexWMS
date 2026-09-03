/**
 * Browser-side API client.
 *
 * Everything goes to the Next.js proxy at /api/backend/* — same origin, so the
 * httpOnly session cookie rides along automatically and no token ever touches
 * JavaScript. The proxy attaches the bearer and refreshes it when it expires.
 *
 * Two shapes have to be normalised here so pages never see them:
 *   - success bodies are enveloped (`{success, data}` / `{success, data, pageIndex, ...}`)
 *   - failure bodies are NOT enveloped; they are `{detail: ...}` where `detail`
 *     is a plain string for domain errors but an *array* of issues for pydantic
 *     request validation.
 */

import { CSRF_HEADERS } from "@/lib/csrf";

const PROXY_PREFIX = "/api/backend";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** A uniqueness violation the form should show on a field. */
  get isConflict() {
    return this.status === 409;
  }

  get isForbidden() {
    return this.status === 403;
  }
}

type Envelope<T> = {
  success: boolean;
  message?: string | null;
  error?: string | null;
  data?: T | null;
};

type PagedEnvelope<T> = Envelope<T[]> & {
  pageIndex: number;
  pageSize: number;
  pagesCount: number;
  totalItems: number;
};

export type Paged<T> = {
  items: T[];
  pageIndex: number;
  pageSize: number;
  pagesCount: number;
  totalItems: number;
};

type PydanticIssue = { loc?: unknown[]; msg?: string };

/**
 * `detail` is a plain string for domain errors but an array of pydantic
 * issues for request-validation failures. Both reach the UI, so both have to
 * turn into one readable sentence.
 */
export function messageFromDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const parts = (detail as PydanticIssue[])
      .map((issue) => {
        // loc is like ["body", "email"] — the leading source is noise.
        const field = Array.isArray(issue.loc)
          ? issue.loc.filter((p) => p !== "body" && p !== "query").join(".")
          : "";
        return field ? `${field}: ${issue.msg ?? ""}` : (issue.msg ?? "");
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }

  return fallback;
}

async function request(
  path: string,
  init: RequestInit & { method: string },
): Promise<Response> {
  const res = await fetch(`${PROXY_PREFIX}${path}`, {
    ...init,
    headers: {
      ...CSRF_HEADERS,
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  if (res.ok) return res;

  let detail: unknown;
  try {
    detail = (await res.json())?.detail;
  } catch {
    detail = undefined;
  }

  // The session is gone for good — the proxy already tried to refresh it.
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login?expired=1";
  }

  throw new ApiError(res.status, messageFromDetail(detail, res.statusText));
}

function body(payload: unknown): string | undefined {
  return payload === undefined ? undefined : JSON.stringify(payload);
}

/** GET an enveloped single resource, returning the unwrapped payload. */
export async function apiGet<T>(path: string): Promise<T> {
  const res = await request(path, { method: "GET" });
  const envelope = (await res.json()) as Envelope<T>;
  return envelope.data as T;
}

/** GET a paged list, returning a flattened shape. */
export async function apiGetPaged<T>(path: string): Promise<Paged<T>> {
  const res = await request(path, { method: "GET" });
  const envelope = (await res.json()) as PagedEnvelope<T>;
  return {
    items: envelope.data ?? [],
    pageIndex: envelope.pageIndex,
    pageSize: envelope.pageSize,
    pagesCount: envelope.pagesCount,
    totalItems: envelope.totalItems,
  };
}

/**
 * Write requests. Several endpoints answer 204 with no body
 * (change-password, role change), hence the `null` return.
 */
export async function apiSend<T>(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  payload?: unknown,
): Promise<T | null> {
  const res = await request(path, { method, body: body(payload) });
  if (res.status === 204) return null;
  const envelope = (await res.json()) as Envelope<T>;
  return (envelope.data ?? null) as T | null;
}

/** Build a query string, dropping empty values so filters stay optional. */
export function queryString(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

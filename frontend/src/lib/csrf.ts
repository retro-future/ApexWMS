/**
 * A cross-site HTML form is the only way another page can send a request that
 * carries our cookies, and a form cannot set headers. So the mere presence of
 * this one proves the request came from our own code.
 */
export const CSRF_HEADER = "x-apex-request";

export const CSRF_HEADERS = { [CSRF_HEADER]: "1" } as const;

const configuredBase = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`API request failed (${status})`);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  if (!configuredBase) throw new Error("VITE_API_BASE_URL is required");
  const base = new URL(configuredBase);
  if (
    !["http:", "https:"].includes(base.protocol) ||
    !base.pathname.endsWith("/")
  ) {
    throw new Error("VITE_API_BASE_URL must be an HTTP(S) URL ending in /");
  }
  const url = new URL(path, base);
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) {
    throw new Error("API path must remain within the configured API base");
  }
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.json() as Promise<T>;
}

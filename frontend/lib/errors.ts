import { ApiError } from "./api";

/** Convierte cualquier error en un mensaje comprensible traducido (usa el `code` estable de la API). */
export function errorMessage(err: unknown, t: { (key: string): string; has: (key: string) => boolean }): string {
  if (err instanceof ApiError) {
    if (t.has(err.code)) return t(err.code);
    if (err.status === 429) return t("RATE_LIMITED");
    return t("generic");
  }
  if (err instanceof TypeError) return t("network");
  return t("generic");
}

/** Errores de validación 422 -> { campo: mensaje }. */
export function fieldErrors(err: unknown): Record<string, string> {
  if (!(err instanceof ApiError) || err.code !== "VALIDATION_ERROR" || !Array.isArray(err.details)) return {};
  const out: Record<string, string> = {};
  for (const d of err.details as { field: string; message: string }[]) {
    if (d.field && !out[d.field]) out[d.field] = d.message.replace(/^Value error, /, "");
  }
  return out;
}

/** URL del backend para llamadas desde el SERVIDOR de Next. Acepta con o sin "http(s)://" (Render a veces entrega solo host:puerto). */
export function apiBase(): string {
  const raw = (process.env.API_INTERNAL_URL || "http://localhost:8000").replace(/\/$/, "");
  return /^https?:\/\//.test(raw) ? raw : `http://${raw}`;
}

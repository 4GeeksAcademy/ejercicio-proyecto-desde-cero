import type { ReactNode } from "react";

const tone = {
  error: "bg-bad-soft text-bad border-bad",
  success: "bg-ok-soft text-ok border-ok",
  info: "bg-info-soft text-info border-info",
  warning: "bg-warn-soft text-warn border-warn",
} as const;

/** Mensajes anunciados por lectores de pantalla: role=alert para errores, role=status para el resto. */
export function Alert({ kind = "info", children }: { kind?: keyof typeof tone; children: ReactNode }) {
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-lg border px-4 py-3 text-sm ${tone[kind]}`}>
      {children}
    </div>
  );
}

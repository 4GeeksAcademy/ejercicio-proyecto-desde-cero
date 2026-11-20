"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";

/** Botón que pide un motivo obligatorio antes de ejecutar (rechazar, cancelar, reembolsar…). */
export function ReasonAction({ label, variant = "secondary", onConfirm }: {
  label: string; variant?: "secondary" | "danger"; onConfirm: (reason: string) => Promise<void>;
}) {
  const t = useTranslations("admin");
  const tc = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [id] = useState(() => `reason-${Math.random().toString(36).slice(2)}`);

  if (!open) return <Button variant={variant} className="min-h-9 px-3 py-1" onClick={() => setOpen(true)}>{label}</Button>;
  return (
    <form
      className="space-y-2"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await onConfirm(reason);
          setOpen(false);
          setReason("");
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor={id} className="block text-xs font-medium">{t("reasonLabel")}</label>
      <input id={id} value={reason} onChange={(e) => setReason(e.target.value)} minLength={3} maxLength={300} required className="block w-full rounded border border-line bg-surface-2 px-2 py-1" />
      <div className="flex gap-2">
        <Button type="submit" variant={variant} busy={busy} className="min-h-9 px-3 py-1">{tc("confirm")}</Button>
        <Button type="button" variant="ghost" className="min-h-9 px-3 py-1" onClick={() => setOpen(false)}>{tc("cancel")}</Button>
      </div>
    </form>
  );
}

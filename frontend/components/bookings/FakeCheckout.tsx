"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

/** Simulador de pasarela SOLO para desarrollo (el backend rechaza /dev/* fuera de development/testing). */
export function FakeCheckout({ reference }: { reference: string }) {
  const t = useTranslations("fakePay");
  const te = useTranslations("errors");
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function simulate(outcome: "success" | "failure") {
    setBusy(true);
    setError(null);
    try {
      await api(`/dev/payments/${encodeURIComponent(reference)}/simulate?outcome=${outcome}`, { method: "POST" });
      router.push("/account");
    } catch (e) {
      setError(errorMessage(e, te));
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4 rounded-xl border border-line bg-surface-2 p-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <p className="text-sm text-muted">{t("help")}</p>
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div className="flex flex-wrap gap-3">
        <Button busy={busy} onClick={() => simulate("success")}>{t("success")}</Button>
        <Button variant="secondary" busy={busy} onClick={() => simulate("failure")}>{t("failure")}</Button>
      </div>
    </div>
  );
}

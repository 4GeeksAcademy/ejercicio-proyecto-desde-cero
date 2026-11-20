"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { api, newIdempotencyKey } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { Booking } from "@/lib/types";
import { useAuth } from "@/components/auth/AuthProvider";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClass } from "@/components/ui/Button";

export function BookButton({ courseId, slug, disabledReason }: { courseId: string; slug: string; disabledReason?: string }) {
  const t = useTranslations("course");
  const te = useTranslations("errors");
  const locale = useLocale();
  const router = useRouter();
  const { user, loading } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alreadyBooked, setAlreadyBooked] = useState(false);
  // Una clave por "intento de usuario": un doble clic NO crea dos reservas (idempotencia).
  const [key] = useState(newIdempotencyKey);

  if (disabledReason) return <Alert kind="warning">{disabledReason}</Alert>;

  if (!loading && !user) {
    return (
      <Link
        href="/login"
        className={buttonClass("primary", "w-full")}
        onClick={() => sessionStorage.setItem("tallerya:next", JSON.stringify({ pathname: "/courses/[slug]", params: { slug } }))}
      >
        {t("loginToReserve")}
      </Link>
    );
  }

  async function reserve() {
    setBusy(true);
    setError(null);
    try {
      const b = await api<Booking>(`/bookings?locale=${locale}`, { method: "POST", body: { course_id: courseId }, idempotencyKey: key });
      router.push({ pathname: "/account/bookings/[id]", params: { id: b.id } });
    } catch (e) {
      setAlreadyBooked((e as { code?: string }).code === "ALREADY_BOOKED");
      setError(errorMessage(e, te));
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <Button className="w-full" busy={busy || loading} onClick={reserve}>
        {busy ? t("reserving") : t("reserve")}
      </Button>
      {error ? <Alert kind="error">{error}</Alert> : null}
      {alreadyBooked ? (
        <Link href="/account" className="text-sm font-semibold underline">{t("viewBooking")}</Link>
      ) : null}
    </div>
  );
}

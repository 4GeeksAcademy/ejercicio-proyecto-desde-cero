"use client";

import { useTranslations } from "next-intl";
import type { BookingStatus } from "@/lib/types";

const tone: Record<BookingStatus, string> = {
  PENDING_PAYMENT: "bg-warn-soft text-warn",
  PAYMENT_PROCESSING: "bg-info-soft text-info",
  PAID: "bg-info-soft text-info",
  PENDING_APPROVAL: "bg-info-soft text-info",
  CONFIRMED: "bg-ok-soft text-ok",
  REJECTED: "bg-bad-soft text-bad",
  CANCELLED: "bg-bad-soft text-bad",
  EXPIRED: "bg-line text-muted",
  REFUNDED: "bg-line text-muted",
};

const icon: Record<BookingStatus, string> = {
  PENDING_PAYMENT: "⏳", PAYMENT_PROCESSING: "⟳", PAID: "✔", PENDING_APPROVAL: "⏳",
  CONFIRMED: "✔", REJECTED: "✖", CANCELLED: "✖", EXPIRED: "⌛", REFUNDED: "↩",
};

/** El estado se comunica con TEXTO + icono, no solo con color. */
export function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("booking.status");
  const s = status as BookingStatus;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${tone[s] ?? "bg-line text-muted"}`}>
      <span aria-hidden="true">{icon[s] ?? "•"}</span>
      {t.has(s) ? t(s) : status}
    </span>
  );
}

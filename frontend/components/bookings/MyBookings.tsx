"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { Booking, BookingPage } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { buttonClass } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function BookingCard({ b }: { b: Booking }) {
  const locale = useLocale();
  const t = useTranslations("booking");
  return (
    <article className="relative rounded-xl border border-line bg-surface-2 p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-lg font-bold">
          <Link href={{ pathname: "/account/bookings/[id]", params: { id: b.id } }} className="after:absolute after:inset-0 hover:underline">
            {b.course.name}
          </Link>
        </h3>
        <StatusBadge status={b.status} />
      </div>
      <p className="mt-1 text-sm text-muted">
        <time dateTime={b.course.starts_at}>{formatDateTime(b.course.starts_at, locale, b.course.timezone)}</time>
      </p>
      <p className="mt-2 text-sm">{t(`next.${b.next_action}`)}</p>
      <p className="mt-2 text-sm font-semibold">{formatMoney(b.price_minor, b.currency, locale)}</p>
    </article>
  );
}

export function MyBookings() {
  const locale = useLocale();
  const t = useTranslations("booking");
  const ta = useTranslations("account");
  const te = useTranslations("errors");
  const [data, setData] = useState<(BookingPage & { now: number }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<BookingPage>(`/bookings?locale=${locale}&limit=100`).then((page) => setData({ ...page, now: Date.now() })).catch((e) => setError(errorMessage(e, te)));
  }, [locale, te]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p role="status" className="text-muted">…</p>;
  if (data.items.length === 0) {
    return (
      <div className="space-y-4 py-6 text-center">
        <p className="text-muted">{t("empty")}</p>
        <Link href="/courses" className={buttonClass("primary")}>{t("exploreCourses")}</Link>
      </div>
    );
  }
  const { now } = data;
  const live = ["PENDING_PAYMENT", "PAYMENT_PROCESSING", "PAID", "PENDING_APPROVAL", "CONFIRMED"];
  const upcoming = data.items.filter((b) => live.includes(b.status) && new Date(b.course.ends_at).getTime() > now);
  const past = data.items.filter((b) => !upcoming.includes(b));

  return (
    <div className="space-y-8">
      {upcoming.length > 0 ? (
        <section aria-labelledby="up">
          <h2 id="up" className="mb-3 text-xl font-bold">{ta("upcoming")}</h2>
          <ul className="grid gap-4 sm:grid-cols-2">{upcoming.map((b) => <li key={b.id}><BookingCard b={b} /></li>)}</ul>
        </section>
      ) : null}
      {past.length > 0 ? (
        <section aria-labelledby="past">
          <h2 id="past" className="mb-3 text-xl font-bold">{ta("history")}</h2>
          <ul className="grid gap-4 sm:grid-cols-2">{past.map((b) => <li key={b.id}><BookingCard b={b} /></li>)}</ul>
        </section>
      ) : null}
    </div>
  );
}

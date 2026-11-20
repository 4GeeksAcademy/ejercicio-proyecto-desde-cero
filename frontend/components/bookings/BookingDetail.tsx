"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import QRCode from "qrcode";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatMoney, remaining } from "@/lib/format";
import type { Booking, Payment } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";

const POLL_STATES = ["PENDING_PAYMENT", "PAYMENT_PROCESSING", "PAID", "PENDING_APPROVAL"];

function Countdown({ expiresAt }: { expiresAt: string }) {
  const t = useTranslations("booking");
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  const r = remaining(expiresAt, now);
  return <p className="text-sm font-semibold text-warn">{r.expired ? t("expiredNow") : t("timeLeft", { hours: r.hours, minutes: r.minutes })}</p>;
}

function QrBlock({ bookingId }: { bookingId: string }) {
  const t = useTranslations("booking");
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    api<{ token: string }>(`/bookings/${bookingId}/qr`)
      .then(({ token }) => QRCode.toString(token, { type: "svg", margin: 1, width: 192 }))
      .then(setSvg)
      .catch(() => setSvg(null));
  }, [bookingId]);
  if (!svg) return null;
  return (
    <section aria-labelledby="qr" className="rounded-xl border border-line bg-surface-2 p-4 text-center">
      <h2 id="qr" className="font-bold">{t("qrTitle")}</h2>
      <div role="img" aria-label={t("qrTitle")} className="mx-auto mt-2 w-48 rounded bg-white p-2" dangerouslySetInnerHTML={{ __html: svg }} />
      <p className="mt-2 text-sm text-muted">{t("qrHelp")}</p>
    </section>
  );
}

export function BookingDetail({ id }: { id: string }) {
  const locale = useLocale();
  const t = useTranslations("booking");
  const te = useTranslations("errors");
  const [b, setB] = useState<Booking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"pay" | "cancel" | null>(null);
  const [confirmCancel, setConfirmCancel] = useState(false);

  const load = useCallback(async () => {
    try {
      setB(await api<Booking>(`/bookings/${id}?locale=${locale}`));
    } catch (e) {
      setError(errorMessage(e, te));
    }
  }, [id, locale, te]);

  useEffect(() => {
    let live = true;
    api<Booking>(`/bookings/${id}?locale=${locale}`)
      .then((r) => live && setB(r))
      .catch((e) => live && setError(errorMessage(e, te)));
    return () => {
      live = false;
    };
  }, [id, locale, te]);

  // Mientras la reserva no esté en un estado final, refrescamos para que el cliente SIEMPRE vea el estado real.
  useEffect(() => {
    if (!b || !POLL_STATES.includes(b.status)) return;
    const timer = setInterval(() => void load(), 10_000);
    return () => clearInterval(timer);
  }, [b, load]);

  async function pay() {
    setBusy("pay");
    setError(null);
    try {
      const p = await api<Payment>(`/bookings/${id}/pay`, { method: "POST" });
      if (p.checkout_url) window.location.href = p.checkout_url;
      else await load();
    } catch (e) {
      setError(errorMessage(e, te));
    } finally {
      setBusy(null);
    }
  }

  async function cancel() {
    setBusy("cancel");
    setError(null);
    try {
      setB(await api<Booking>(`/bookings/${id}/cancel?locale=${locale}`, { method: "POST", body: {} }));
      setConfirmCancel(false);
    } catch (e) {
      setError(errorMessage(e, te));
    } finally {
      setBusy(null);
    }
  }

  if (!b) return error ? <Alert kind="error">{error}</Alert> : <p role="status" className="text-muted">…</p>;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{b.course.name}</h1>
          <p className="text-muted">
            <time dateTime={b.course.starts_at}>{formatDateTime(b.course.starts_at, locale, b.course.timezone)}</time> · {b.course.address}
          </p>
        </div>
        <StatusBadge status={b.status} />
      </header>

      {/* Qué está pasando y qué debe hacer el cliente: SIEMPRE visible. */}
      <div className="rounded-xl border border-line bg-brand-soft p-4" role="status">
        <p className="font-semibold">{t(`next.${b.next_action}`)}</p>
        {b.status === "PENDING_PAYMENT" && b.expires_at ? <Countdown expiresAt={b.expires_at} /> : null}
      </div>

      {error ? <Alert kind="error">{error}</Alert> : null}

      <div className="flex flex-wrap gap-3">
        {b.next_action === "pay" ? (
          <Button busy={busy === "pay"} onClick={pay}>{busy === "pay" ? t("paying") : t("payNow")}</Button>
        ) : null}
        {b.can_cancel ? (
          confirmCancel ? (
            <div role="alertdialog" aria-label={t("cancelConfirm")} className="flex flex-wrap items-center gap-3 rounded-lg border border-bad p-3">
              <span className="text-sm font-medium">{t("cancelConfirm")}</span>
              <Button variant="danger" busy={busy === "cancel"} onClick={cancel}>{busy === "cancel" ? t("cancelling") : t("cancel")}</Button>
              <Button variant="secondary" onClick={() => setConfirmCancel(false)}>←</Button>
            </div>
          ) : (
            <Button variant="secondary" onClick={() => setConfirmCancel(true)}>{t("cancel")}</Button>
          )
        ) : ["PENDING_PAYMENT", "PENDING_APPROVAL", "CONFIRMED"].includes(b.status) ? (
          <p className="text-sm text-muted">{t("cannotCancel")}</p>
        ) : null}
      </div>

      {b.status === "CONFIRMED" ? <QrBlock bookingId={b.id} /> : null}

      <dl className="grid gap-4 rounded-xl border border-line bg-surface-2 p-4 text-sm sm:grid-cols-3">
        <div><dt className="text-muted">{t("price")}</dt><dd className="font-semibold">{formatMoney(b.price_minor, b.currency, locale)}</dd></div>
        <div><dt className="text-muted">{t("created")}</dt><dd>{formatDateTime(b.created_at, locale, b.course.timezone)}</dd></div>
        {b.expires_at && b.status === "PENDING_PAYMENT" ? (
          <div><dt className="text-muted">{t("expires")}</dt><dd>{formatDateTime(b.expires_at, locale, b.course.timezone)}</dd></div>
        ) : null}
      </dl>

      {b.history && b.history.length > 0 ? (
        <section aria-labelledby="hist">
          <h2 id="hist" className="mb-2 text-lg font-bold">{t("history")}</h2>
          <ol className="space-y-2 border-l-2 border-line pl-4">
            {b.history.map((h, i) => (
              <li key={i} className="text-sm">
                <StatusBadge status={h.to_status} />{" "}
                <time dateTime={h.at} className="text-muted">{formatDateTime(h.at, locale, b.course.timezone)}</time>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <Link href="/account" className="inline-block text-sm font-semibold underline">← {t("title")}</Link>
    </div>
  );
}

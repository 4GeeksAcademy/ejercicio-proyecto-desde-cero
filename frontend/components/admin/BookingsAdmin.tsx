"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatMoney } from "@/lib/format";
import { useApiData } from "@/lib/useApiData";
import type { AdminBooking } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { DataTable } from "./DataTable";
import { ReasonAction } from "./ReasonAction";

type Page = { items: AdminBooking[]; total: number };
const STATUSES = ["PENDING_PAYMENT", "PAYMENT_PROCESSING", "PENDING_APPROVAL", "CONFIRMED", "REJECTED", "CANCELLED", "EXPIRED", "REFUNDED"];

export function BookingsAdmin() {
  const t = useTranslations("admin");
  const tb = useTranslations("booking.status");
  const te = useTranslations("errors");
  const locale = useLocale();
  const [status, setStatus] = useState("PENDING_APPROVAL");
  const { data, error, reload } = useApiData<Page>(`/admin/bookings?limit=100${status ? `&status=${status}` : ""}`);
  const [actionError, setActionError] = useState<string | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setActionError(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setActionError(errorMessage(e, te));
    }
  };

  return (
    <div className="space-y-4">
      <div className="max-w-xs">
        <label htmlFor="st" className="block text-sm font-medium">{t("status")}</label>
        <select id="st" value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1 block min-h-11 w-full rounded-lg border border-line bg-surface-2 px-3">
          <option value="">{t("allStatuses")}</option>
          {STATUSES.map((s) => <option key={s} value={s}>{tb(s)}</option>)}
        </select>
      </div>
      {actionError ? <Alert kind="error">{actionError}</Alert> : null}
      {error ? <Alert kind="error">{error}</Alert> : null}
      {data ? (
        <DataTable
          caption={t("bookings")}
          empty="—"
          rows={data.items}
          rowKey={(b) => b.id}
          columns={[
            { header: t("client"), cell: (b) => <div><strong>{b.user_name}</strong><div className="text-muted">{b.user_email}</div></div> },
            { header: t("course"), cell: (b) => <div>{b.course.name}<div className="text-muted">{formatDateTime(b.course.starts_at, locale, b.course.timezone)}</div></div> },
            { header: t("amount"), cell: (b) => formatMoney(b.price_minor, b.currency, locale) },
            { header: t("status"), cell: (b) => <StatusBadge status={b.status} /> },
            {
              header: t("actions"),
              cell: (b) => (
                <div className="flex flex-col gap-2">
                  {b.status === "PENDING_APPROVAL" ? (
                    <>
                      <Button className="min-h-9 px-3 py-1" onClick={() => run(() => api(`/admin/bookings/${b.id}/approve`, { method: "POST" }))}>{t("approve")}</Button>
                      <ReasonAction variant="danger" label={t("reject")} onConfirm={(reason) => run(() => api(`/admin/bookings/${b.id}/reject`, { method: "POST", body: { reason } }))} />
                    </>
                  ) : null}
                  {["PENDING_PAYMENT", "PENDING_APPROVAL", "CONFIRMED"].includes(b.status) ? (
                    <ReasonAction label={tb("CANCELLED")} onConfirm={(reason) => run(() => api(`/admin/bookings/${b.id}/cancel`, { method: "POST", body: { reason } }))} />
                  ) : null}
                </div>
              ),
            },
          ]}
        />
      ) : <p role="status" className="text-muted">…</p>}
    </div>
  );
}

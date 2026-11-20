"use client";

import { useLocale, useTranslations } from "next-intl";
import { useApiData } from "@/lib/useApiData";
import { formatDateTime, formatMoney } from "@/lib/format";
import { Alert } from "@/components/ui/Alert";
import { Link } from "@/i18n/navigation";

type Metrics = {
  pending_approval: number;
  pending_payment: number;
  bookings_created_last_30_days: number;
  bookings_by_status: Record<string, number>;
  upcoming_courses: { id: string; name: string; starts_at: string; capacity: number; seats_taken: number; occupancy_pct: number }[];
  revenue_by_currency?: Record<string, { gross_minor: number; commission_minor: number }>;
};

function Stat({ label, value, href }: { label: string; value: number; href?: "/admin/bookings" }) {
  const inner = (
    <>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-3xl font-extrabold">{value}</p>
    </>
  );
  const cls = "rounded-xl border border-line bg-surface-2 p-4";
  return href ? <Link href={href} className={`${cls} block hover:bg-brand-soft`}>{inner}</Link> : <div className={cls}>{inner}</div>;
}

export function Dashboard() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const { data, error } = useApiData<Metrics>("/admin/metrics");
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p role="status" className="text-muted">…</p>;
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label={t("pendingApproval")} value={data.pending_approval} href="/admin/bookings" />
        <Stat label={t("pendingPayment")} value={data.pending_payment} href="/admin/bookings" />
        <Stat label={t("bookings30")} value={data.bookings_created_last_30_days} />
      </div>
      <section aria-labelledby="upc">
        <h2 id="upc" className="mb-3 text-xl font-bold">{t("upcomingCourses")}</h2>
        <ul className="space-y-3">
          {data.upcoming_courses.map((c) => (
            <li key={c.id} className="rounded-xl border border-line bg-surface-2 p-4">
              <div className="flex flex-wrap justify-between gap-2">
                <strong>{c.name}</strong>
                <span className="text-sm text-muted">{formatDateTime(c.starts_at, locale, "America/Bogota")}</span>
              </div>
              <div className="mt-2 flex items-center gap-3">
                <div className="h-3 flex-1 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuenow={c.occupancy_pct} aria-valuemin={0} aria-valuemax={100} aria-label={t("occupancy")}>
                  <div className="h-full bg-brand" style={{ width: `${c.occupancy_pct}%` }} />
                </div>
                <span className="text-sm font-semibold">{c.seats_taken}/{c.capacity} ({c.occupancy_pct}%)</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
      {data.revenue_by_currency ? (
        <section aria-labelledby="rev">
          <h2 id="rev" className="mb-3 text-xl font-bold">{t("revenue")}</h2>
          {Object.entries(data.revenue_by_currency).map(([cur, v]) => (
            <dl key={cur} className="grid gap-4 rounded-xl border border-line bg-surface-2 p-4 sm:grid-cols-3">
              <div><dt className="text-sm text-muted">{t("gross")}</dt><dd className="text-xl font-bold">{formatMoney(v.gross_minor, cur, locale)}</dd></div>
              <div><dt className="text-sm text-muted">{t("commission")}</dt><dd className="text-xl font-bold">{formatMoney(v.commission_minor, cur, locale)}</dd></div>
              <div><dt className="text-sm text-muted">{t("net")}</dt><dd className="text-xl font-bold">{formatMoney(v.gross_minor - v.commission_minor, cur, locale)}</dd></div>
            </dl>
          ))}
        </section>
      ) : null}
    </div>
  );
}

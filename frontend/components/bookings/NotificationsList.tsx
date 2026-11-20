"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { NotificationPage } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

export function NotificationsList() {
  const locale = useLocale();
  const t = useTranslations("account");
  const te = useTranslations("errors");
  const [data, setData] = useState<NotificationPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api<NotificationPage>("/notifications?limit=50").then(setData).catch((e) => setError(errorMessage(e, te))), [te]);
  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data) return <p role="status" className="text-muted">…</p>;
  if (data.items.length === 0) return <p className="text-muted">{t("noNotifications")}</p>;

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted" aria-live="polite">{t("unread", { count: data.unread })}</p>
      <ul className="space-y-3">
        {data.items.map((n) => (
          <li key={n.id} className={`rounded-xl border p-4 ${n.read ? "border-line bg-surface-2" : "border-brand bg-brand-soft"}`}>
            <p className="font-semibold">{n.title}</p>
            <p className="mt-1 text-sm">{n.body}</p>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
              <time dateTime={n.created_at} className="text-muted">{new Date(n.created_at).toLocaleString(locale === "es" ? "es-CO" : "en-US")}</time>
              {n.booking_id ? (
                <Link href={{ pathname: "/account/bookings/[id]", params: { id: n.booking_id } }} className="font-semibold underline">→</Link>
              ) : null}
              {!n.read ? (
                <Button variant="ghost" className="min-h-9 px-2 py-1" onClick={async () => { await api(`/notifications/${n.id}/read`, { method: "PATCH" }); await load(); }}>
                  {t("markRead")}
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

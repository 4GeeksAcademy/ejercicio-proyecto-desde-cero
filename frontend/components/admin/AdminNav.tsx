"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { can, useAuth } from "@/components/auth/AuthProvider";

export function AdminNav() {
  const t = useTranslations("admin");
  const pathname = usePathname();
  const { user } = useAuth();
  const items = [
    { href: "/admin", label: t("dashboard"), show: true },
    { href: "/admin/courses", label: t("courses"), show: true },
    { href: "/admin/bookings", label: t("bookings"), show: true },
    { href: "/admin/payments", label: t("payments"), show: can(user, "payment:read_all") },
    { href: "/admin/users", label: t("users"), show: can(user, "user:read_all") },
    { href: "/admin/commissions", label: t("commissions"), show: can(user, "commission:read") },
    { href: "/admin/audit", label: t("audit"), show: can(user, "audit:read") },
  ] as const;
  return (
    <nav aria-label={t("title")} className="mb-6 flex flex-wrap gap-2 text-sm font-medium">
      {items.filter((i) => i.show).map((i) => (
        <Link
          key={i.href}
          href={i.href}
          aria-current={pathname === i.href ? "page" : undefined}
          className={`rounded-full border px-4 py-2 ${pathname === i.href ? "border-brand bg-brand text-brand-ink" : "border-line bg-surface-2 hover:bg-brand-soft"}`}
        >
          {i.label}
        </Link>
      ))}
    </nav>
  );
}

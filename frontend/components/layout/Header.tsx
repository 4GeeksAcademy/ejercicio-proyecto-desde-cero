"use client";

import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import { useAuth, can } from "@/components/auth/AuthProvider";
import { LocaleSwitcher } from "./LocaleSwitcher";
import { buttonClass } from "@/components/ui/Button";

export function Header() {
  const t = useTranslations("nav");
  const app = useTranslations("common");
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const isStaff = can(user, "booking:approve") || can(user, "course:write");

  return (
    <header className="border-b border-line bg-surface-2">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-3xl font-extrabold tracking-tight text-brand sm:text-4xl">
          {app("appName")}
        </Link>
        <nav aria-label={t("main")} className="flex flex-wrap items-center gap-1 text-sm font-medium">
          <Link href="/courses" className="rounded px-3 py-2 hover:bg-brand-soft">{t("courses")}</Link>
          <Link href="/faq" className="rounded px-3 py-2 hover:bg-brand-soft">{t("faq")}</Link>
          <Link href="/contact" className="rounded px-3 py-2 hover:bg-brand-soft">{t("contact")}</Link>
          {isStaff ? <Link href="/admin" className="rounded px-3 py-2 hover:bg-brand-soft">{t("admin")}</Link> : null}
        </nav>
        <div className="flex items-center gap-3">
          <LocaleSwitcher />
          {loading ? null : user ? (
            <>
              <Link href="/account" className="rounded px-3 py-2 text-sm font-medium hover:bg-brand-soft">{t("account")}</Link>
              <button
                type="button"
                className={buttonClass("secondary")}
                onClick={async () => {
                  await logout();
                  router.push("/");
                }}
              >
                {t("logout")}
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="rounded px-3 py-2 text-sm font-medium hover:bg-brand-soft">{t("login")}</Link>
              <Link href="/register" className={buttonClass("primary")}>{t("register")}</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { RequireAuth } from "@/components/auth/RequireAuth";

export default async function AccountLayout({ children }: { children: React.ReactNode }) {
  const t = await getTranslations("nav");
  return (
    <RequireAuth>
      <nav aria-label={t("account")} className="mb-6 flex flex-wrap gap-2 text-sm font-medium">
        <Link href="/account" className="rounded-full border border-line bg-surface-2 px-4 py-2 hover:bg-brand-soft">{t("account")}</Link>
        <Link href="/account/notifications" className="rounded-full border border-line bg-surface-2 px-4 py-2 hover:bg-brand-soft">{t("notifications")}</Link>
        <Link href="/account/profile" className="rounded-full border border-line bg-surface-2 px-4 py-2 hover:bg-brand-soft">{t("profile")}</Link>
      </nav>
      {children}
    </RequireAuth>
  );
}

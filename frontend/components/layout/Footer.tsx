import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export async function Footer() {
  const t = await getTranslations("footer");
  return (
    <footer className="mt-16 border-t border-line bg-surface-2">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-muted">
        <p>
          © {new Date().getFullYear()} Tallerya. {t("rights")} {t("tagline")}
        </p>
        <nav className="flex gap-4">
          <Link href="/privacy" className="underline">{t("privacy")}</Link>
          <Link href="/terms" className="underline">{t("terms")}</Link>
        </nav>
      </div>
    </footer>
  );
}

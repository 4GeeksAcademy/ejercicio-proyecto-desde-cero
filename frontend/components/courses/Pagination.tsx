import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { buttonClass } from "@/components/ui/Button";

export async function Pagination({
  total, limit, offset, query,
}: { total: number; limit: number; offset: number; query: Record<string, string | undefined> }) {
  const t = await getTranslations("common");
  const pages = Math.max(1, Math.ceil(total / limit));
  const page = Math.floor(offset / limit) + 1;
  if (pages <= 1) return null;
  const q = (p: number) => ({ ...Object.fromEntries(Object.entries(query).filter(([, v]) => v)), page: String(p) });
  return (
    <nav aria-label="Pagination" className="mt-8 flex items-center justify-center gap-4">
      {page > 1 ? (
        <Link href={{ pathname: "/courses", query: q(page - 1) }} rel="prev" className={buttonClass("secondary")}>{t("previous")}</Link>
      ) : null}
      <span className="text-sm text-muted">{t("page", { page, pages })}</span>
      {page < pages ? (
        <Link href={{ pathname: "/courses", query: q(page + 1) }} rel="next" className={buttonClass("secondary")}>{t("next")}</Link>
      ) : null}
    </nav>
  );
}

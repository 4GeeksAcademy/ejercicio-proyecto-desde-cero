import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import type { Category } from "@/lib/types";
import { buttonClass } from "@/components/ui/Button";

type Props = { categories: Category[]; values: { q?: string; category?: string; sort?: string; available?: string } };

/** Formulario GET nativo: funciona sin JavaScript y los filtros quedan en la URL (compartible/indexable). */
export async function CourseFilters({ categories, values }: Props) {
  const t = await getTranslations("courses");
  const field = "mt-1 block w-full min-h-11 rounded-lg border border-line bg-surface-2 px-3 py-2";
  return (
    <form role="search" aria-label={t("filters")} className="grid gap-4 rounded-xl border border-line bg-surface-2 p-4 sm:grid-cols-2 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <label htmlFor="q" className="block text-sm font-medium">{t("search")}</label>
        <input id="q" name="q" type="search" defaultValue={values.q} placeholder={t("searchPlaceholder")} className={field} />
      </div>
      <div>
        <label htmlFor="category" className="block text-sm font-medium">{t("category")}</label>
        <select id="category" name="category" defaultValue={values.category ?? ""} className={field}>
          <option value="">{t("allCategories")}</option>
          {categories.map((c) => (
            <option key={c.id} value={c.slug}>{c.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="sort" className="block text-sm font-medium">{t("sortBy")}</label>
        <select id="sort" name="sort" defaultValue={values.sort ?? "date"} className={field}>
          {(["date", "price_asc", "price_desc", "newest"] as const).map((s) => (
            <option key={s} value={s}>{t(`sort.${s}`)}</option>
          ))}
        </select>
      </div>
      <div className="flex items-end gap-2">
        <label className="flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" name="available" value="1" defaultChecked={values.available === "1"} className="size-5 accent-[var(--brand)]" />
          {t("availableOnly")}
        </label>
      </div>
      <div className="flex gap-2 sm:col-span-2 lg:col-span-5">
        <button type="submit" className={buttonClass("primary")}>{t("apply")}</button>
        <Link href="/courses" className={buttonClass("secondary")}>{t("clear")}</Link>
      </div>
    </form>
  );
}

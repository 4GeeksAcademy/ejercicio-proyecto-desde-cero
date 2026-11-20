import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { buttonClass } from "@/components/ui/Button";

export default async function NotFound() {
  const t = await getTranslations("notFound");
  return (
    <section className="py-16 text-center">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      <p className="mt-3 text-muted">{t("body")}</p>
      <Link href="/" className={buttonClass("primary", "mt-6")}>
        Tallerya
      </Link>
    </section>
  );
}

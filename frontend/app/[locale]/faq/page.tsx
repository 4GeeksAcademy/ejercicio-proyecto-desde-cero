import { getTranslations, setRequestLocale } from "next-intl/server";
import { titled } from "@/lib/meta";

export const generateMetadata = titled("faq", "title");

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("faq");
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-3xl font-bold">{t("title")}</h1>
      {(["1", "2", "3", "4", "5"] as const).map((n) => (
        <details key={n} className="rounded-xl border border-line bg-surface-2 p-4">
          <summary className="cursor-pointer font-semibold">{t(`q${n}`)}</summary>
          <p className="mt-2 text-muted">{t(`a${n}`)}</p>
        </details>
      ))}
    </div>
  );
}

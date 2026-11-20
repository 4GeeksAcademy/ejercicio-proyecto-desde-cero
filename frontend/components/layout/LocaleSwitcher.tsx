"use client";

import { useLocale, useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { Link, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { useAlternates } from "./alternates";

export function LocaleSwitcher() {
  const t = useTranslations("nav");
  const current = useLocale();
  const pathname = usePathname();
  const params = useParams<Record<string, string>>();
  const { alternates } = useAlternates();

  return (
    <nav aria-label={t("language")} className="flex items-center gap-1 text-sm">
      {routing.locales.map((loc) => {
        const p: Record<string, string> = { ...(params as Record<string, string>) };
        delete p.locale;
        if (alternates?.[loc] && "slug" in p) p.slug = alternates[loc];
        const href = (Object.keys(p).length ? { pathname, params: p } : pathname) as never;
        return (
          <Link
            key={loc}
            href={href}
            locale={loc}
            hrefLang={loc}
            lang={loc}
            aria-current={loc === current ? "true" : undefined}
            className={`rounded px-2 py-1 font-semibold uppercase ${loc === current ? "bg-brand text-brand-ink" : "hover:bg-brand-soft"}`}
          >
            {loc}
          </Link>
        );
      })}
    </nav>
  );
}

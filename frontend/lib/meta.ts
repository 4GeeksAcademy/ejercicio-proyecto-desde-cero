import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { type Loc, pageAlternates } from "./seo";

type PublicHref = "/faq" | "/contact" | "/privacy" | "/terms";

/** generateMetadata reutilizable: título traducido; con `href` añade canonical + hreflang (páginas indexables). */
export function titled(namespace: string, key: string, noindex = false, href?: PublicHref) {
  return async ({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> => {
    const { locale } = await params;
    const t = await getTranslations({ locale, namespace });
    return {
      title: t(key),
      robots: noindex ? { index: false, follow: false } : undefined,
      alternates: href ? pageAlternates(locale as Loc, href) : undefined,
    };
  };
}

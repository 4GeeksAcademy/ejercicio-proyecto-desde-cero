import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

/** generateMetadata reutilizable: título traducido desde messages. */
export function titled(namespace: string, key: string, noindex = false) {
  return async ({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> => {
    const { locale } = await params;
    const t = await getTranslations({ locale, namespace });
    return { title: t(key), robots: noindex ? { index: false, follow: false } : undefined };
  };
}

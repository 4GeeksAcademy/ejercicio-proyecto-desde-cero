import type { Metadata } from "next";
import { getPathname } from "@/i18n/navigation";

/** URL pública del sitio: la configurada, o la que Render asigna, o localhost en desarrollo. */
const vercel = process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "";
export const SITE = (process.env.NEXT_PUBLIC_SITE_URL || process.env.RENDER_EXTERNAL_URL || vercel || "http://localhost:3000").replace(/\/$/, "");
export type Loc = "es" | "en";
type Href = Parameters<typeof getPathname>[0]["href"];

export const absoluteUrl = (locale: Loc, href: Href): string => SITE + getPathname({ locale, href });

/** canonical + hreflang (es, en, x-default) de una página pública. */
export function pageAlternates(locale: Loc, href: Href): NonNullable<Metadata["alternates"]> {
  return {
    canonical: absoluteUrl(locale, href),
    languages: { es: absoluteUrl("es", href), en: absoluteUrl("en", href), "x-default": absoluteUrl("es", href) },
  };
}

/** JSON-LD seguro para incrustar en <script>: se escapa "<" para evitar inyección. */
export const jsonLd = (data: unknown): string => JSON.stringify(data).replace(/</g, "\\u003c");

/** Datos de la organización (schema.org). Solo datos reales; teléfono/redes se añadirán cuando el cliente los confirme. */
export function organizationLd(locale: Loc, description: string) {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": ["Organization", "LocalBusiness"],
        "@id": `${SITE}/#organization`,
        name: "Tallerya",
        url: `${SITE}/${locale}`,
        description,
        address: { "@type": "PostalAddress", addressLocality: "Bogotá", addressCountry: "CO" },
        areaServed: { "@type": "City", name: "Bogotá" },
        knowsLanguage: ["es", "en"],
        makesOffer: { "@type": "Offer", itemOffered: { "@type": "Service", name: locale === "es" ? "Talleres presenciales de un día" : "One-day in-person workshops" } },
      },
      {
        "@type": "WebSite",
        "@id": `${SITE}/#website`,
        url: `${SITE}/${locale}`,
        name: "Tallerya",
        inLanguage: locale,
        publisher: { "@id": `${SITE}/#organization` },
        potentialAction: {
          "@type": "SearchAction",
          target: { "@type": "EntryPoint", urlTemplate: `${absoluteUrl(locale, "/courses")}?q={search_term_string}` },
          "query-input": "required name=search_term_string",
        },
      },
    ],
  };
}

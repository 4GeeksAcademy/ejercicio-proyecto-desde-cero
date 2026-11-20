import type { MetadataRoute } from "next";
import { getPathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import type { CoursePage } from "@/lib/types";

export const revalidate = 3600;
const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

async function allCourses(locale: string): Promise<CoursePage["items"]> {
  const base = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  const out: CoursePage["items"] = [];
  for (let offset = 0; offset < 1000; offset += 50) {
    const res = await fetch(`${base}/api/v1/courses?locale=${locale}&limit=50&offset=${offset}`, { next: { revalidate: 3600 } });
    if (!res.ok) break;
    const page = (await res.json()) as CoursePage;
    out.push(...page.items);
    if (offset + 50 >= page.total) break;
  }
  return out;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const abs = (locale: "es" | "en", href: Parameters<typeof getPathname>[0]["href"]) => SITE + getPathname({ locale, href });
  const staticPages = ["/", "/courses", "/faq", "/contact", "/privacy", "/terms"] as const;
  const entries: MetadataRoute.Sitemap = staticPages.map((p) => ({
    url: abs("es", p),
    alternates: { languages: { es: abs("es", p), en: abs("en", p) } },
  }));
  try {
    const [es, en] = await Promise.all(routing.locales.map((l) => allCourses(l).catch(() => [])));
    const enByCourse = new Map(en.map((c) => [c.id, c.slug]));
    for (const c of es) {
      const enSlug = enByCourse.get(c.id);
      entries.push({
        url: abs("es", { pathname: "/courses/[slug]", params: { slug: c.slug } }),
        alternates: {
          languages: {
            es: abs("es", { pathname: "/courses/[slug]", params: { slug: c.slug } }),
            ...(enSlug ? { en: abs("en", { pathname: "/courses/[slug]", params: { slug: enSlug } }) } : {}),
          },
        },
      });
    }
    // Cursos que solo existen en inglés
    const esIds = new Set(es.map((c) => c.id));
    for (const c of en.filter((c) => !esIds.has(c.id))) {
      entries.push({ url: abs("en", { pathname: "/courses/[slug]", params: { slug: c.slug } }) });
    }
  } catch {
    /* sin API no listamos cursos, pero el sitemap sigue válido */
  }
  return entries;
}

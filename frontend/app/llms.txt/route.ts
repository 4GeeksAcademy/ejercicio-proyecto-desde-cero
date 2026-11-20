import { SITE, absoluteUrl } from "@/lib/seo";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { CourseDetail, CoursePage } from "@/lib/types";

// Dinámico: NO se genera en el build (la API no existe entonces). Los datos se cachean 15 min en cada fetch.
export const dynamic = "force-dynamic";

const API = () => process.env.API_INTERNAL_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API()}/api/v1${path}`, { next: { revalidate: 900 } });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

/**
 * /llms.txt: resumen en texto plano/markdown pensado para asistentes de IA y buscadores.
 * Todo sale de la API real (cursos activos y futuros); no se inventa nada.
 */
export async function GET() {
  const [es, en] = await Promise.all([
    getJson<CoursePage>("/courses?locale=es&limit=50"),
    getJson<CoursePage>("/courses?locale=en&limit=50"),
  ]);
  const enSlugById = new Map((en?.items ?? []).map((c) => [c.id, c.slug]));
  const courses = es?.items ?? [];
  const details = await Promise.all(courses.map((c) => getJson<CourseDetail>(`/courses/${c.slug}?locale=es`)));

  const lines: string[] = [
    "# Tallerya",
    "",
    "> Tallerya es una academia de talleres presenciales de un día en Bogotá, Colombia: cerámica, fotografía, cocina, costura, mecánica, arte y manualidades. Se reserva y se paga online.",
    "",
    "## Datos del negocio",
    `- Sitio web: ${SITE}`,
    "- Ciudad: Bogotá, Colombia (zona horaria America/Bogota)",
    "- Idiomas del sitio: español e inglés",
    `- Catálogo de cursos: ${absoluteUrl("es", "/courses")} (ES) · ${absoluteUrl("en", "/courses")} (EN)`,
    `- Preguntas frecuentes: ${absoluteUrl("es", "/faq")}`,
    `- Contacto: ${absoluteUrl("es", "/contact")}`,
    "",
    "## Cómo funciona la reserva",
    "- Cada reserva es para una persona. No se puede reservar con menos de 24 horas de antelación.",
    "- Tras reservar hay 24 horas para pagar; si no se paga, la reserva caduca y se libera la plaza.",
    "- Tras el pago, Tallerya confirma la participación. Se puede cancelar si faltan más de 24 horas.",
    "- Para reservar hay que crear una cuenta en el sitio web (el asistente no reserva ni paga por el usuario).",
    "",
    "## Cursos disponibles ahora",
    "",
  ];

  if (courses.length === 0) lines.push("Por ahora no hay cursos publicados.");
  courses.forEach((c, i) => {
    const d = details[i];
    const enSlug = enSlugById.get(c.id);
    lines.push(`### ${c.name}`);
    lines.push(`- URL (ES): ${absoluteUrl("es", { pathname: "/courses/[slug]", params: { slug: c.slug } })}`);
    if (enSlug) lines.push(`- URL (EN): ${absoluteUrl("en", { pathname: "/courses/[slug]", params: { slug: enSlug } })}`);
    lines.push(`- Categoría: ${c.category.name}`);
    lines.push(`- Fecha y hora: ${formatDateTime(c.starts_at, "es", c.timezone)} (hora de Bogotá)`);
    if (d) lines.push(`- Lugar: ${d.venue.name}, ${d.venue.address}, ${d.venue.city}`);
    lines.push(`- Precio: ${c.price_minor === 0 ? "gratis" : formatMoney(c.price_minor, c.currency, "es")} por persona`);
    lines.push(`- Plazas disponibles: ${c.is_full ? "ninguna (completo)" : c.seats_available}`);
    lines.push(`- Descripción: ${c.short_description}`);
    lines.push("");
  });

  lines.push(`_Actualizado: ${new Date().toISOString()}. Las plazas cambian; confirma siempre en la página del curso._`, "");
  return new Response(lines.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=900" },
  });
}

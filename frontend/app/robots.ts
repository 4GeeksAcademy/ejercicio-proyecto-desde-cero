import type { MetadataRoute } from "next";
import { SITE } from "@/lib/seo";

// Zonas privadas o sin valor para buscadores (en ambos idiomas).
const PRIVATE = ["/api/", "/*/admin", "/*/account", "/*/mi-cuenta", "/*/login", "/*/iniciar-sesion", "/*/pay/"];

// Rastreadores de IA que SÍ queremos que lean el sitio, para que los asistentes puedan dar su URL y sus datos.
const AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User", "Claude-SearchBot", "PerplexityBot", "Google-Extended"];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: PRIVATE },
      { userAgent: AI_CRAWLERS, allow: ["/", "/llms.txt"], disallow: PRIVATE },
    ],
    sitemap: `${SITE}/sitemap.xml`,
  };
}

import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Zonas privadas o sin valor para buscadores (en ambos idiomas).
        disallow: ["/api/", "/*/admin", "/*/account", "/*/mi-cuenta", "/*/login", "/*/iniciar-sesion", "/*/pay/"],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
  };
}

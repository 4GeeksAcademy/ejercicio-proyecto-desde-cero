import { describe, expect, it, vi } from "vitest";

// La navegación de next-intl depende del runtime de Next; aquí solo probamos la lógica de datos.
vi.mock("@/i18n/navigation", () => ({ getPathname: ({ locale }: { locale: string }) => `/${locale}/courses` }));

import { jsonLd, organizationLd } from "@/lib/seo";

describe("jsonLd", () => {
  it("escapa '<' para que un texto malicioso no cierre el <script>", () => {
    const out = jsonLd({ name: "</script><script>alert(1)</script>" });
    expect(out).not.toContain("</script>");
    expect(JSON.parse(out).name).toContain("</script>");
  });
});

describe("organizationLd", () => {
  it("describe Tallerya en Bogotá sin inventar contacto", () => {
    const g = organizationLd("es", "desc")["@graph"];
    const org = g[0] as Record<string, unknown>;
    expect(org.name).toBe("Tallerya");
    expect((org.address as { addressLocality: string }).addressLocality).toBe("Bogotá");
    expect(org).not.toHaveProperty("telephone");
  });
});

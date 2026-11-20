import { expect, test } from "@playwright/test";

test("home publica los datos de la organización para buscadores", async ({ page }) => {
  await page.goto("/es");
  const blocks = await page.locator('script[type="application/ld+json"]').allTextContents();
  const org = blocks.map((b) => JSON.parse(b)).find((d) => d["@graph"]);
  const business = org["@graph"].find((n: { "@type": unknown }) => Array.isArray(n["@type"]) && n["@type"].includes("LocalBusiness"));
  expect(business.name).toBe("Tallerya");
  expect(business.address.addressLocality).toBe("Bogotá");
});

test("cada página pública declara canonical y hreflang es/en", async ({ page }) => {
  for (const path of ["/es", "/es/cursos", "/es/cursos/ceramica-para-principiantes", "/en/faq"]) {
    await page.goto(path);
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
    for (const lang of ["es", "en", "x-default"]) {
      await expect(page.locator(`link[rel="alternate"][hreflang="${lang}"]`), `${path} ${lang}`).toHaveCount(1);
    }
  }
});

test("llms.txt da la URL y los datos de los talleres reales", async ({ request }) => {
  const res = await request.get("/llms.txt");
  expect(res.status()).toBe(200);
  const text = await res.text();
  expect(text).toContain("# Tallerya");
  expect(text).toMatch(/Cerámica para principiantes/);
  expect(text).toMatch(/URL \(ES\): https?:\/\/\S+\/es\/cursos\/ceramica-para-principiantes/);
  expect(text).toMatch(/URL \(EN\): https?:\/\/\S+\/en\/courses\/beginner-ceramics/);
  expect(text).toMatch(/Lugar: .*Bogotá/);
  expect(text).toMatch(/Precio: .*180\.000/);
});

test("robots.txt deja entrar a los rastreadores de IA y protege zonas privadas", async ({ request }) => {
  const text = await (await request.get("/robots.txt")).text();
  for (const bot of ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]) expect(text).toContain(`User-Agent: ${bot}`);
  expect(text).toContain("Disallow: /*/admin");
  expect(text).toMatch(/Sitemap: https?:\/\/\S+\/sitemap\.xml/);
});

test("el sitemap lista los cursos en los dos idiomas", async ({ request }) => {
  const xml = await (await request.get("/sitemap.xml")).text();
  expect(xml).toContain("/es/cursos/ceramica-para-principiantes");
  expect(xml).toContain('hreflang="en"');
});

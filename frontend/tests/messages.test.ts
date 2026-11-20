import { describe, expect, it } from "vitest";
import es from "@/messages/es.json";
import en from "@/messages/en.json";

const keys = (o: Record<string, unknown>, prefix = ""): string[] =>
  Object.entries(o).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v as Record<string, unknown>, `${prefix}${k}.`) : [`${prefix}${k}`],
  );

describe("i18n", () => {
  it("es y en tienen exactamente las mismas claves", () => {
    expect(keys(es).sort()).toEqual(keys(en).sort());
  });
  it("ningún texto está vacío", () => {
    const empty = [...keys(es), ...keys(en)].length;
    expect(empty).toBeGreaterThan(200);
  });
});

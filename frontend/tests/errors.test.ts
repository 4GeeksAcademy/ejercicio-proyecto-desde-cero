import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { errorMessage, fieldErrors } from "@/lib/errors";

const t = Object.assign((k: string) => `T:${k}`, { has: (k: string) => ["COURSE_FULL", "generic", "network", "RATE_LIMITED"].includes(k) });

describe("errorMessage", () => {
  it("traduce códigos conocidos de la API", () => {
    expect(errorMessage(new ApiError(409, "COURSE_FULL", "x"), t)).toBe("T:COURSE_FULL");
  });
  it("usa un mensaje genérico para códigos desconocidos (nunca el texto técnico)", () => {
    expect(errorMessage(new ApiError(500, "WHATEVER", "stack trace..."), t)).toBe("T:generic");
  });
  it("distingue fallos de red", () => {
    expect(errorMessage(new TypeError("Failed to fetch"), t)).toBe("T:network");
  });
  it("429 => demasiados intentos", () => {
    expect(errorMessage(new ApiError(429, "X", "x"), t)).toBe("T:RATE_LIMITED");
  });
});

describe("fieldErrors", () => {
  it("mapea los errores de validación 422 por campo", () => {
    const e = new ApiError(422, "VALIDATION_ERROR", "x", [{ field: "phone", message: "Value error, Teléfono inválido" }]);
    expect(fieldErrors(e)).toEqual({ phone: "Teléfono inválido" });
  });
  it("devuelve vacío para otros errores", () => {
    expect(fieldErrors(new ApiError(409, "X", "x"))).toEqual({});
  });
});

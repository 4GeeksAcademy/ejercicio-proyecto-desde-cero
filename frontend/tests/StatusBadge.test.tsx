import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "@/components/ui/StatusBadge";
import es from "@/messages/es.json";
import en from "@/messages/en.json";

const wrap = (locale: "es" | "en", messages: typeof es) =>
  render(
    <NextIntlClientProvider locale={locale} messages={messages}>
      <StatusBadge status="PENDING_APPROVAL" />
    </NextIntlClientProvider>,
  );

describe("StatusBadge", () => {
  it("comunica el estado con TEXTO (no solo color) en español", () => {
    wrap("es", es);
    expect(screen.getByText("Pendiente de aprobación")).toBeInTheDocument();
  });
  it("y en inglés", () => {
    wrap("en", en);
    expect(screen.getByText("Awaiting approval")).toBeInTheDocument();
  });
});

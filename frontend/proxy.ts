import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

// Next 16: "middleware" se llama "proxy". Redirige "/" al idioma preferido y normaliza las rutas.
export default createMiddleware(routing);

export const config = {
  // Todo excepto API, archivos estáticos y recursos internos de Next.
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};

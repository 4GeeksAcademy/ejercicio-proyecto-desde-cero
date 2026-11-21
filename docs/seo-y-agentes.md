# Que Google y los asistentes de IA encuentren Tallerya

**Objetivo del cliente [CLIENTE]:** que lo encuentren en Google y que, al preguntarle a un asistente de IA, este pueda dar la URL y los datos del taller.

## Qué ya está hecho (verificado con tests E2E)
| Qué | Dónde | Para qué sirve |
|---|---|---|
| Datos de la organización (`LocalBusiness`, Bogotá, idiomas, búsqueda) | portada, JSON-LD | Google entiende qué es Tallerya y dónde está |
| Datos de cada taller (`Event`: fecha, lugar, precio, disponibilidad) | página del curso | Resultados enriquecidos de Google |
| Migas de pan y lista de cursos (`BreadcrumbList`, `ItemList`) | curso y catálogo | Estructura clara del sitio |
| `canonical` + `hreflang` es/en/x-default | todas las páginas públicas | Evita duplicados entre idiomas |
| `sitemap.xml` con cursos en ambos idiomas | `/sitemap.xml` | Descubrimiento de URLs |
| `robots.txt` que permite GPTBot, ClaudeBot, PerplexityBot, Google-Extended… y protege admin/cuenta | `/robots.txt` | Los rastreadores de IA pueden leer el sitio |
| **`llms.txt`**: resumen del negocio + cada curso con URL (ES/EN), fecha, lugar, precio y plazas | `/llms.txt` | Texto pensado para que un asistente cite la URL y los datos correctos |
| Herramientas del asistente: `search_courses`, `get_course_details` y `get_business_info` devuelven la **URL pública** | `backend/app/modules/assistant` | Cuando se integre el modelo, responderá con enlaces reales |

## Pasos para salir en Google (después de desplegar en Render o Vercel)
Nada de esto se puede hacer desde el código: necesita tu cuenta de Google y la web ya publicada.

1. **Despliega** la web ([despliegue.md](despliegue.md)) y comprueba que `https://<tu-web>/sitemap.xml` y `/llms.txt` muestran tu dirección real, no `localhost`.
2. Entra en **https://search.google.com/search-console** con tu cuenta de Google → **Añadir propiedad** → tipo **"Prefijo de la URL"** → escribe `https://<tu-web>/`.
3. **Verificar la propiedad** con el método **"Etiqueta HTML"**: Google te da un código (`content="..."`). Cópialo SOLO el valor.
4. En Render (servicio `tallerya-web` → Environment) o en Vercel (Settings → Environment Variables) crea **`GOOGLE_SITE_VERIFICATION`** con ese valor y **vuelve a desplegar**. En 1-2 minutos, la portada incluirá la etiqueta. Vuelve a Search Console y pulsa **Verificar**.
   - Si Google no la encuentra (la raíz `/` redirige a `/es`), usa un **dominio propio** y el método **DNS**, que es más fiable.
5. En Search Console → **Sitemaps** → añade `sitemap.xml` → Enviar.
6. En **Inspección de URL** pega `https://<tu-web>/es` y pulsa **Solicitar indexación**. Repite con 2 o 3 cursos.
7. **Espera.** Puede tardar de unos días a un par de semanas. Para comprobar: busca `site:<tu-web>` en Google.

**Con el plan gratuito de Render** la web se duerme y tarda 30-60 s en despertar; si Google llega en ese momento puede dar error y reintentarlo más tarde. Un dominio propio y un plan que no duerma ayudan mucho a indexar bien.

Nadie puede garantizar en qué posición saldrá. Al principio aparecerá al buscar el nombre "Tallerya".

## Cómo comprobarlo
- Prueba de resultados enriquecidos de Google (Rich Results Test) sobre la URL de un curso.
- Abrir `/llms.txt`, `/robots.txt` y `/sitemap.xml` en el dominio real.
- Preguntar a un asistente con búsqueda web por "talleres de cerámica en Bogotá Tallerya" una vez indexado.

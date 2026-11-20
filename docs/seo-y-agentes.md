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

## Qué NO se puede hacer desde el código (pasos manuales al publicar)
1. **Publicar en un dominio público.** Hoy corre en `localhost`; nadie fuera de esta máquina puede encontrarlo. Hace falta hosting + dominio + HTTPS.
2. **Configurar `NEXT_PUBLIC_SITE_URL` y `FRONTEND_URL`** con ese dominio (las URLs canónicas, el sitemap y `llms.txt` salen de ahí).
3. **Dar de alta el dominio en Google Search Console** y enviar `https://<dominio>/sitemap.xml`.
4. Completar los datos reales del negocio cuando el cliente los dé (teléfono, redes, dirección exacta, logo): ahora no se inventan.
5. **Google y los asistentes tardan** días o semanas en indexar; ninguna web puede garantizar posiciones.

## Cómo comprobarlo
- Prueba de resultados enriquecidos de Google (Rich Results Test) sobre la URL de un curso.
- Abrir `/llms.txt`, `/robots.txt` y `/sitemap.xml` en el dominio real.
- Preguntar a un asistente con búsqueda web por "talleres de cerámica en Bogotá Tallerya" una vez indexado.

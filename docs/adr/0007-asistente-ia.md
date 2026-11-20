# ADR-0007 — Asistente de IA: herramientas de solo lectura

**Estado:** preparado (capa de herramientas implementada y probada); **integración con el modelo: pendiente de aprobación del cliente** · [PROPUESTA]

## Diseño
`app/modules/assistant/tools.py` expone `search_courses`, `get_course_details` y `check_availability` con esquemas JSON compatibles con *tool use* de la API de Claude. Llaman a los **mismos servicios** que el catálogo.

## Garantías
- **No inventa:** solo ve resultados de la BD; si no hay, devuelve vacío y el prompt del sistema le obliga a decirlo.
- **Precio/fecha/cupos no los escribe el modelo:** el modelo devuelve IDs de cursos y la interfaz los pinta desde la API.
- **Sin acciones:** no hay herramientas de reservar, pagar, cancelar o reembolsar (test `test_only_read_only_tools_exist`). Reservar sigue exigiendo sesión, reglas de negocio y clic del usuario.
- **Errores como dato** (`NOT_FOUND`, `invalid_arguments`) para que el modelo los explique sin excepciones.
- **Datos de contenido = datos, no instrucciones:** las descripciones de cursos se tratan como texto no confiable (mitigación de *prompt injection*); no se envían datos personales al modelo.

## Pendiente para activarlo
Endpoint `POST /api/v1/assistant/chat` (con límite de tasa y de coste), bucle de *tool use* con la API de Anthropic y la clave en variable de entorno (nunca en código), conjunto de evaluación ("algo creativo este fin de semana" → cursos reales de arte/manualidades), y confirmación del alcance con el cliente.

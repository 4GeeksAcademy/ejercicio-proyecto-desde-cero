# HITO 1 — Arquitectura inicial, repositorio, Docker y configuración

## Objetivo
Tener un esqueleto ejecutable con `docker compose up`: base de datos, backend con `/health`, frontend mínimo, configuración por entorno y CI mínima. Sin lógica de negocio todavía.

## Qué problema resuelve
Que cada hito posterior se construya sobre una base reproducible, sin secretos en el repo y con calidad automática desde el primer commit.

## Requisitos relacionados
[CLIENTE] C-14 (web encontrable, se prepara con Next.js) · [CLIENTE] RN-18 (lógica en backend) · [TÉCNICO] monolito modular · [PROPUESTA] logging estructurado y errores base desde el inicio (ajuste b del roadmap).

## Tecnologías
Git/GitHub, Docker + Compose, Python + FastAPI + pydantic-settings, pytest, ruff, Next.js + TypeScript + Tailwind, GitHub Actions.

## Pasos (cada uno: plan → cambio pequeño → explicación → test → commit)
| Paso | Contenido | Prueba de que funciona |
|---|---|---|
| 1.1 | `.gitignore` y `.env.example` | `git check-ignore .env` confirma que `.env` no se sube |
| 1.2 | Backend mínimo: FastAPI, config por entorno, `GET /health` | `pytest` + `curl /health` |
| 1.3 | Logging JSON, `request_id`, manejador central de errores | tests del formato de error y de que no se filtran secretos |
| 1.4 | Dockerfile backend + `docker-compose.yml` con PostgreSQL y healthchecks, `GET /ready` | `docker compose up` sano, `/ready` comprueba la BD |
| 1.5 | Frontend Next.js mínimo + Dockerfile | página carga en el contenedor |
| 1.6 | CI: lint, tipos, tests, docker build | workflow en verde |
| 1.7 | README real + ADR 0001 (monolito modular) y 0002 (FastAPI) | revisión |

## Archivos
`.gitignore`, `.env.example`, `backend/…`, `frontend/…`, `docker-compose.yml`, `.github/workflows/ci.yml`, `README.md`, `docs/adr/…`.

## Base de datos / endpoints
Solo el contenedor PostgreSQL (sin tablas). Endpoints: `GET /health` (viva) y `GET /ready` (lista para tráfico).

## Seguridad
Secretos solo por variables de entorno; `.env` ignorado por Git; contenedores con usuario no-root; versiones fijadas.

## Telemetría
Logs JSON con `request_id`; sin datos sensibles (OpenTelemetry completo llega en el Hito 10).

## Criterios de aceptación y Definition of Done
- `docker compose up` levanta db, backend y frontend; los healthchecks pasan.
- `/health` responde 200 y `/ready` falla si la BD no está disponible.
- Tests y lint pasan en local y en CI.
- Ningún secreto en el repo; `.env.example` documentado.
- README explica cómo arrancar y probar.

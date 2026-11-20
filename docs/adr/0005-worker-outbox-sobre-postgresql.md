# ADR-0005 — Procesamiento asíncrono: outbox + worker con polling a PostgreSQL

**Estado:** aceptada (revisa el borrador del análisis, que proponía Procrastinate) · **Etiqueta:** [TÉCNICO]

## Problema
Emails, notificaciones, caducidad de reservas y recordatorios no deben bloquear la petición web ni perderse si algo falla.

## Decisión
- **Outbox transaccional:** cada cambio de negocio inserta un `domain_events` en LA MISMA transacción (si la reserva se confirma, el evento existe; si se revierte, no).
- **Worker** (`python -m app.worker`): cada pocos segundos ejecuta caducidad, consume el outbox (`FOR UPDATE SKIP LOCKED`, varios workers seguros), envía emails pendientes y recordatorios. Cada trabajo usa su propia sesión.
- **Fiabilidad:** handlers idempotentes (`dedupe_key`), SAVEPOINT por evento (un evento "venenoso" no bloquea al resto; tras 5 intentos queda aparcado), emails con backoff exponencial y 5 intentos.
- **Corrección independiente del worker:** la disponibilidad ignora holds vencidos (ADR-0004); el worker solo limpia y notifica.

## Alternativas
Celery/Redis o una librería de cola: más piezas de infraestructura para una carga pequeña. Se puede migrar después manteniendo el outbox como fuente de verdad.

## Consecuencias
Latencia de notificación ≈ intervalo de polling (5 s por defecto). Una sola tecnología (PostgreSQL) que operar.

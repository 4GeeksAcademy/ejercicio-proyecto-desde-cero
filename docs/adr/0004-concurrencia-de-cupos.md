# ADR-0004 — Control de cupos y concurrencia en PostgreSQL

**Estado:** aceptada · **Etiqueta:** [TÉCNICO] (requisito [CLIENTE]: nunca sobrevender)

## Problema
Queda 1 plaza y dos personas reservan a la vez. Si ambas leen "queda 1" antes de que la otra escriba, las dos entran: sobreventa.

## Decisión
Tres defensas en capas, todas en backend/BD:
1. **Bloqueo de fila del curso** (`SELECT … FOR UPDATE` dentro de la transacción de reserva). Las reservas del mismo curso se serializan; las de cursos distintos no se afectan. Quien llega segundo espera milisegundos y ya ve el cupo actualizado.
2. **Índice único parcial** `(course_id, user_id) WHERE status IN (estados que ocupan plaza)`: la BD impide duplicados aunque el código fallara.
3. **Idempotency-Key** (tabla `idempotency_keys`): reintentos/dobles clics devuelven la misma respuesta.

## Cálculo de plazas
Una reserva ocupa plaza en `PENDING_PAYMENT` (mientras `expires_at` no venza), `PAYMENT_PROCESSING`, `PAID`, `PENDING_APPROVAL` y `CONFIRMED`. Los holds vencidos **no cuentan aunque el job aún no los haya marcado `EXPIRED`**: la corrección no depende del worker.

## Alternativas descartadas
- *Contador `seats_left` en el curso*: puede desincronizarse; hay que mantenerlo en cada transición.
- *Aislamiento SERIALIZABLE con reintentos*: más complejo para el equipo y reintentos visibles; el bloqueo explícito es más simple de razonar.
- *Bloqueo optimista (versión)*: reintentos bajo carga, peor UX en el caso "última plaza".

## Consecuencias
Rendimiento: un bloqueo corto por curso (aceptable a esta escala). Verificado con tests de carrera (`tests/integration/test_bookings.py`): 25 y 30 contendientes, 0 sobreventas.

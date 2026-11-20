# ADR-0001 — Monolito modular

**Estado:** aceptada · [TÉCNICO]

**Decisión.** Un backend desplegable (FastAPI) organizado en módulos de dominio (`auth`, `users`, `courses`, `bookings`, `payments`, `notifications`, `admin`, `audit`, `core_events`), cada uno con `models / schemas / service / router`. Un worker usa el mismo código.

**Por qué.** Reservas, pagos e historial necesitan transacciones ACID entre sí (p. ej. confirmar pago + cambiar estado + registrar comisión + escribir el evento de outbox en UNA transacción). Con un equipo pequeño, microservicios añadirían red, despliegues y consistencia eventual sin beneficio actual.

**Reglas de límites.** Los módulos se llaman por funciones de servicio y por eventos del outbox, no leyendo tablas ajenas a mano. Dependencias permitidas: `payments → bookings → courses`; `notifications` solo reacciona a eventos. Si un módulo creciera, se podría extraer porque ya habla por interfaces y eventos.

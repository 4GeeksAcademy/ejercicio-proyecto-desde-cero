# ADR-0002 — FastAPI + SQLAlchemy 2.0 async + Pydantic v2

**Estado:** aceptada · [TÉCNICO]

**Por qué FastAPI.** Validación declarativa (Pydantic), OpenAPI automático (de ahí se generan los tipos TypeScript del frontend: un único contrato), dependencias inyectables (`require_permission`) y soporte async para I/O (BD, pasarela, email).

**Capas.** `router` (HTTP) → `service` (reglas de negocio y transacciones) → modelos SQLAlchemy. Los modelos de BD **no** se devuelven directamente: cada endpoint declara un `response_model` que oculta campos internos (`password_hash`, etc.).

**Coste asumido.** En async no hay carga perezosa implícita: las relaciones se cargan explícitamente (`selectin`/`joined`/recarga). Lo vimos en la práctica y está cubierto por tests.

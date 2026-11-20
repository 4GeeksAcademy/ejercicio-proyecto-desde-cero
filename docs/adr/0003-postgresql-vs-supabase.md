# ADR-0003 — PostgreSQL estándar (Supabase solo como posible hosting)

**Estado:** aceptada · [TÉCNICO]

**Decisión.** PostgreSQL 17 estándar: contenedor en desarrollo y Postgres gestionado en producción (puede ser el de Supabase **solo como hosting**). Autenticación propia en FastAPI; sin Row Level Security (RLS).

**Por qué no usar Supabase Auth/RLS.**
- Todo acceso a datos pasa por FastAPI, que ya aplica RBAC y propiedad del recurso; RLS duplicaría la autorización en dos sitios.
- El modelo de roles/permisos, consentimientos, bloqueo por intentos y rotación de refresh tokens es parte del aprendizaje y del producto.
- Menor acoplamiento a un proveedor.

**Cuándo reconsiderarlo.** Si el frontend necesitara consultar la BD directamente, o para Supabase Storage (imágenes de cursos), donde sí aporta valor sin tocar el dominio.

**Seguridad en BD.** El usuario de la aplicación no debería tener privilegios de DDL (el de migraciones sí): pendiente al configurar producción. `audit_logs` es de solo inserción por trigger.

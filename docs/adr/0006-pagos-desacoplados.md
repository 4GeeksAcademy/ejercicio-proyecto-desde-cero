# ADR-0006 — Pagos desacoplados mediante puerto/adaptador

**Estado:** aceptada · **Etiquetas:** [TÉCNICO]; proveedor real **[PENDIENTE P-02]**

## Decisión
El dominio de reservas no conoce a ningún proveedor. `payments/provider.py` define `PaymentProvider` (`create_checkout`, `verify_webhook`, `get_status`, `refund`). Hoy existe `FakePaymentProvider` (firma HMAC-SHA256 igual que uno real) para desarrollo y tests; el adaptador real (Wompi, Mercado Pago, PayU, ePayco… a verificar) se añade sin tocar reservas.

## Garantías
- **Webhooks:** firma + marca de tiempo (anti-replay), estado confirmado contra el proveedor (no se confía solo en el payload), importe y moneda comparados con lo que esperamos, y `UNIQUE(provider, provider_event_id)` para idempotencia (también bajo concurrencia).
- **Tarjetas:** checkout alojado por el proveedor; Tallerya no recibe ni guarda PAN/CVV (test `test_no_card_data_columns_exist`).
- **Dinero:** enteros en la unidad mínima + moneda; comisión en puntos básicos con redondeo documentado y `CHECK (comisión + neto = bruto)`.
- **Comisión:** snapshot por reserva al confirmarse el pago; cambiar el % no reescribe el pasado.
- **Pago tardío / reserva cerrada:** no se confirma plaza; se emite `payment_needs_refund` (RN-14).
- **Llamada externa fuera del bloqueo:** el cobro se inicia tras liberar los locks de BD.

## Pendiente del cliente
P-01 (quién recibe el 20 %), P-02 (proveedor/moneda), P-04/P-05 (reembolsos): hoy solo se reembolsa si la reserva está cerrada.

"""Cálculo de comisión. Dinero = enteros en la unidad mínima (centavos). NUNCA float.

Regla de redondeo [PROPUESTA, confirmar en P-01]: la comisión se redondea al entero más cercano
(mitades hacia arriba) y el resto es `neto = bruto - comisión`, así `comisión + neto == bruto` SIEMPRE
(no se pierde ni se inventa ni un centavo).
"""

BPS_DENOMINATOR = 10_000  # 1 bps = 0,01 %; 2000 bps = 20 %


def compute_commission(gross_minor: int, bps: int) -> tuple[int, int]:
    if gross_minor < 0:
        raise ValueError("El importe no puede ser negativo")
    if not 0 <= bps <= BPS_DENOMINATOR:
        raise ValueError("Los puntos básicos deben estar entre 0 y 10000")
    commission = (gross_minor * bps + BPS_DENOMINATOR // 2) // BPS_DENOMINATOR
    return commission, gross_minor - commission

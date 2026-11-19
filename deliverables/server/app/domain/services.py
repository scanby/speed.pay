from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal


_UNIDADES = (
    "",
    "un",
    "dos",
    "tres",
    "cuatro",
    "cinco",
    "seis",
    "siete",
    "ocho",
    "nueve",
)

_ESPECIALES = {
    10: "diez",
    11: "once",
    12: "doce",
    13: "trece",
    14: "catorce",
    15: "quince",
    16: "dieciséis",
    17: "diecisiete",
    18: "dieciocho",
    19: "diecinueve",
    20: "veinte",
    21: "veintiún",
    22: "veintidós",
    23: "veintitrés",
    24: "veinticuatro",
    25: "veinticinco",
    26: "veintiséis",
    27: "veintisiete",
    28: "veintiocho",
    29: "veintinueve",
}

_DECENAS = (
    "",
    "",
    "",
    "treinta",
    "cuarenta",
    "cincuenta",
    "sesenta",
    "setenta",
    "ochenta",
    "noventa",
)

_CENTENAS = (
    "",
    "ciento",
    "doscientos",
    "trescientos",
    "cuatrocientos",
    "quinientos",
    "seiscientos",
    "setecientos",
    "ochocientos",
    "novecientos",
)


def _convertir_menor_mil(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "cien"
    partes = []
    centenas = n // 100
    resto = n % 100
    if centenas > 0:
        partes.append(_CENTENAS[centenas])
    if resto > 0:
        if resto in _ESPECIALES:
            partes.append(_ESPECIALES[resto])
        elif resto < 10:
            partes.append(_UNIDADES[resto])
        else:
            dec = resto // 10
            uni = resto % 10
            if uni == 0:
                partes.append(_DECENAS[dec])
            else:
                partes.append(f"{_DECENAS[dec]} y {_UNIDADES[uni]}")
    return " ".join(partes)


def entero_a_letras(numero: int) -> str:
    if numero == 0:
        return "cero"
    if numero < 0:
        return f"menos {entero_a_letras(abs(numero))}"

    millones = numero // 1_000_000
    miles = (numero % 1_000_000) // 1_000
    unidades = numero % 1_000

    partes = []
    if millones > 0:
        if millones == 1:
            partes.append("un millón")
        else:
            partes.append(f"{_convertir_menor_mil(millones)} millones")

    if miles > 0:
        if miles == 1:
            partes.append("mil")
        else:
            partes.append(f"{_convertir_menor_mil(miles)} mil")

    if unidades > 0:
        partes.append(_convertir_menor_mil(unidades))

    return " ".join(partes).strip()


def monto_a_letras(monto: Decimal) -> str:
    """Convierte un monto COP a frase legible en español para síntesis TTS."""
    entero = int(monto)
    centavos = int((monto - Decimal(entero)) * 100)
    sufijo_moneda = "peso" if entero == 1 else "pesos"
    texto_entero = entero_a_letras(entero)
    if entero >= 1_000_000 and entero % 1_000_000 == 0:
        sufijo_moneda = "de pesos"

    if centavos > 0:
        texto_centavos = entero_a_letras(centavos)
        sufijo_cent = "centavo" if centavos == 1 else "centavos"
        return f"{texto_entero} {sufijo_moneda} con {texto_centavos} {sufijo_cent}"

    return f"{texto_entero} {sufijo_moneda}"


def compute_idempotency_hash(
    account_id: int,
    sender_name: str,
    amount_cop: Decimal,
    captured_at: datetime,
    window_seconds: int = 120,
) -> str:
    """
    Genera un hash SHA-256 determinístico combinando:
    cuenta_id + remitente normalizado + monto exacto + ventana de tiempo discreta.
    Previene duplicados ante reintentos de red de WorkManager o notificaciones repetidas.
    """
    epoch_seconds = int(captured_at.timestamp())
    time_bucket = epoch_seconds // max(1, window_seconds)
    normalized_sender = " ".join(sender_name.strip().lower().split())
    normalized_amount = f"{amount_cop.quantize(Decimal('0.01'))}"
    payload = f"{account_id}|{normalized_sender}|{normalized_amount}|{time_bucket}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_tts_phrase(amount_cop: Decimal) -> str:
    return f"Pago por el valor de {monto_a_letras(amount_cop)}"

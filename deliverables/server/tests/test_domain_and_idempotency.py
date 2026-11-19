from datetime import datetime
from decimal import Decimal

from app.domain.services import build_tts_phrase, compute_idempotency_hash, monto_a_letras
from app.infrastructure.updater_service import parse_semver


def test_monto_a_letras_valores_colombia() -> None:
    assert monto_a_letras(Decimal("1")) == "un peso"
    assert monto_a_letras(Decimal("45000")) == "cuarenta y cinco mil pesos"
    assert monto_a_letras(Decimal("120500")) == "ciento veinte mil quinientos pesos"
    assert monto_a_letras(Decimal("1000000")) == "un millón de pesos"
    assert monto_a_letras(Decimal("2350800")) == "dos millones trescientos cincuenta mil ochocientos pesos"
    assert build_tts_phrase(Decimal("45000")) == "Pago por el valor de cuarenta y cinco mil pesos"


def test_idempotency_hash_deterministico_por_ventana() -> None:
    t1 = datetime(2026, 5, 10, 14, 20, 10)
    t2 = datetime(2026, 5, 10, 14, 21, 50)
    t3 = datetime(2026, 5, 10, 14, 25, 0)

    h1 = compute_idempotency_hash(1, "Carlos  Mendoza ", Decimal("45000.00"), t1, 120)
    h2 = compute_idempotency_hash(1, "carlos mendoza", Decimal("45000"), t2, 120)
    h3 = compute_idempotency_hash(1, "carlos mendoza", Decimal("45000"), t3, 120)

    assert len(h1) == 64
    assert h1 == h2
    assert h1 != h3


def test_semver_version_comparison() -> None:
    assert parse_semver("v1.2.0") > parse_semver("1.0.0")
    assert parse_semver("1.0.10") > parse_semver("1.0.2")
    assert parse_semver("v1.0.0") == parse_semver("1.0.0")

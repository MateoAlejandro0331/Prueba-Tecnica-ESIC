"""Tests de las reglas de validación/normalización de campos y de validar_fila."""

import pytest

from src.validaciones import validar_fila


def fila_valida(**overrides) -> dict:
    base = {
        "id_solicitud": "SOL-001",
        "fecha": "2026-01-15",
        "nombre": "Ana Pérez",
        "correo": "ana@example.com",
        "tipo_solicitud": "Compra",
        "valor": "150.50",
        "estado": "pendiente",
    }
    base.update(overrides)
    return base


def test_validar_fila_valida_normaliza_fecha_y_estado():
    errores, solicitud = validar_fila(fila_valida(fecha="15/01/2026", estado="RECHAZADA"))
    assert errores == []
    assert solicitud is not None
    assert solicitud.fecha == "2026-01-15"
    assert solicitud.estado == "Rechazado"
    assert solicitud.valor == 150.5


def test_validar_fila_colecciona_todos_los_errores_no_solo_el_primero():
    fila = fila_valida(nombre="", correo="invalido", valor="-5", estado="Desconocido")
    errores, solicitud = validar_fila(fila)
    assert solicitud is None
    assert "Nombre vacío" in errores
    assert "Correo inválido" in errores
    assert "Valor negativo" in errores
    assert "Estado no válido" in errores
    assert len(errores) == 4


@pytest.mark.parametrize(
    "overrides,mensaje_esperado",
    [
        ({"id_solicitud": ""}, "ID de solicitud vacío"),
        ({"nombre": ""}, "Nombre vacío"),
        ({"correo": "no-es-un-correo"}, "Correo inválido"),
        ({"tipo_solicitud": "Devolución"}, "Tipo de solicitud inválido"),
        ({"valor": "-10"}, "Valor negativo"),
        ({"valor": "abc"}, "Valor no numérico"),
        ({"estado": "Desconocido"}, "Estado no válido"),
        ({"fecha": "32/01/2026"}, "Fecha inválida"),
    ],
)
def test_validar_fila_rechaza_campo_invalido(overrides, mensaje_esperado):
    errores, solicitud = validar_fila(fila_valida(**overrides))
    assert solicitud is None
    assert mensaje_esperado in errores

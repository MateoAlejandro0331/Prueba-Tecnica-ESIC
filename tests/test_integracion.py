"""Tests de la simulación de envío al servicio externo y su lógica de reintento."""

from unittest.mock import Mock

import pytest

from src import integracion
from src.integracion import (
    ErrorDefinitivoAPI,
    ErrorTemporalAPI,
    enviar_con_reintento,
    enviar_solicitud_simulada,
    enviar_solicitudes_validas,
)


def test_enviar_solicitud_simulada_exito(monkeypatch):
    monkeypatch.setattr(integracion.random, "random", lambda: 0.0)
    assert enviar_solicitud_simulada({"id_solicitud": "SOL-1"}) is None


def test_enviar_solicitud_simulada_limites_de_probabilidad(monkeypatch):
    # 0.75 exacto ya no cuenta como éxito (< estricto) -> error temporal.
    monkeypatch.setattr(integracion.random, "random", lambda: 0.75)
    with pytest.raises(ErrorTemporalAPI):
        enviar_solicitud_simulada({"id_solicitud": "SOL-1"})

    # 0.90 exacto ya no cuenta como temporal -> error definitivo.
    monkeypatch.setattr(integracion.random, "random", lambda: 0.90)
    with pytest.raises(ErrorDefinitivoAPI):
        enviar_solicitud_simulada({"id_solicitud": "SOL-1"})


def test_enviar_con_reintento_exito_primer_intento(monkeypatch):
    mock_envio = Mock(return_value=None)
    monkeypatch.setattr(integracion, "enviar_solicitud_simulada", mock_envio)

    resultado = enviar_con_reintento({"id_solicitud": "SOL-1"})

    assert resultado == {"id_solicitud": "SOL-1", "estado_envio": "exitoso", "motivo": None}
    assert mock_envio.call_count == 1


def test_enviar_con_reintento_temporal_y_luego_exito(monkeypatch):
    mock_envio = Mock(side_effect=[ErrorTemporalAPI("timeout"), None])
    monkeypatch.setattr(integracion, "enviar_solicitud_simulada", mock_envio)

    resultado = enviar_con_reintento({"id_solicitud": "SOL-1"})

    assert resultado["estado_envio"] == "exitoso"
    assert mock_envio.call_count == 2


def test_enviar_con_reintento_agota_intentos_en_error_temporal(monkeypatch):
    mock_envio = Mock(side_effect=[ErrorTemporalAPI("t1"), ErrorTemporalAPI("t2")])
    monkeypatch.setattr(integracion, "enviar_solicitud_simulada", mock_envio)

    resultado = enviar_con_reintento({"id_solicitud": "SOL-1"}, max_intentos=2)

    assert resultado == {"id_solicitud": "SOL-1", "estado_envio": "fallido", "motivo": "t2"}
    assert mock_envio.call_count == 2


def test_enviar_con_reintento_error_definitivo_no_reintenta(monkeypatch):
    mock_envio = Mock(side_effect=[ErrorDefinitivoAPI("rechazado")])
    monkeypatch.setattr(integracion, "enviar_solicitud_simulada", mock_envio)

    resultado = enviar_con_reintento({"id_solicitud": "SOL-1"}, max_intentos=2)

    assert resultado == {"id_solicitud": "SOL-1", "estado_envio": "fallido", "motivo": "rechazado"}
    assert mock_envio.call_count == 1


def test_enviar_con_reintento_error_inesperado_es_terminal(monkeypatch):
    mock_envio = Mock(side_effect=[RuntimeError("boom")])
    monkeypatch.setattr(integracion, "enviar_solicitud_simulada", mock_envio)

    resultado = enviar_con_reintento({"id_solicitud": "SOL-1"}, max_intentos=2)

    assert resultado["estado_envio"] == "fallido"
    assert mock_envio.call_count == 1


def test_enviar_solicitudes_validas_procesa_todas_y_no_se_detiene_ante_fallos(monkeypatch):
    resultados_por_id = {
        "SOL-1": None,
        "SOL-2": ErrorDefinitivoAPI("rechazado"),
        "SOL-3": None,
    }

    def envio_simulado(solicitud):
        resultado = resultados_por_id[solicitud["id_solicitud"]]
        if resultado is not None:
            raise resultado

    monkeypatch.setattr(integracion, "enviar_solicitud_simulada", envio_simulado)

    solicitudes = [{"id_solicitud": id_} for id_ in resultados_por_id]
    resultados = enviar_solicitudes_validas(solicitudes)

    assert len(resultados) == 3
    estados = {r["id_solicitud"]: r["estado_envio"] for r in resultados}
    assert estados == {"SOL-1": "exitoso", "SOL-2": "fallido", "SOL-3": "exitoso"}

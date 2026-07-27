"""Tests de lectura del CSV, clasificación de solicitudes, resumen y escritura
de resultados.
"""

import json

import pandas as pd
import pytest

from src.procesamiento import (
    COLUMNAS_ENTRADA,
    construir_resumen,
    detectar_ids_duplicados,
    guardar_resultados,
    leer_archivo_solicitudes,
    procesar_solicitudes,
)


def fila(**overrides) -> dict:
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


def test_leer_archivo_solicitudes_ok(tmp_path):
    ruta = tmp_path / "solicitudes.csv"
    pd.DataFrame([fila(), fila(id_solicitud="SOL-002")], columns=COLUMNAS_ENTRADA).to_csv(ruta, index=False)

    df = leer_archivo_solicitudes(ruta)

    assert len(df) == 2
    assert df["valor"].iloc[0] == "150.50"  # sin inferencia de tipos: no se coerciona a float


def test_leer_archivo_solicitudes_columna_faltante(tmp_path):
    ruta = tmp_path / "incompleto.csv"
    pd.DataFrame([{"id_solicitud": "SOL-001"}]).to_csv(ruta, index=False)
    with pytest.raises(ValueError, match="columnas esperadas"):
        leer_archivo_solicitudes(ruta)


def test_detectar_ids_duplicados_ignora_vacios():
    df = pd.DataFrame({"id_solicitud": ["A", "A", "B", "C", "C", "C", "", ""]})
    assert detectar_ids_duplicados(df) == {"A", "C"}


def test_procesar_solicitudes_separa_validas_y_con_errores():
    df = pd.DataFrame([fila(), fila(id_solicitud="SOL-002", correo="invalido")])
    validas, con_errores, ids_duplicados = procesar_solicitudes(df)
    assert len(validas) == 1
    assert con_errores[0]["errores"] == "Correo inválido"
    assert ids_duplicados == set()
    assert len(validas) + len(con_errores) == len(df)


def test_procesar_solicitudes_id_duplicado_se_rechaza_y_prepone_error():
    df = pd.DataFrame([
        fila(id_solicitud="SOL-DUP"),
        fila(id_solicitud="SOL-DUP", correo="invalido"),
    ])
    validas, con_errores, ids_duplicados = procesar_solicitudes(df)
    assert validas == []
    assert ids_duplicados == {"SOL-DUP"}
    fila_con_correo_malo = next(r for r in con_errores if r["correo"] == "invalido")
    assert fila_con_correo_malo["errores"] == "ID duplicado; Correo inválido"


def test_construir_resumen_cuenta_ids_duplicados_distintos_no_filas():
    df = pd.DataFrame([
        fila(id_solicitud="SOL-DUP", correo="uno@example.com"),
        fila(id_solicitud="SOL-DUP", correo="dos@example.com"),
        fila(id_solicitud="SOL-DUP", correo="tres@example.com"),
    ])
    validas, con_errores, ids_duplicados = procesar_solicitudes(df)
    resumen = construir_resumen(validas, con_errores, ids_duplicados)
    assert resumen["cantidad_duplicados"] == 1
    assert resumen["registros_con_errores"] == 3


def test_construir_resumen_totales_y_valor_total():
    df = pd.DataFrame([
        fila(id_solicitud="SOL-1", valor="100", tipo_solicitud="Compra", estado="pendiente"),
        fila(id_solicitud="SOL-2", valor="50.5", tipo_solicitud="Soporte", estado="completado"),
        fila(id_solicitud="SOL-3", correo="invalido"),
    ])
    validas, con_errores, ids_duplicados = procesar_solicitudes(df)
    resumen = construir_resumen(validas, con_errores, ids_duplicados)
    assert resumen["total_registros"] == 3
    assert resumen["registros_validos"] == 2
    assert resumen["valor_total_solicitudes_validas"] == pytest.approx(150.5)
    assert resumen["solicitudes_por_tipo"] == {"Compra": 1, "Soporte": 1}


def test_construir_resumen_sin_validas():
    resumen = construir_resumen([], [], set())
    assert resumen["valor_total_solicitudes_validas"] == 0.0
    assert resumen["solicitudes_por_tipo"] == {}


def test_guardar_resultados_escribe_los_tres_archivos(tmp_path):
    validas = [{**{c: "" for c in COLUMNAS_ENTRADA}, "id_solicitud": "SOL-1", "valor": 100.0}]
    con_errores = [{**{c: "" for c in COLUMNAS_ENTRADA}, "id_solicitud": "SOL-2", "errores": "Correo inválido"}]
    resumen = {"total_registros": 2, "registros_validos": 1}

    guardar_resultados(tmp_path, validas, con_errores, resumen)

    assert (tmp_path / "solicitudes_validas.csv").exists()
    assert (tmp_path / "solicitudes_con_errores.csv").exists()
    with open(tmp_path / "resumen.json", encoding="utf-8") as archivo:
        assert json.load(archivo) == resumen

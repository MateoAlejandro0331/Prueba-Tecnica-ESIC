"""Lectura del CSV de entrada, validación/clasificación de solicitudes, construcción
del resumen y escritura de los archivos de salida (`solicitudes_validas.csv`,
`solicitudes_con_errores.csv`, `resumen.json`).
"""

from __future__ import annotations

import logging
import pandas as pd
from pathlib import Path
import json
from datetime import datetime
from .validaciones import validar_fila
logger = logging.getLogger(__name__)

#Variable para identificar que el archivo de entrada si corresponde al formato recibido por la aplicación
COLUMNAS_ENTRADA = ["id_solicitud", "fecha", "nombre", "correo", "tipo_solicitud", "valor", "estado"]
COLUMNAS_ERRORES = COLUMNAS_ENTRADA + ["errores"]

def leer_archivo_solicitudes(archivo_csv: str | Path) -> pd.DataFrame:
    """Lee el CSV de solicitudes como texto plano y valida que tenga las columnas esperadas.

    Args:
        archivo_csv: Ruta al CSV de entrada.

    Returns:
        DataFrame con todas las columnas como texto, sin normalizar.

    Raises:
        ValueError: Si al archivo le falta alguna de las columnas de `COLUMNAS_ENTRADA`.
    """
    df = pd.read_csv(archivo_csv, dtype=str, keep_default_na=False, encoding="utf-8")
    faltantes = set(COLUMNAS_ENTRADA) - set(df.columns)
    if faltantes:
        raise ValueError(f"El archivo no tiene las columnas esperadas: {sorted(faltantes)}")
    return df

def detectar_ids_duplicados(df: pd.DataFrame) -> set[str]:
    """IDs (no vacíos) que aparecen en más de una fila del archivo."""
    ids = df["id_solicitud"].astype(str).str.strip()
    ids = ids[ids != ""]
    conteo = ids.value_counts()
    return set(conteo[conteo > 1].index)

def procesar_solicitudes(df: pd.DataFrame) -> tuple[list[dict], list[dict], set[str]]:
    """Valida cada fila del DataFrame y la separa en válidas o con errores.

    Las filas con `id_solicitud` duplicado también se validan campo por campo: se les
    antepone el error `"ID duplicado"` a cualquier otro error que tengan, en vez de
    rechazarlas solo por la duplicación. Ninguna fila se descarta: toda fila termina
    en `solicitudes_validas` o en `solicitudes_errores`.

    Args:
        df: DataFrame crudo devuelto por `leer_archivo_solicitudes`.

    Returns:
        Tupla `(solicitudes_validas, solicitudes_errores, ids_duplicados)`: las dos
        primeras son listas de dicts (una por fila) y la tercera es el set de
        `id_solicitud` que aparecen más de una vez.
    """
    ids_duplicados = detectar_ids_duplicados(df)
    
    solicitudes_validas = []
    solicitudes_errores = []
    
    for fila in df.to_dict(orient="records"):
        id_fila = str(fila.get("id_solicitud") or "").strip()
        errores, solicitud = validar_fila(fila)
          
        if id_fila and id_fila in ids_duplicados:
            errores = ["ID duplicado"] + errores

        if errores:
            registro = {columna: fila.get(columna, "") for columna in COLUMNAS_ENTRADA}
            registro["errores"] = "; ".join(errores)
            solicitudes_errores.append(registro)
            logger.warning("Solicitud %s rechazada: %s", id_fila or "(sin id)", registro["errores"])
        else:
            assert solicitud is not None
            solicitudes_validas.append(solicitud.model_dump())
            logger.info("Solicitud %s validada correctamente", id_fila)

    return solicitudes_validas, solicitudes_errores, ids_duplicados

def construir_resumen(validas: list[dict], con_errores: list[dict], ids_duplicados: set[str]) -> dict:
    """Arma el diccionario para crear resumen.json a partir de lo ya calculado en
    `procesar_solicitudes` (no vuelve a leer el DataFrame original).

    Args:
        validas: Solicitudes válidas, como las devuelve `procesar_solicitudes`.
        con_errores: Solicitudes rechazadas, como las devuelve `procesar_solicitudes`.
        ids_duplicados: Set de `id_solicitud` duplicados.

    Returns:
        Dict listo para serializar a `resumen.json`. `cantidad_duplicados` cuenta
        identificadores **distintos** duplicados, no la cantidad de filas afectadas
        (un ID repetido 3 veces cuenta como 1).
    """
    df_validas = pd.DataFrame(validas, columns=COLUMNAS_ENTRADA)

    return {
        "fecha_ejecucion": datetime.now().isoformat(timespec="seconds"),
        "total_registros": len(validas) + len(con_errores),
        "registros_validos": len(validas),
        "registros_con_errores": len(con_errores),
        "cantidad_duplicados": len(ids_duplicados),
        "solicitudes_por_tipo": df_validas["tipo_solicitud"].value_counts().to_dict(),
        "solicitudes_por_estado": df_validas["estado"].value_counts().to_dict(),
        "valor_total_solicitudes_validas": float(df_validas["valor"].sum()) if not df_validas.empty else 0.0,
    }
    
def guardar_resultados(carpeta_salida: str | Path, validas: list[dict], con_errores: list[dict], resumen: dict) -> None:
    """Escribe solicitudes_validas.csv, solicitudes_con_errores.csv y resumen.json."""
    carpeta = Path(carpeta_salida)
    carpeta.mkdir(parents=True, exist_ok=True)

    # utf-8-sig para que Excel en Windows muestre bien las tildes/ñ.
    pd.DataFrame(validas, columns=COLUMNAS_ENTRADA).to_csv(
        carpeta / "solicitudes_validas.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(con_errores, columns=COLUMNAS_ERRORES).to_csv(
        carpeta / "solicitudes_con_errores.csv", index=False, encoding="utf-8-sig"
    )
    with open(carpeta / "resumen.json", "w", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, indent=2)

    logger.info(
        "Resultados guardados en %s (validas=%d, con_errores=%d)",
        carpeta, len(validas), len(con_errores),
    )
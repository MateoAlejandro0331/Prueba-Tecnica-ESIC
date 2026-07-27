"""Punto de entrada de la CLI: lee un CSV de solicitudes, las valida/normaliza,
separa válidas de rechazadas, escribe los resultados y simula su envío a un
servicio externo. Ejecutar con `python main.py --input <csv> --output <carpeta>`.
"""

import argparse
import logging
import sys
from pathlib import Path
from src.procesamiento import *
from src.integracion import enviar_solicitudes_validas

logger = logging.getLogger(__name__)


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos (--input, --output)."""
    parser = argparse.ArgumentParser(
        description="Valida, normaliza y clasifica solicitudes desde un archivo CSV."
    )
    parser.add_argument("--input", required=True, help="Ruta del archivo CSV de entrada.")
    parser.add_argument("--output", required=True, help="Carpeta donde se guardan los resultados.")
    return parser.parse_args(argv)

def configurar_logging(carpeta_salida: Path) -> None:
    """Escribe el log tanto en consola como en <carpeta_salida>/log_procesamiento.txt."""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(carpeta_salida / "log_procesamiento.txt", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Orquesta el pipeline completo: lectura, validación, resultados e integración.

    Escribe `solicitudes_validas.csv`, `solicitudes_con_errores.csv`, `resumen.json`
    y `log_procesamiento.txt` en `argumentos.output`, y simula el envío de las
    solicitudes válidas al servicio externo. Cualquier error de lectura/formato del
    CSV de entrada se captura y se registra en el log en vez de propagarse.

    Args:
        argv: Argumentos de línea de comandos a parsear (`--input`, `--output`).
            Si es `None`, se toman de `sys.argv` (comportamiento por defecto de
            `argparse`).

    Returns:
        0 si el procesamiento terminó, con o sin registros rechazados. 1 si el
        archivo de entrada no existe (`FileNotFoundError`), no tiene el formato
        esperado (`ValueError`), o ocurrió un error inesperado.
    """
    argumentos = parsear_argumentos(argv)
    carpeta_salida = Path(argumentos.output)
    configurar_logging(carpeta_salida)
    
    logger.info("Inicio del procesamiento. Archivo de entrada: %s", argumentos.input)

    try:
        df = leer_archivo_solicitudes(argumentos.input)
        logger.info("Archivo leído correctamente: %d filas encontradas.", len(df))

        validas, con_errores, ids_duplicados = procesar_solicitudes(df)
        resumen = construir_resumen(validas, con_errores, ids_duplicados)
        guardar_resultados(carpeta_salida, validas, con_errores, resumen)

        if validas:
            enviar_solicitudes_validas(validas)

        logger.info(
            "Procesamiento finalizado. Total: %d | Válidas: %d | Con errores: %d | Duplicados: %d",
            resumen["total_registros"],
            resumen["registros_validos"],
            resumen["registros_con_errores"],
            resumen["cantidad_duplicados"],
        )
        return 0

    except FileNotFoundError:
        logger.error("No se encontró el archivo de entrada: %s", argumentos.input)
        return 1
    except ValueError as error:
        logger.error("El archivo de entrada no tiene el formato esperado: %s", error)
        return 1
    except Exception:
        logger.exception("Error inesperado durante el procesamiento.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
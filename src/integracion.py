from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)

PROBABILIDAD_EXITO = 0.75
PROBABILIDAD_ERROR_TEMPORAL = 0.15
# El resto de la probabilidad (0.10) corresponde a error definitivo.

MAX_INTENTOS_DEFECTO = 2


class ErrorTemporalAPI(Exception):
    """Falla transitoria del servicio externo: vale la pena reintentar."""


class ErrorDefinitivoAPI(Exception):
    """Falla permanente del servicio externo: no debe reintentarse."""


def enviar_solicitud_simulada(solicitud: dict) -> None:
    """Simula un único intento de envío a un servicio externo.

    No hay red real: el resultado se decide al azar, reproduciendo los
    3 escenarios posibles (envío exitoso, error temporal, error definitivo).
    """
    dado = random.random()
    if dado < PROBABILIDAD_EXITO:
        return
    if dado < PROBABILIDAD_EXITO + PROBABILIDAD_ERROR_TEMPORAL:
        raise ErrorTemporalAPI("Timeout del servicio externo")
    raise ErrorDefinitivoAPI("El servicio externo rechazó la solicitud")


def enviar_con_reintento(solicitud: dict, max_intentos: int = MAX_INTENTOS_DEFECTO) -> dict:
    """Envía una solicitud al servicio externo, reintentando solo ante errores temporales."""
    id_solicitud = solicitud.get("id_solicitud", "(sin id)")

    for intento in range(1, max_intentos + 1):
        try:
            enviar_solicitud_simulada(solicitud)
        except ErrorTemporalAPI as error:
            logger.warning(
                "Envío de %s: error temporal en intento %d/%d (%s)",
                id_solicitud, intento, max_intentos, error,
            )
            if intento == max_intentos:
                return {"id_solicitud": id_solicitud, "estado_envio": "fallido", "motivo": str(error)}
        except ErrorDefinitivoAPI as error:
            logger.error("Envío de %s: error definitivo (%s). No se reintenta.", id_solicitud, error)
            return {"id_solicitud": id_solicitud, "estado_envio": "fallido", "motivo": str(error)}
        except Exception as error:
            # Cualquier fallo no anticipado se trata como definitivo, para no
            # interrumpir el envío de las demás solicitudes.
            logger.exception("Envío de %s: error inesperado.", id_solicitud)
            return {"id_solicitud": id_solicitud, "estado_envio": "fallido", "motivo": str(error)}
        else:
            logger.info("Envío de %s: exitoso en intento %d/%d.", id_solicitud, intento, max_intentos)
            return {"id_solicitud": id_solicitud, "estado_envio": "exitoso", "motivo": None}

    return {"id_solicitud": id_solicitud, "estado_envio": "fallido", "motivo": "Reintentos agotados"}


def enviar_solicitudes_validas(solicitudes: list[dict], max_intentos: int = MAX_INTENTOS_DEFECTO) -> list[dict]:
    """Envía todas las solicitudes válidas al servicio externo simulado.
    El fallo de una solicitud individual no interrumpe el envío de las demás.
    """
    resultados = [enviar_con_reintento(solicitud, max_intentos) for solicitud in solicitudes]

    exitosos = sum(1 for resultado in resultados if resultado["estado_envio"] == "exitoso")
    fallidos = len(resultados) - exitosos
    logger.info(
        "Integración con servicio externo finalizada. Enviadas: %d | Exitosas: %d | Fallidas: %d",
        len(resultados), exitosos, fallidos,
    )
    return resultados

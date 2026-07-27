"""Reglas de validación y normalización por campo de una solicitud, implementadas
como `field_validator`s de Pydantic sobre `SolicitudValidada`.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

TIPOS_VALIDOS = {"Compra", "Reembolso", "Acceso", "Soporte"}

_ESTADOS_VALIDOS = {
    "pendiente": "Pendiente",
    "en proceso": "En proceso",
    "completado": "Completado",
    "completada": "Completado",
    "rechazado": "Rechazado",
    "rechazada": "Rechazado",
}

#Expresión regular para hacer match con cualquier email
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_FORMATOS_FECHA = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y")


def normalizar_estado(valor: str | None) -> str | None:
    """Devuelve el estado estandarizado o None si no es normalizable."""
    if valor is None:
        return None
    clave = " ".join(str(valor).strip().lower().split())
    return _ESTADOS_VALIDOS.get(clave)


def es_correo_valido(valor: str | None) -> bool:
    """Valida estructura básica local@dominio.tld sin puntos consecutivos."""
    if not valor:
        return False
    valor = str(valor).strip()
    if valor.count("@") != 1:
        return False
    if ".." in valor or valor.startswith(".") or valor.endswith("."):
        return False
    if not _EMAIL_PATTERN.match(valor):
        return False
    local, dominio = valor.split("@")
    return bool(local) and "." in dominio


def normalizar_fecha(valor: str | None) -> str | None:
    """Intenta convertir la fecha a formato ISO (YYYY-MM-DD)."""
    if not valor:
        return None
    texto = str(valor).strip()
    for formato in _FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parsear_valor_numerico(valor) -> float:
    """Convierte el campo 'valor' a float o lanza ValueError con el motivo."""
    texto = str(valor).strip() if valor is not None else ""
    if not texto:
        raise ValueError("Valor vacío")
    try:
        return float(texto)
    except ValueError as exc:
        raise ValueError("Valor no numérico") from exc


class SolicitudValidada(BaseModel):
    """Valida y normaliza una fila del CSV de solicitudes.

    Attributes:
        id_solicitud: Identificador único de la solicitud (no vacío).
        fecha: Fecha normalizada a ISO `YYYY-MM-DD`.
        nombre: Nombre del solicitante (no vacío).
        correo: Correo electrónico con formato `local@dominio.tld` válido.
        tipo_solicitud: Uno de `TIPOS_VALIDOS` (`Compra`, `Reembolso`, `Acceso`, `Soporte`).
        valor: Monto de la solicitud, no negativo.
        estado: Estado normalizado a uno de los 4 valores de `_ESTADOS_VALIDOS`.
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    id_solicitud: str
    fecha: str
    nombre: str
    correo: str
    tipo_solicitud: str
    valor: float
    estado: str

    @field_validator("id_solicitud")
    @classmethod
    def _id_obligatorio(cls, v: str) -> str:
        """Rechaza id_solicitud vacío (regla "Identificador obligatorio")."""
        if not v:
            raise ValueError("ID de solicitud vacío")
        return v

    @field_validator("fecha", mode="before")
    @classmethod
    def _fecha_normalizable(cls, v) -> str:
        """Normaliza la fecha a ISO (YYYY-MM-DD) o rechaza si no coincide con ningún formato soportado."""
        normalizada = normalizar_fecha(v)
        if normalizada is None:
            raise ValueError("Fecha inválida")
        return normalizada

    @field_validator("nombre")
    @classmethod
    def _nombre_obligatorio(cls, v: str) -> str:
        """Rechaza nombre vacío."""
        if not v:
            raise ValueError("Nombre vacío")
        return v

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, v: str) -> str:
        """Rechaza correos que no cumplan el formato local@dominio.tld (regla "Correo electrónico válido")."""
        if not es_correo_valido(v):
            raise ValueError("Correo inválido")
        return v

    @field_validator("tipo_solicitud")
    @classmethod
    def _tipo_permitido(cls, v: str) -> str:
        """Rechaza tipo_solicitud fuera del catálogo permitido (regla "Tipo de solicitud permitido")."""
        if v not in TIPOS_VALIDOS:
            raise ValueError("Tipo de solicitud inválido")
        return v

    @field_validator("valor", mode="before")
    @classmethod
    def _valor_valido(cls, v) -> float:
        """Convierte valor a float y rechaza negativos (reglas "Valor numérico" y "Valor no negativo")."""
        numero = parsear_valor_numerico(v)
        if numero < 0:
            raise ValueError("Valor negativo")
        return numero

    @field_validator("estado", mode="before")
    @classmethod
    def _estado_normalizable(cls, v) -> str:
        """Normaliza estado a uno de los 4 valores estandarizados o rechaza (regla "Estado normalizable")."""
        normalizado = normalizar_estado(v)
        if normalizado is None:
            raise ValueError("Estado no válido")
        return normalizado


def validar_fila(fila: dict) -> tuple[list[str], SolicitudValidada | None]:
    """Valida una fila cruda del CSV.

    Args:
        fila: Dict con las claves de `COLUMNAS_ENTRADA` tal como vienen del CSV
            (sin normalizar).

    Returns:
        Tupla `(errores, solicitud)`. En éxito: `([], SolicitudValidada)`. En
        fallo: `(lista de mensajes de error, None)`, con un mensaje por cada
        campo inválido (Pydantic no se detiene en el primero).
    """
    try:
        solicitud = SolicitudValidada(
            id_solicitud = str(fila.get("id_solicitud") or "").strip(),
            fecha = fila.get("fecha", ""),
            nombre = str(fila.get("nombre") or "").strip(),
            correo = str(fila.get("correo") or "").strip(),
            tipo_solicitud = str(fila.get("tipo_solicitud") or "").strip(),
            valor = fila.get("valor", ""),
            estado = fila.get("estado", ""),
        )
    except ValidationError as exc:
        errores = [error["msg"].removeprefix("Value error, ") for error in exc.errors()]
        return errores, None
    return [], solicitud

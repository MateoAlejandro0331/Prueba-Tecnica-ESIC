# Prueba Técnica — Automatización de Solicitudes

Automatiza la lectura, validación, normalización, clasificación y envío de solicitudes
recibidas en un archivo CSV, reemplazando la revisión manual que hacía el área
administrativa. El detalle completo del problema está en
`Prueba Tecnica Instrucciones.pdf`.

## Requisitos previos

- Python 3.12+
- Dependencias en `requirements.txt`: `pandas` y `pydantic`. No se usa `requests`
  porque el envío al servicio externo (sección "Integración") se simula, sin llamadas
  HTTP reales.

## Instalación y configuración

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso básico

```bash
python main.py --input solicitudes_prueba_tecnica.csv --output resultados/
```

- `--input`: ruta al CSV de entrada. Debe tener las columnas `id_solicitud`, `fecha`,
  `nombre`, `correo`, `tipo_solicitud`, `valor`, `estado`.
- `--output`: carpeta donde se escriben los resultados (se crea si no existe).

El proceso termina con código de salida `0` si logró leer y procesar el archivo (con o
sin registros rechazados), o `1` si el CSV no existe o no tiene las columnas esperadas.

### Qué genera

Dentro de la carpeta indicada en `--output`:

| Archivo | Contenido |
|---|---|
| `solicitudes_validas.csv` | Únicamente los registros que pasaron todas las validaciones. |
| `solicitudes_con_errores.csv` | Los registros rechazados, con una columna adicional `errores` que lista **todas** las causas de rechazo (no solo la primera), separadas por `; `. |
| `resumen.json` | Fecha de ejecución, total de registros, válidos, con errores, cantidad de duplicados, conteo por tipo y por estado, y valor total de las solicitudes válidas. |
| `log_procesamiento.txt` | Registro de eventos de toda la ejecución: cada solicitud validada/rechazada y cada intento de envío al servicio externo. También se imprime en consola. |

## Estructura del proyecto

```
main.py                     Punto de entrada (CLI con --input / --output).
src/validaciones.py         Reglas de validación y normalización por campo (Pydantic).
src/procesamiento.py        Lectura del CSV, clasificación válidas/con errores, resumen y escritura de resultados.
src/integracion.py          Simulación del envío al servicio externo, con reintentos.
tests/                      Pruebas unitarias (validaciones, procesamiento, integración).
```

## Reglas de validación

### Mínimas del enunciado

| Regla | Condición |
|---|---|
| Identificador obligatorio | `id_solicitud` no puede estar vacío. |
| Identificador único | No puede haber dos filas con el mismo `id_solicitud`. |
| Correo válido | Debe tener forma `local@dominio.tld` (sin puntos consecutivos, sin empezar/terminar en punto). |
| Tipo de solicitud permitido | Debe ser exactamente `Compra`, `Reembolso`, `Acceso` o `Soporte`. |
| Valor numérico | El campo `valor` debe poder convertirse a número. |
| Valor no negativo | `valor >= 0`. |
| Estado normalizable | El texto de `estado` debe poder mapearse a uno de los 4 estados estandarizados (ver abajo). |

Cuando una fila tiene el mismo `id_solicitud` repetido, se le antepone el error
`"ID duplicado"` y además se validan sus demás campos, para que el CSV de errores
muestre todas las causas de rechazo de esa fila, no solo la duplicación.

### Reglas adicionales definidas para esta solución

Estas no están explícitamente en el Cuadro 4 del enunciado, pero se agregaron porque
mejoran la calidad del proceso frente a los datos reales del CSV de prueba:

- **Fecha normalizable**: `fecha` se acepta en los formatos `YYYY-MM-DD`, `YYYY/MM/DD`
  o `DD/MM/YYYY` y se reescribe siempre a `YYYY-MM-DD` en la salida. Si no coincide con
  ninguno (fecha vacía, formato distinto, día/mes inválido como `32/01/2026`), se
  rechaza con `"Fecha inválida"`.
- **Nombre obligatorio**: `nombre` no puede estar vacío (el enunciado no lo pide
  explícitamente, pero un registro sin nombre no es procesable en la práctica).
- **Distinción entre valor vacío y no numérico**: un `valor` vacío se reporta como
  `"Valor vacío"` y un valor con texto no convertible como `"Valor no numérico"`, en vez
  de agrupar ambos bajo un mismo mensaje genérico, para que quien revise el CSV de
  errores sepa exactamente qué corregir.

### Normalización de `estado`

Se ignoran mayúsculas/minúsculas, espacios repetidos y las variantes de género
(`completada`/`completado`, `rechazada`/`rechazado`) mencionadas en el enunciado:

| Entrada | Normalizado |
|---|---|
| `pendiente`, `PENDIENTE` | `Pendiente` |
| `en proceso`, `En Proceso` | `En proceso` |
| `completado`, `completada` | `Completado` |
| `rechazado`, `rechazada` | `Rechazado` |

Cualquier otro valor (`Aprobado`, `Finalizado`, `Desconocido`, typos como `Pendientee`
o `Completad0`, etc.) no es normalizable y la fila se rechaza con `"Estado no válido"`.

## Integración con el servicio externo (simulada)

Después de escribir los resultados, `src/integracion.py` "envía" únicamente las
solicitudes válidas a un servicio externo simulado (sin red real): cada intento tira un
número aleatorio para decidir el resultado —

- **75%** envío exitoso.
- **15%** error temporal (`ErrorTemporalAPI`) → se reintenta automáticamente, hasta
  2 intentos en total.
- **10%** error definitivo (`ErrorDefinitivoAPI`) → se registra el motivo y no se
  reintenta.

Todo intento (éxito, error temporal, error definitivo) queda registrado en
`log_procesamiento.txt`. El fallo de una solicitud nunca detiene el envío de las demás.

## Tests

`pytest` está en `requirements.txt`. Para correr toda la suite:

```bash
pytest
```

| Archivo | Cubre |
|---|---|
| `tests/test_validaciones.py` | Reglas de validación/normalización por campo y `validar_fila`, incluyendo que Pydantic colecciona **todos** los errores de una fila, no solo el primero. |
| `tests/test_procesamiento.py` | Lectura del CSV, detección de duplicados, clasificación válidas/con errores y construcción del resumen (incluida la semántica de `cantidad_duplicados`). |
| `tests/test_integracion.py` | Los 3 escenarios de `enviar_solicitud_simulada` (mockeando `random.random`) y la lógica de reintento de `enviar_con_reintento` / `enviar_solicitudes_validas`. |


## Notas

- `cantidad_duplicados` en `resumen.json` cuenta **identificadores distintos**
  duplicados (si `SOL-1015` aparece 3 veces, cuenta 1), no el total de filas afectadas.

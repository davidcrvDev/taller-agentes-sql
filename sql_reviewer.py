#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Taller sobre Agentes - Asignatura: Base de Datos
Politecnico Colombiano Jaime Isaza Cadavid
Docente: Manolo Pajaro Borras

Revisor y corrector de scripts SQL que combina dos capas:

  1. CAPA DETERMINISTA (sqlglot): detecta el dialecto (MySQL / PostgreSQL),
     valida la sintaxis, formatea y transpila entre dialectos.

  2. CAPA AGENTE (API de Gemini): cuando el parser encuentra un error real,
     le entrega al modelo el script junto con el mensaje exacto del error,
     recibe una propuesta de correccion y LA VUELVE A VALIDAR con sqlglot.
     Si sigue fallando, realimenta el nuevo error y reintenta (hasta 3 veces).

El ciclo "generar -> validar con una herramienta -> realimentar el error ->
reintentar" es lo que convierte esto en un AGENTE y no en una simple llamada
a una IA: el modelo nunca tiene la ultima palabra, la tiene el parser.

Si no se configura la API Key, el programa sigue siendo util: detecta el
dialecto, reporta los errores exactos de sintaxis y formatea o convierte
los scripts validos entre MySQL y PostgreSQL.

Uso:
    python sql_reviewer.py                              # captura por teclado
    python sql_reviewer.py archivo.sql                  # desde archivo
    python sql_reviewer.py archivo.sql postgres         # ademas transpila
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Literal, Optional, Tuple

import sqlglot
from sqlglot.errors import ParseError

# sqlglot avisa por consola cuando una sentencia no la soporta por completo y
# la conserva como texto opaco ('Command'). Es informativo, no es un error, y
# ensucia la salida del programa: se baja de nivel. Los errores de sintaxis
# reales (ParseError) se siguen capturando y mostrando igual.
logging.getLogger("sqlglot").setLevel(logging.ERROR)

# Carga opcional del archivo .env para que la API Key no tenga que definirse
# a mano en cada sesion de la terminal.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from google import genai

    GENAI_DISPONIBLE = True
except ImportError:
    GENAI_DISPONIBLE = False

Dialecto = Literal["mysql", "postgres"]

# Modelo usado por el agente corrector.
#
# El enunciado del taller proponia "gemini-2.5-flash", pero Google ya lo retiro
# para las cuentas nuevas: la API responde 404 "no longer available to new users".
# Se usa el modelo flash vigente. Si su clave no tiene acceso a este modelo,
# cambie esta constante por alguno de los alternativos; la logica del agente no
# depende del modelo, lo que sostiene la calidad es la revalidacion con sqlglot.
#
# Alternativas verificadas: "gemini-3.5-flash", "gemini-3.1-flash-lite".
# Para listar los modelos disponibles para su clave:
#     python -c "from google import genai; [print(m.name) for m in genai.Client().models.list()]"
MODELO_GEMINI = "gemini-3.6-flash"

CENTINELA_FIN = "FIN"


# Patrones caracteristicos para distinguir MySQL de PostgreSQL incluso con errores de sintaxis
PATRONES_MYSQL = [
    r"`[^`]+`",                      # Identificadores con backticks
    r"\bAUTO_INCREMENT\b",           # Autoincremento MySQL
    r"\bENGINE\s*=\s*\w+",           # ENGINE=InnoDB / MyISAM
    r"\bDEFAULT\s+CHARSET\b",        # DEFAULT CHARSET=utf8mb4
    r"\bUNSIGNED\b",                 # Enteros sin signo
    r"\b(TINYINT|MEDIUMINT|LONGTEXT|DATETIME)\b",
    r"\bIFNULL\s*\(",                # Funcion IFNULL
    r"\bLIMIT\s+\d+\s*,\s*\d+",      # LIMIT offset, count
    r"\bSHOW\s+(TABLES|DATABASES)\b",
    r"\bUSE\s+[`'\"]?\w+[`'\"]?\s*;",
]

PATRONES_POSTGRES = [
    r"\b(SMALLSERIAL|SERIAL|BIGSERIAL)\b",
    r"::[a-zA-Z_]\w*",               # Operador de cast ::tipo
    r"\bILIKE\b",                    # Busqueda insensible a mayusculas
    r"\bRETURNING\b",                # Clausula RETURNING
    r"\b(JSONB|BYTEA|TIMESTAMPTZ|UUID)\b",
    r"\bGENERATED\s+(ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY\b",
    r"\bON\s+CONFLICT\b",            # Upsert en PostgreSQL
    r"\bCREATE\s+EXTENSION\b",
    r"\$\$.*?\$\$",                  # Bloques dollar-quoted (PL/pgSQL)
    r"\bVARCHAR\s*\(\d+\)\s*\[\]",   # Arrays nativos
]


def detectar_dialecto(sql: str) -> Tuple[Dialecto, dict]:
    """
    Detecta si un script SQL pertenece a MySQL o PostgreSQL combinando
    heuristicas lexicas y pruebas de parseo con sqlglot.
    """
    puntos_mysql = sum(
        1 for patron in PATRONES_MYSQL if re.search(patron, sql, re.IGNORECASE | re.DOTALL)
    )
    puntos_postgres = sum(
        1 for patron in PATRONES_POSTGRES if re.search(patron, sql, re.IGNORECASE | re.DOTALL)
    )

    valido_mysql, _ = validar_sql(sql, "mysql")
    valido_postgres, _ = validar_sql(sql, "postgres")

    if valido_mysql and not valido_postgres:
        puntos_mysql += 2
    elif valido_postgres and not valido_mysql:
        puntos_postgres += 2

    detalles = {
        "puntos_mysql": puntos_mysql,
        "puntos_postgres": puntos_postgres,
        "valido_mysql": valido_mysql,
        "valido_postgres": valido_postgres,
    }

    dialecto: Dialecto = "postgres" if puntos_postgres > puntos_mysql else "mysql"
    return dialecto, detalles


def validar_sql(sql: str, dialecto: Dialecto) -> Tuple[bool, Optional[str]]:
    """Valida la sintaxis de un script SQL bajo un dialecto especifico."""
    try:
        sentencias = sqlglot.parse(sql, read=dialecto)
        if not sentencias or all(s is None for s in sentencias):
            return False, "El script esta vacio o no contiene sentencias SQL validas."
        return True, None
    except ParseError as e:
        return False, str(e)


def formatear_sql(sql: str, origen: Dialecto, destino: Optional[Dialecto] = None) -> str:
    """Formatea un script valido y, si se indica destino, lo transpila de dialecto."""
    destino_final = destino or origen
    sentencias = sqlglot.transpile(
        sql,
        read=origen,
        write=destino_final,
        pretty=True,
    )
    return ";\n\n".join(s.strip() for s in sentencias if s.strip()) + ";"


def limpiar_bloques_markdown(texto: str) -> str:
    """Extrae unicamente el codigo SQL si el modelo lo devuelve dentro de bloques ```sql."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", texto, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else texto.strip()


def corregir_con_ia(
    sql: str,
    dialecto: Dialecto,
    error_sintaxis: Optional[str],
    max_reintentos: int = 3,
) -> Tuple[str, bool, Optional[str]]:
    """
    Envia el script con errores a Gemini para repararlo y valida cada intento
    con sqlglot hasta obtener un script sintacticamente correcto.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not GENAI_DISPONIBLE or not api_key:
        return sql, False, "GEMINI_API_KEY no configurada o paquete google-genai no instalado."

    client = genai.Client(api_key=api_key)
    sql_actual = sql
    ultimo_error = error_sintaxis

    for intento in range(1, max_reintentos + 1):
        prompt = f"""Eres un DBA experto en {dialecto.upper()}.
Revisa y corrige el siguiente script SQL para que sea 100% valido en {dialecto.upper()}.
Manten intacta la logica original y corrige errores de sintaxis, tipos de datos incompatibles o palabras reservadas mal usadas.
Devuelve UNICAMENTE el codigo SQL corregido, sin explicaciones adicionales.

Error detectado por el parser:
{ultimo_error or 'Ninguno (revisar buenas practicas y compatibilidad de dialecto).'}

Script SQL:
```sql
{sql_actual}
```"""

        try:
            respuesta = client.models.generate_content(
                model=MODELO_GEMINI,
                contents=prompt,
            )
        except Exception as e:
            # Fallo de red, modelo saturado (503), cuota agotada o clave invalida.
            # No se aborta de inmediato: los errores 503 son temporales y suelen
            # resolverse al siguiente intento, asi que se consume un reintento.
            mensaje = f"Error al invocar la API de Gemini: {e}"
            print(f"  [Reintento {intento}/{max_reintentos}] {mensaje}")
            if intento == max_reintentos:
                return sql_actual, False, mensaje
            continue

        sql_candidato = limpiar_bloques_markdown(respuesta.text or "")

        es_valido, nuevo_error = validar_sql(sql_candidato, dialecto)
        if es_valido:
            return formatear_sql(sql_candidato, dialecto), True, None

        sql_actual = sql_candidato
        ultimo_error = nuevo_error
        print(f"  [Reintento {intento}/{max_reintentos}] Aun hay errores: {nuevo_error}")

    return sql_actual, False, ultimo_error


def procesar_sql(
    sql_original: str,
    nombre_origen: str,
    dialecto_destino: Optional[Dialecto] = None,
    ruta_salida: Optional[str] = None,
) -> None:
    """
    Flujo completo sobre un script ya cargado en memoria:
    deteccion -> validacion -> correccion con el agente -> guardado.

    Se usa tanto para los scripts leidos de un archivo como para los que el
    usuario captura por teclado.
    """
    if not sql_original.strip():
        print("Error: no se recibio ningun contenido SQL para analizar.")
        sys.exit(1)

    # 1. Detectar dialecto
    dialecto_detectado, detalles = detectar_dialecto(sql_original)
    print(f"Origen analizado  : {nombre_origen}")
    print(f"Dialecto detectado: {dialecto_detectado.upper()} {detalles}")

    # 2. Validar sintaxis
    es_valido, error = validar_sql(sql_original, dialecto_detectado)

    if es_valido:
        print("Estado inicial    : Sintaxis valida.")
        sql_final = formatear_sql(sql_original, dialecto_detectado, dialecto_destino)
        if dialecto_destino and dialecto_destino != dialecto_detectado:
            print(
                f"Conversion        : Transpilado de {dialecto_detectado.upper()} "
                f"a {dialecto_destino.upper()}."
            )
    else:
        print(f"Estado inicial    : Error de sintaxis detectado -> {error}")
        print("Accion            : Ejecutando agente corrector...")
        sql_corregido, exito, error_final = corregir_con_ia(
            sql_original, dialecto_detectado, error
        )
        if not exito:
            print(f"No fue posible corregir automaticamente el script: {error_final}")
            sys.exit(1)

        print("Estado final      : Script corregido y validado correctamente.")
        sql_final = (
            formatear_sql(sql_corregido, dialecto_detectado, dialecto_destino)
            if dialecto_destino
            else sql_corregido
        )

    # 3. Guardar resultado
    destino_archivo = Path(ruta_salida) if ruta_salida else Path("salida/script_corregido.sql")
    destino_archivo.parent.mkdir(parents=True, exist_ok=True)
    destino_archivo.write_text(sql_final, encoding="utf-8")
    print(f"Archivo guardado  : {destino_archivo}")

    print("-" * 70)
    print("RESULTADO:")
    print("-" * 70)
    print(sql_final)


def revisar_y_corregir_script(
    ruta_entrada: str,
    dialecto_destino: Optional[Dialecto] = None,
    ruta_salida: Optional[str] = None,
) -> None:
    """Flujo completo partiendo de un archivo .sql en disco."""
    archivo = Path(ruta_entrada)
    if not archivo.exists():
        print(f"Error: no se encontro el archivo '{ruta_entrada}'.")
        sys.exit(1)

    sql_original = archivo.read_text(encoding="utf-8")
    salida_final = ruta_salida or str(archivo.with_name(f"{archivo.stem}_corregido.sql"))

    procesar_sql(
        sql_original,
        nombre_origen=archivo.name,
        dialecto_destino=dialecto_destino,
        ruta_salida=salida_final,
    )


def capturar_sql_por_teclado() -> str:
    """
    Captura el script SQL escrito o pegado por el usuario en la terminal.

    Se usa una palabra centinela en lugar del fin de archivo (Ctrl+Z en Windows,
    Ctrl+D en Linux) porque es mas claro de usar y no se rompe al pegar un
    bloque de texto con varios saltos de linea.
    """
    print("=" * 70)
    print("CAPTURA DEL SCRIPT SQL POR TECLADO")
    print("=" * 70)
    print("Escriba o pegue su script SQL a continuacion.")
    print(f"Cuando termine, escriba una linea con la palabra {CENTINELA_FIN} y pulse Enter.")
    print("-" * 70)

    lineas: List[str] = []
    while True:
        try:
            linea = input()
        except EOFError:
            break
        if linea.strip().upper() == CENTINELA_FIN:
            break
        lineas.append(linea)

    print("-" * 70)
    return "\n".join(lineas)


def preguntar_dialecto_destino() -> Optional[Dialecto]:
    """Pregunta, tambien por teclado, si se desea convertir el script a otro dialecto."""
    try:
        respuesta = input(
            "Dialecto destino [mysql/postgres] (Enter = conservar el detectado): "
        ).strip().lower()
    except EOFError:
        return None

    if respuesta in ("mysql", "postgres"):
        return respuesta  # type: ignore[return-value]
    return None


def mostrar_ayuda() -> None:
    print(__doc__)


def configurar_salida_utf8() -> None:
    """Evita que los acentos se vean rotos al redirigir la salida en Windows."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main() -> None:
    configurar_salida_utf8()

    argumentos = sys.argv[1:]

    if argumentos and argumentos[0] in ("-h", "--help", "--ayuda"):
        mostrar_ayuda()
        return

    # Modo 2: archivo .sql pasado como argumento
    if argumentos:
        archivo_sql = argumentos[0]
        destino: Optional[Dialecto] = None
        if len(argumentos) >= 2 and argumentos[1].lower() in ("mysql", "postgres"):
            destino = argumentos[1].lower()  # type: ignore[assignment]

        revisar_y_corregir_script(archivo_sql, dialecto_destino=destino)
        return

    # Modo 1 (por defecto): captura del script por teclado
    sql_capturado = capturar_sql_por_teclado()
    destino_teclado = preguntar_dialecto_destino()

    procesar_sql(
        sql_capturado,
        nombre_origen="entrada por teclado",
        dialecto_destino=destino_teclado,
    )


if __name__ == "__main__":
    main()

# Taller sobre Agentes — Revisor y corrector de scripts SQL

**Asignatura:** Base de Datos
**Institución:** Politécnico Colombiano Jaime Isaza Cadavid
**Docente:** Manolo Pájaro Borrás

Programa en Python que **detecta el dialecto** de un script SQL (MySQL o PostgreSQL),
**valida su sintaxis**, lo **formatea**, lo **convierte entre dialectos** y —cuando
encuentra errores reales— los **corrige automáticamente mediante un agente** apoyado en
la API de Gemini.

---

## 1. Qué hace

| Capa | Herramienta | Responsabilidad |
|---|---|---|
| **Determinista** | `sqlglot` | Detectar dialecto, validar sintaxis, formatear, transpilar MySQL ↔ PostgreSQL |
| **Agente** | API de Gemini | Reparar errores de sintaxis reales y **revalidar** cada intento con `sqlglot` |

La capa determinista funciona **siempre**. La capa de agente es opcional: si no hay
`GEMINI_API_KEY` configurada, el programa igual detecta el dialecto, reporta el error
exacto de sintaxis y formatea o convierte los scripts válidos.

---

## 2. Instalación

```bash
pip install -r requirements.txt
```

Instala `sqlglot`, `google-genai` y `python-dotenv`.

### Configurar la API Key (opcional, para la autocorrección)

Obtenga una clave gratuita en <https://aistudio.google.com/apikey> y use **cualquiera**
de estas dos formas:

**Opción A — archivo `.env`** (recomendada, persiste entre sesiones):

```bash
copy .env.example .env      # Windows
cp .env.example .env        # Linux / macOS
```

Y edite el archivo reemplazando el valor:

```
GEMINI_API_KEY=AIza...su_clave_real
```

**Opción B — variable de entorno** (solo para la terminal actual):

```powershell
# Windows (PowerShell)
$env:GEMINI_API_KEY="tu_api_key_aqui"
```

```bash
# Linux / macOS
export GEMINI_API_KEY="tu_api_key_aqui"
```

> El archivo `.env` está excluido por `.gitignore` y **nunca** se sube al repositorio.

### Sobre el modelo

El enunciado del taller proponía `gemini-2.5-flash`, pero Google **ya lo retiró para las
cuentas nuevas**: la API responde `404 — This model is no longer available to new users`.
El programa usa `gemini-3.6-flash`, verificado como funcional. Si su clave no tiene
acceso a ese modelo, cambie la constante `MODELO_GEMINI` al inicio de `sql_reviewer.py`
(alternativas comprobadas: `gemini-3.5-flash`, `gemini-3.1-flash-lite`).

Para ver qué modelos admite su clave:

```bash
python -c "from google import genai; [print(m.name) for m in genai.Client().models.list()]"
```

---

## 3. Uso

### Modo 1 — Captura del script por teclado *(modo por defecto)*

```bash
python sql_reviewer.py
```

El programa pide que escriba o pegue el script SQL. Para terminar, escriba una línea
que diga únicamente `FIN` y pulse Enter. Luego pregunta, también por teclado, si desea
convertir el resultado a otro dialecto (Enter para conservar el detectado).

El resultado se guarda en `salida/script_corregido.sql`.

> Se usa la palabra centinela `FIN` en lugar del fin de archivo (`Ctrl+Z` en Windows,
> `Ctrl+D` en Linux) porque es más claro de usar y no se rompe al pegar un bloque de
> texto con varios saltos de línea.

### Modo 2 — Desde un archivo `.sql`

```bash
python sql_reviewer.py ejemplos/mysql_valido.sql
python sql_reviewer.py ejemplos/mysql_valido.sql postgres    # además transpila
```

El resultado se guarda junto al original como `<nombre>_corregido.sql`.

---

## 4. Cómo funciona internamente

### 4.1 Detección del dialecto — `detectar_dialecto()`

Combina **dos señales independientes**, lo cual es clave porque un script con errores
no se puede parsear y aun así hay que saber de qué motor es:

1. **Heurística léxica.** Dos listas de expresiones regulares con rasgos exclusivos de
   cada motor. Funcionan aunque el SQL esté roto, porque solo miran el texto:

   | MySQL | PostgreSQL |
   |---|---|
   | `` `identificadores` `` con backticks | `SERIAL` / `BIGSERIAL` |
   | `AUTO_INCREMENT` | operador de cast `::tipo` |
   | `ENGINE=InnoDB` | `ILIKE` |
   | `DEFAULT CHARSET` | `RETURNING` |
   | `UNSIGNED` | `JSONB`, `BYTEA`, `TIMESTAMPTZ`, `UUID` |
   | `TINYINT`, `LONGTEXT`, `DATETIME` | `ON CONFLICT` |
   | `IFNULL(...)` | `CREATE EXTENSION` |
   | `LIMIT offset, count` | bloques `$$ ... $$` |

   Cada patrón encontrado suma **1 punto** a su dialecto.

2. **Prueba de parseo.** Se intenta parsear el script con `sqlglot` bajo **ambos**
   dialectos. Si parsea en uno y falla en el otro, el ganador recibe **2 puntos** extra.
   Es un desempate fuerte: no es una suposición sobre el texto, es el parser diciendo
   "esto sí lo entiendo".

Gana el puntaje más alto. En caso de empate se asume MySQL.

### 4.2 Validación — `validar_sql()`

Llama a `sqlglot.parse(sql, read=dialecto)` dentro de un `try/except ParseError`.
`sqlglot` construye un **AST** (árbol de sintaxis abstracta) a partir del texto; si no
puede, lanza `ParseError` con el **mensaje, la línea y la columna exactos** del fallo.
Ese mensaje no se descarta: es justamente lo que después se le entrega al modelo.

### 4.3 Formateo y transpilación — `formatear_sql()`

`sqlglot.transpile(sql, read=origen, write=destino, pretty=True)` recorre el AST y lo
vuelve a escribir en el dialecto destino. Por eso un `LIMIT 0, 5` de MySQL se convierte
en `LIMIT 5 OFFSET 0` de PostgreSQL, y los backticks en comillas dobles: no es un
reemplazo de texto, es una **reescritura del árbol**.

### 4.4 El agente corrector — `corregir_con_ia()`

Aquí está el núcleo del taller. El ciclo es:

```
error del parser  ->  prompt a Gemini  ->  respuesta  ->  limpiar bloques markdown
                                                            |
                      <-- realimentar el NUEVO error --  validar con sqlglot
                                                            |
                                                      ¿válido? -> devolver formateado
```

Cuatro detalles que lo convierten en un **agente** y no en una simple llamada a una IA:

1. **El prompt incluye el error exacto del parser**, no solo el script. El modelo
   recibe evidencia concreta de qué falló y dónde.
2. **La respuesta del modelo no se acepta nunca por la cara.** Se vuelve a validar con
   `sqlglot`. La última palabra la tiene el parser, no el modelo.
3. **Si sigue fallando, se realimenta el nuevo error y se reintenta** (hasta 3 veces).
   Cada iteración parte del mejor intento anterior, no del original. El mismo ciclo
   absorbe los fallos temporales de la API (por ejemplo un `503` por saturación del
   modelo): consumen un reintento en lugar de abortar la ejecución.
4. **`limpiar_bloques_markdown()`** extrae el SQL de los bloques ` ```sql ` que los
   modelos tienden a añadir, porque esa envoltura rompería al parser.

Ese lazo cerrado *modelo → herramienta de verificación → modelo* es la definición
práctica de un agente: el LLM propone, la herramienta determinista dispone.

### 4.5 Degradación sin API Key

`corregir_con_ia()` revisa `GENAI_DISPONIBLE` (import exitoso de `google-genai`) y la
presencia de `GEMINI_API_KEY`. Si falta cualquiera de los dos, retorna sin intentar la
llamada y el programa informa el motivo, conservando intacta toda la capa determinista.

---

## 5. Casos de prueba incluidos

| Archivo | Escenario | Resultado esperado |
|---|---|---|
| `ejemplos/mysql_valido.sql` | MySQL correcto | Detecta MYSQL (10 a 0), formatea |
| `ejemplos/postgres_valido.sql` | PostgreSQL correcto | Detecta POSTGRES (0 a 8), formatea |
| `ejemplos/mysql_con_errores.sql` | MySQL con 3 errores | Detecta MYSQL (6 a 0) pese a no parsear, **dispara el agente** |
| `ejemplos/postgres_con_errores.sql` | PostgreSQL con 3 errores | Detecta POSTGRES (0 a 3) pese a no parsear, **dispara el agente** |

Los errores sembrados son: coma faltante entre columnas, paréntesis sin cerrar en el
tipo `DECIMAL`/`NUMERIC`, y una palabra reservada mal escrita (`WHRE` / `VALUE`).

---

## 6. Limitaciones conocidas

Vale la pena conocerlas porque son propias de la herramienta, no del programa:

- **La transpilación de DDL no es perfecta.** Al convertir MySQL → PostgreSQL,
  `sqlglot` arrastra cláusulas que no existen en el destino (`ENGINE=InnoDB`,
  `DEFAULT CHARACTER SET`) y traduce `INT UNSIGNED` como `UINT`, que PostgreSQL no
  reconoce. La transpilación es confiable para DML (`SELECT`, `INSERT`, `UPDATE`) y
  aproximada para DDL.
- **`sqlglot` es permisivo.** Cuando no soporta del todo una sentencia, en lugar de
  fallar la conserva como texto opaco (`Command`). Esos avisos se silencian en el
  programa para no ensuciar la salida, pero los `ParseError` reales sí se muestran.
- **La validación es sintáctica, no semántica.** `sqlglot` no se conecta a ninguna base
  de datos: no verifica que las tablas existan ni que los tipos sean coherentes.

---

## 7. Estructura del proyecto

```
taller-agenteBD2/
├── sql_reviewer.py              # Programa principal
├── requirements.txt
├── .env.example                 # Plantilla de configuración (sin claves reales)
├── .gitignore
├── INTEGRANTES.md
├── ejemplos/
│   ├── mysql_valido.sql
│   ├── postgres_valido.sql
│   ├── mysql_con_errores.sql
│   └── postgres_con_errores.sql
├── docs/
│   ├── diagrama_flujo.md        # Diagrama del ciclo del agente
│   └── guion_video.md           # Guion para la sustentación oral
└── salida/                      # Resultados generados (ignorado por git)
```

# Guion para la sustentación en video

**Duración objetivo:** 8 a 10 minutos.
**Lo que se evalúa:** que el programa funcione **y** que usted explique **cómo funciona
internamente**. La explicación pesa más que la demo.

### Antes de grabar — lista de 6 chequeos

1. Terminal abierta en `C:\Users\USUARIO\taller-agenteBD2`.
2. Letra de la terminal grande (en Windows Terminal: `Ctrl` + rueda del ratón).
3. Archivo `.env` con la API Key ya configurada (**no lo muestre en pantalla**).
4. `python sql_reviewer.py ejemplos\mysql_con_errores.sql` probado una vez, para
   confirmar que hay internet y cuota disponible.
5. Abiertos en pestañas del editor: `sql_reviewer.py`, `docs/diagrama_flujo.md`.
6. Cierre Slack, WhatsApp y notificaciones.

---

## Minuto 0:00 – 0:45 · Presentación

> «Buenas, soy **[su nombre]**, del grupo conformado por **[integrantes]**, para el
> taller sobre agentes de la asignatura Base de Datos.
>
> Lo que construimos es un **revisor y corrector de scripts SQL**. Recibe un script,
> detecta automáticamente si es MySQL o PostgreSQL, valida su sintaxis, y si encuentra
> errores los corrige usando un agente apoyado en la API de Gemini. Además puede
> convertir un script de un motor al otro.
>
> La idea central, y es lo que quiero explicar hoy, es que esto **no es simplemente
> mandarle el código a una IA**. Hay dos capas: una determinista con la librería
> `sqlglot`, y una capa de agente. Y la capa determinista es la que manda.»

---

## Minuto 0:45 – 2:00 · El diagrama (abra `docs/diagrama_flujo.md`)

Muestre el **diagrama 1** y recórralo con el cursor:

> «El programa puede recibir el SQL de dos formas: **capturado por teclado**, que es el
> modo por defecto, o desde un archivo `.sql`. Ambas entradas caen en la misma función
> `procesar_sql`.
>
> De ahí el flujo es siempre el mismo: **detectar dialecto**, **validar sintaxis**, y
> ahí se bifurca. Si el script es válido, se formatea y, si uno lo pidió, se transpila
> al otro motor. Si **no** es válido, entra el agente corrector —la caja naranja—.
>
> Lo azul es `sqlglot`, puro determinismo. Lo naranja es el modelo. Fíjense que el
> agente, cuando termina, **vuelve a entrar al flujo azul**. Nunca se sale del control
> de la herramienta.»

---

## Minuto 2:00 – 3:30 · Demo 1: detección de dialecto

```powershell
python sql_reviewer.py ejemplos\mysql_valido.sql
```

Señale la línea del dialecto detectado:

> «Detectó MySQL con **10 puntos contra 0**. Esa puntuación sale de combinar **dos
> señales independientes**.
>
> La primera son **patrones léxicos**: expresiones regulares que buscan rasgos
> exclusivos de cada motor. Aquí encontró backticks, `AUTO_INCREMENT`, `ENGINE=InnoDB`,
> `UNSIGNED`, `DATETIME`, `IFNULL`, `LIMIT` con offset y coma. Cada uno suma un punto.
>
> La segunda señal es más fuerte: el programa **intenta parsear el script con los dos
> dialectos**. Vean que dice `valido_mysql: True` y `valido_postgres: False`. Como
> parsea en uno y falla en el otro, el ganador se lleva **2 puntos extra**. No es una
> suposición sobre el texto: es el parser diciendo "esto sí lo entiendo".»

Ahora el mismo archivo, pero convertido:

```powershell
python sql_reviewer.py ejemplos\mysql_valido.sql postgres
```

> «Mismo script, ahora transpilado a PostgreSQL. Los backticks pasaron a comillas
> dobles y el `DATETIME` de MySQL se volvió `TIMESTAMP`.
>
> Y esto es importante: **no es un reemplazo de texto**. `sqlglot` construye un **AST**,
> un árbol de sintaxis abstracta, lo recorre, y lo vuelve a escribir con las reglas del
> motor destino. Por eso entiende equivalencias que un buscar-y-reemplazar jamás
> pillaría, como que el `LIMIT 0, 10` de MySQL equivale a `LIMIT 10 OFFSET 0`.»

---

## Minuto 3:30 – 6:00 · Demo 2: el agente *(la parte importante)*

Primero muestre el archivo roto:

```powershell
type ejemplos\mysql_con_errores.sql
```

> «Este script tiene tres errores sembrados a propósito: falta una coma entre dos
> columnas, falta cerrar el paréntesis del `DECIMAL`, y `WHERE` está mal escrito como
> `WHRE`.»

Ejecútelo:

```powershell
python sql_reviewer.py ejemplos\mysql_con_errores.sql
```

**Pause en la línea del dialecto** y diga:

> «Primero, algo que vale la pena notar: **detectó MySQL con 6 a 0 aunque el script no
> parsea en ningún dialecto** —vean que `valido_mysql` y `valido_postgres` son los dos
> `False`—. Como la prueba de parseo queda neutralizada, **los patrones léxicos son los
> que salvan la detección**. Por eso están las dos señales y no solo una.»

**Pause en la línea del error** y diga:

> «Y aquí está la clave de todo. `sqlglot` no dice "hay un error": dice **qué** error,
> en **qué línea** y en **qué columna**, y hasta subraya el fragmento.
>
> Ese mensaje **no se descarta**. Se le entrega al modelo dentro del prompt.»

Ahora abra `sql_reviewer.py` en la función `corregir_con_ia` y muestre el prompt:

> «Miren el prompt: le damos un rol —"eres un DBA experto en MySQL"—, le decimos que
> mantenga la lógica intacta, que devuelva únicamente SQL... y le pasamos **el error
> exacto del parser**. El modelo no está adivinando qué está mal: tiene la evidencia.»

Baje a la validación y marque el ciclo `for`:

> «Y esto es lo que hace que sea un **agente** y no un chatbot. Son cuatro cosas:
>
> **Uno:** la respuesta pasa por `limpiar_bloques_markdown`, porque los modelos tienden
> a envolver el código en bloques con triple comilla y eso rompería al parser.
>
> **Dos**, y es lo más importante: la respuesta del modelo **se vuelve a validar con
> `sqlglot`**. Nunca se acepta por la cara. La última palabra la tiene el parser, no el
> modelo.
>
> **Tres:** si el resultado sigue fallando, se toma **el nuevo error** y se le devuelve
> al modelo. Reintenta hasta tres veces, y cada intento parte del mejor candidato
> anterior, no del original.
>
> **Cuatro:** si agota los tres intentos, falla de forma honesta y lo reporta.
>
> Ese lazo cerrado —generar, verificar con una herramienta, realimentar el error,
> reintentar— es la definición práctica de un agente. **El modelo propone, la
> herramienta determinista dispone.**»

Muestre el resultado corregido en pantalla.

---

## Minuto 6:00 – 7:30 · Demo 3: captura por teclado *(requisito de la entrega)*

```powershell
python sql_reviewer.py
```

Escriba o pegue, por ejemplo:

```sql
SELECT id, nombre FROM `usuarios` WHERE activo = 1 LIMIT 0, 5;
```

Luego escriba `FIN`, Enter, y al preguntar el dialecto escriba `postgres`.

> «Este es el modo por defecto: **captura del script por teclado**. Se termina
> escribiendo `FIN` en una línea.
>
> Usamos una palabra centinela en vez del fin de archivo —`Ctrl+Z` en Windows— porque
> es más claro y no se rompe al pegar un bloque con varios saltos de línea.
>
> Vean que detectó MySQL por los backticks y el `LIMIT` con coma, y al convertirlo a
> PostgreSQL ese `LIMIT 0, 5` se volvió `LIMIT 5 OFFSET 0`. El resultado también queda
> guardado en `salida/script_corregido.sql`.»

---

## Minuto 7:30 – 8:30 · Degradación sin API Key

```powershell
$env:GEMINI_API_KEY=""
python sql_reviewer.py ejemplos\postgres_valido.sql
python sql_reviewer.py ejemplos\postgres_con_errores.sql
```

> «Una última cosa que pedía el taller: **sin API Key el programa sigue siendo útil**.
>
> Con un script válido hace todo su trabajo: detecta PostgreSQL —aquí 8 a 0 por el
> `BIGSERIAL`, el `JSONB`, el `TIMESTAMPTZ`, el `ILIKE`, el `ON CONFLICT`, el
> `RETURNING`— y lo formatea.
>
> Con un script roto detecta el dialecto, **reporta el error exacto**, y al llegar al
> agente informa con claridad que no hay clave configurada, en vez de reventar. Eso se
> maneja con la bandera `GENAI_DISPONIBLE`, que se activa en un `try/except ImportError`
> al inicio del archivo, más la verificación de la variable de entorno.»

Restaure la clave antes de seguir: `$env:GEMINI_API_KEY="su_clave"`.

---

## Minuto 8:30 – 9:30 · Cierre

> «Para cerrar, lo esencial del taller en tres ideas:
>
> **Primera:** combinar un LLM con una herramienta determinista es mucho más confiable
> que usar cualquiera de los dos por separado. `sqlglot` solo detecta errores pero no
> los arregla; el modelo solo propone pero puede equivocarse. Juntos, uno propone y el
> otro verifica.
>
> **Segunda:** un agente se define por el **lazo de realimentación**, no por usar una
> IA. Lo que hace agente a este programa es que el resultado del modelo se verifica y,
> si falla, el error vuelve a entrar como entrada.
>
> **Tercera**, y es honestidad sobre los límites: la validación es **sintáctica, no
> semántica**. `sqlglot` no se conecta a ninguna base de datos, así que no verifica que
> las tablas existan ni que los tipos tengan sentido. Y la transpilación de DDL es
> aproximada: al pasar de MySQL a PostgreSQL arrastra cláusulas como `ENGINE=InnoDB`
> que no existen en el destino. Para DML —`SELECT`, `INSERT`, `UPDATE`— sí es confiable.
>
> Muchas gracias.»

---

## Si el docente pregunta

**«¿Por qué esto es un agente y no una llamada a una IA?»**
Por el lazo cerrado: la salida del modelo se verifica con una herramienta externa
(`sqlglot`) y, si falla, el error se realimenta como nueva entrada hasta 3 veces. Un
chatbot responde una vez y se acabó; este programa itera hasta que un verificador
independiente aprueba el resultado.

**«¿Qué es un AST?»**
Árbol de sintaxis abstracta: la representación estructurada del código. `sqlglot` lee el
texto del SQL y construye un árbol donde cada nodo es una construcción del lenguaje
(un `SELECT`, una columna, una condición). Transpilar es recorrer ese árbol y volver a
escribirlo con las reglas de otro motor.

**«¿Por qué dos métodos para detectar el dialecto?»**
Porque se complementan justo donde el otro falla. La prueba de parseo es la señal fuerte,
pero **se cae cuando el script tiene errores** (no parsea en ninguno). Ahí los patrones
léxicos son lo único que queda. Se ve en `mysql_con_errores.sql`: 6 a 0 con ambos
`valido_*` en `False`.

**«¿Qué pasa si el modelo devuelve algo peor?»**
No importa, porque no se acepta: `validar_sql` lo rechaza y el ciclo reintenta con el
nuevo error. Si tras 3 intentos no hay un script válido, el programa falla
explícitamente y muestra el último error en lugar de entregar algo roto.

**«¿Por qué `max_reintentos = 3`?»**
Es un tope de seguridad: cada intento cuesta una llamada a la API. En la práctica los
errores de sintaxis típicos se resuelven en el primero; el límite evita un ciclo infinito
y un gasto innecesario si el script está irrecuperablemente dañado.

**«¿Se puede cambiar de modelo?»**
Sí, está en la constante `MODELO_GEMINI` al inicio del archivo. La lógica del agente es
independiente del modelo: lo que sostiene la calidad es el verificador, no el proveedor.

**«¿Por qué no usó el `gemini-2.5-flash` del enunciado?»**
Porque Google ya lo retiró para cuentas nuevas: al llamarlo, la API responde
`404 — This model is no longer available to new users`. Lo verificamos listando los
modelos disponibles para nuestra clave y usamos `gemini-3.6-flash`, que sí responde.
Es un cambio de una línea precisamente porque el agente no depende del modelo.

**«¿Y si se cae la API en mitad de la corrección?»**
Está contemplado. Durante las pruebas nos respondió un `503` por saturación del modelo.
El manejo de excepciones no aborta: registra el fallo, consume un reintento y vuelve a
intentar, porque esos errores son temporales. Solo si se agotan los tres intentos
reporta el fallo.

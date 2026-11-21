# Diagrama de flujo — Ciclo del agente corrector

> Para mostrar en la sustentación. GitHub renderiza estos diagramas automáticamente:
> basta con abrir este archivo en el repositorio y compartir pantalla.

## 1. Flujo general del programa

```mermaid
flowchart TD
    A[Inicio] --> B{¿Hay argumentos<br/>en la línea de comandos?}
    B -->|No| C[capturar_sql_por_teclado<br/>centinela FIN]
    B -->|Sí| D[revisar_y_corregir_script<br/>lee el archivo .sql]
    C --> E[procesar_sql]
    D --> E

    E --> F[detectar_dialecto]
    F --> G[validar_sql]
    G --> H{¿Sintaxis<br/>válida?}

    H -->|Sí| I[formatear_sql<br/>pretty + transpilación]
    H -->|No| J[corregir_con_ia<br/>AGENTE]

    J --> K{¿Logró<br/>corregirlo?}
    K -->|Sí| I
    K -->|No| L[Informa el motivo<br/>y termina]

    I --> M[Guardar resultado<br/>e imprimir en pantalla]

    style J fill:#ffe0b2,stroke:#e65100,stroke-width:3px
    style F fill:#e1f5fe,stroke:#01579b
    style G fill:#e1f5fe,stroke:#01579b
    style I fill:#e1f5fe,stroke:#01579b
```

Azul = capa determinista (`sqlglot`). Naranja = capa de agente (Gemini).

---

## 2. Detección del dialecto — dos señales independientes

```mermaid
flowchart LR
    A[Script SQL<br/>aunque esté roto] --> B[Señal 1:<br/>patrones léxicos<br/>regex]
    A --> C[Señal 2:<br/>intento de parseo<br/>en ambos dialectos]

    B --> D["backticks, AUTO_INCREMENT,<br/>ENGINE=, UNSIGNED...<br/>+1 punto a MySQL c/u"]
    B --> E["SERIAL, ::cast, ILIKE,<br/>JSONB, ON CONFLICT...<br/>+1 punto a PostgreSQL c/u"]

    C --> F{"¿Parsea en uno<br/>y falla en el otro?"}
    F -->|Sí| G[+2 puntos<br/>al que sí parsea]
    F -->|No| H[Sin desempate]

    D --> I[Suma de puntos]
    E --> I
    G --> I
    H --> I
    I --> J{"¿Quién tiene<br/>más puntos?"}
    J --> K[Dialecto detectado<br/>empate = MySQL]
```

**Por qué dos señales:** un script con errores de sintaxis **no parsea en ningún
dialecto**, así que la señal 2 queda neutralizada y solo los patrones léxicos pueden
identificarlo. Es exactamente el caso de `mysql_con_errores.sql`, que se detecta como
MySQL con 6 puntos a 0 pese a que `valido_mysql` y `valido_postgres` son ambos `False`.

---

## 3. El lazo del agente — lo que hay que explicar

```mermaid
flowchart TD
    A[ParseError de sqlglot<br/>mensaje + línea + columna] --> B[Construir el prompt:<br/>rol de DBA + dialecto +<br/>ERROR EXACTO + script]
    B --> C[Gemini<br/>genera una corrección]
    C --> D[limpiar_bloques_markdown<br/>quita las comillas ```sql]
    D --> E[validar_sql<br/>REVALIDACIÓN con sqlglot]
    E --> F{"¿Válido<br/>ahora?"}
    F -->|Sí| G[formatear_sql<br/>y devolver con éxito]
    F -->|No, e intentos < 3| H[Realimentar el NUEVO error<br/>sql_actual = candidato]
    H --> B
    F -->|No, agotó 3 intentos| I[Devolver fallo<br/>con el último error]

    style C fill:#ffe0b2,stroke:#e65100,stroke-width:3px
    style E fill:#c8e6c9,stroke:#1b5e20,stroke-width:3px
```

### La idea en una frase

> **El modelo propone, la herramienta determinista dispone.**

La respuesta de Gemini **nunca** se acepta sin verificar. Cada propuesta vuelve a pasar
por `sqlglot`, y si falla, el nuevo error se le devuelve al modelo para que reintente.
Ese lazo cerrado `generar → verificar → realimentar → reintentar` es lo que convierte el
programa en un **agente**, y no en una simple llamada a una IA.

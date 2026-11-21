-- ============================================================
-- Caso 4: script PostgreSQL CON ERRORES DE SINTAXIS
-- Demuestra: el mismo ciclo del agente corrector, pero en el
--            otro dialecto.
--
-- Errores intencionales:
--   1. Falta la coma despues de nombre VARCHAR(150) NOT NULL
--   2. "VALUE" deberia ser "VALUES"
--   3. Falta cerrar el parentesis del VALUES
-- ============================================================

CREATE TABLE empleados (
  id BIGSERIAL PRIMARY KEY,
  nombre VARCHAR(150) NOT NULL
  cargo VARCHAR(80) NOT NULL,
  salario NUMERIC(12, 2 NOT NULL,
  datos JSONB NOT NULL DEFAULT '{}',
  ingreso TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO empleados (nombre, cargo, salario)
VALUE ('Ana Gomez', 'Analista', 4500000.00
RETURNING id;

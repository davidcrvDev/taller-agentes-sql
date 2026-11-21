-- ============================================================
-- Caso 2: script PostgreSQL VALIDO
-- Demuestra: deteccion de dialecto por patrones lexicos
--            (SERIAL, JSONB, TIMESTAMPTZ, ILIKE, RETURNING,
--             ON CONFLICT, operador de cast ::tipo)
--            + formateo y transpilacion a MySQL.
-- ============================================================

CREATE TABLE productos (
  id BIGSERIAL PRIMARY KEY,
  sku VARCHAR(40) NOT NULL UNIQUE,
  nombre VARCHAR(150) NOT NULL,
  precio NUMERIC(12, 2) NOT NULL,
  atributos JSONB NOT NULL DEFAULT '{}',
  creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE inventario (
  id BIGSERIAL PRIMARY KEY,
  producto_id BIGINT NOT NULL REFERENCES productos (id),
  bodega VARCHAR(60) NOT NULL,
  cantidad INTEGER NOT NULL DEFAULT 0
);

INSERT INTO productos (sku, nombre, precio, atributos)
VALUES ('SKU-001', 'Teclado mecanico', 189900.00, '{"color": "negro"}'::JSONB)
ON CONFLICT (sku) DO UPDATE SET precio = EXCLUDED.precio
RETURNING id;

SELECT
  p.nombre,
  p.precio::NUMERIC(12, 2) AS precio_final,
  SUM(i.cantidad) AS stock_total
FROM productos AS p
JOIN inventario AS i ON i.producto_id = p.id
WHERE p.nombre ILIKE '%teclado%'
GROUP BY p.id, p.nombre, p.precio
ORDER BY stock_total DESC;

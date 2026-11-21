-- ============================================================
-- Caso 1: script MySQL VALIDO
-- Demuestra: deteccion de dialecto por patrones lexicos
--            (backticks, AUTO_INCREMENT, ENGINE, CHARSET,
--             UNSIGNED, DATETIME, IFNULL, LIMIT offset,count)
--            + formateo y transpilacion a PostgreSQL.
-- ============================================================

CREATE TABLE `clientes` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(120) NOT NULL,
  `correo` VARCHAR(180) NOT NULL,
  `telefono` VARCHAR(20),
  `activo` TINYINT(1) NOT NULL DEFAULT 1,
  `creado_en` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_clientes_correo` (`correo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `pedidos` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `cliente_id` INT UNSIGNED NOT NULL,
  `total` DECIMAL(12, 2) NOT NULL,
  `creado_en` DATETIME NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_pedidos_cliente` FOREIGN KEY (`cliente_id`) REFERENCES `clientes` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT
  c.`nombre`,
  IFNULL(SUM(p.`total`), 0) AS total_comprado
FROM `clientes` AS c
LEFT JOIN `pedidos` AS p ON p.`cliente_id` = c.`id`
WHERE c.`activo` = 1
GROUP BY c.`id`, c.`nombre`
ORDER BY total_comprado DESC
LIMIT 0, 10;

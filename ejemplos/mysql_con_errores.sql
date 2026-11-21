-- ============================================================
-- Caso 3: script MySQL CON ERRORES DE SINTAXIS
-- Demuestra: el dialecto se sigue detectando aunque el script
--            no parsee (gracias a los patrones lexicos) y se
--            DISPARA EL AGENTE CORRECTOR.
--
-- Errores intencionales:
--   1. Falta la coma despues de `nombre` VARCHAR(120) NOT NULL
--   2. Falta cerrar el parentesis de DECIMAL(12, 2
--   3. "WHRE" esta mal escrito (deberia ser WHERE)
-- ============================================================

CREATE TABLE `facturas` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(120) NOT NULL
  `nit` VARCHAR(30) NOT NULL,
  `total` DECIMAL(12, 2 NOT NULL,
  `emitida_en` DATETIME NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT `nombre`, `total`
FROM `facturas`
WHRE `total` > 100000
ORDER BY `total` DESC;

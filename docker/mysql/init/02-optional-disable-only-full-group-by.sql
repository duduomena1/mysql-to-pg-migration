-- Script opcional para desabilitar ONLY_FULL_GROUP_BY no MySQL
-- NOTA: As queries já foram corrigidas para serem compatíveis com ONLY_FULL_GROUP_BY
-- Este script é fornecido apenas como alternativa, caso você prefira essa abordagem

-- Ver o sql_mode atual
SELECT @@sql_mode;

-- Desabilitar ONLY_FULL_GROUP_BY temporariamente (apenas para a sessão atual)
-- SET sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));

-- Para desabilitar permanentemente, você pode adicionar ao my.cnf:
-- [mysqld]
-- sql_mode=STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION

-- Entretanto, é recomendado manter ONLY_FULL_GROUP_BY ativado, pois:
-- 1. Está no padrão SQL
-- 2. Previne queries ambíguas
-- 3. As queries do projeto já foram corrigidas para serem compatíveis

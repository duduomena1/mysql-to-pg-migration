-- Script de inicialização para PostgreSQL
-- Este script cria apenas o schema, pois os dados virão da migração do MySQL

-- Nota: Este arquivo é opcional. O banco PostgreSQL será populado
-- pela ferramenta de migração a partir dos dados do MySQL.

-- Se necessário, você pode criar schemas adicionais aqui:
-- CREATE SCHEMA IF NOT EXISTS test;

-- Garantir que as extensões necessárias estejam disponíveis
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configurações recomendadas para melhor performance durante migração
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Nota: Estas configurações requerem restart do PostgreSQL para terem efeito
-- Elas são otimizadas para o processo de migração

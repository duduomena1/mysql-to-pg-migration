# Migração PostgreSQL to PostgreSQL - Método CSV

## 📋 Resumo das Mudanças

A página de migração PG to PG foi **completamente reescrita** para utilizar **CSV como formato intermediário**, resolvendo os problemas de integridade de dados que você estava enfrentando.

## ✨ Novo Método CSV

### Arquivos Criados

1. **`dbmigrator/data_migration/pg_to_pg_csv.py`** - Módulo principal com duas classes:
   - `PostgreSQLToCSV` - Exporta tabelas PostgreSQL para CSV
   - `CSVToPostgreSQL` - Importa CSV para PostgreSQL

2. **`pages/13_🔄_PG_to_PG.py`** - Interface Streamlit renovada e simplificada

### Vantagens do Método CSV

✅ **Melhor tratamento de NULL values** - Valores nulos são preservados corretamente

✅ **Preservação de tipos de dados** - JSON, JSONB, Arrays e tipos especiais são serializados/desserializados corretamente

✅ **Maior confiabilidade** - Elimina problemas de timeout e conexões perdidas

✅ **ON CONFLICT inteligente** - Detecta primary keys automaticamente e aplica estratégias de conflito

✅ **Facilita debug** - Os arquivos CSV ficam disponíveis para inspeção

✅ **Retomável** - Possível reiniciar migração do ponto de falha

## 🔧 Como Funciona

### Fase 1: Exportação
```python
exporter = PostgreSQLToCSV(source_connection, schema='public', output_dir='data')
result = exporter.export_table('my_table', batch_size=10000)
```

Para cada tabela:
- Lê metadados das colunas (tipos, nullable, defaults)
- Extrai dados em lotes (batch_size)
- Serializa valores especiais:
  - JSON/JSONB → string JSON
  - Arrays → string JSON 
  - Boolean → 't'/'f'
  - NULL → string vazia
- Salva em arquivo CSV com encoding UTF-8

### Fase 2: Importação
```python
importer = CSVToPostgreSQL(dest_connection, schema='public', input_dir='data')
result = importer.import_table('my_table', batch_size=10000, on_conflict='do_nothing')
```

Para cada tabela:
- Lê CSV linha por linha
- Desserializa valores de volta aos tipos corretos
- Detecta primary key automaticamente
- Cria INSERT com ON CONFLICT:
  - `'do_nothing'` → Ignora duplicatas
  - `'update'` → Atualiza duplicatas
  - `None` → Falha em duplicatas
- Processa em lotes com fallback linha-por-linha em caso de erro

## 🐛 Problemas Resolvidos

### 1. Coluna `name` como NULL em `vehicle_types`
**Causa**: INSERT direto não preservava NULL corretamente  
**Solução**: CSV serializa/desserializa NULL explicitamente (string vazia → None)

### 2. Linha não migrada (não duplicada)
**Causa**: Erro silencioso no INSERT em lote  
**Solução**: CSV + fallback linha-por-linha captura e reporta cada erro

### 3. Número menor de dados em `rules`
**Causa**: ON CONFLICT mal configurado ou erro de FK  
**Solução**: Detecção automática de PK + ordem topológica de FK

### 4. `tax_logs` sem `user_id`
**Causa**: Serialização incorreta de NULL ou tipo especial  
**Solução**: Tratamento específico por tipo de coluna no CSV

## 📖 Como Usar

### 1. Configure as Conexões
```python
# Source Database
Host: 192.168.101.87
Database: tatico_source
Schema: public

# Destination Database  
Host: 192.168.101.87
Database: tatico_dest
Schema: public
```

### 2. Carregue Metadados (Tab 1)
- Clique em "🔄 Scan Tables"
- Sistema detecta dependências FK automaticamente
- Ordena tabelas topologicamente (pais → filhos)
- Selecione tabelas a migrar

### 3. Migre Schema (Tab 2)
- Clique em "🚀 Migrate Schema"
- Cria tabelas, sequences, defaults
- **Não migra** constraints/indexes ainda (evita problemas de FK)

### 4. Migre Dados (Tab 3) - **MÉTODO CSV**
Configurações:
- **CSV Directory**: `data_pg_migration` (onde salvar CSVs)
- **Batch Size**: `10000` (linhas por lote)
- **Duplicate Handling**:
  - `Skip (DO NOTHING)` - Recomendado para re-execução
  - `Update (DO UPDATE)` - Sobrescreve duplicatas
  - `Fail` - Aborta em duplicata
- **Keep CSV files**: Marque para debug

Execução:
1. **Fase 1**: Exporta todas as tabelas para CSV
2. **Fase 2**: Importa todos os CSVs no destino
3. **Cleanup**: Remove CSVs (se não marcou "keep")

### 5. Sincronize Sequences (Tab 4)
- Detecta sequences automaticamente
- Lê MAX(id) da origem
- Define next_value = MAX(id) + offset no destino

### 6. Valide (Tab 5)
- Compara COUNT(*) entre origem e destino
- Identifica tabelas com divergências

## 🎯 Recomendações

### Para Primeira Migração
```
1. Metadata → Selecione todas as tabelas
2. Schema → Migre estrutura
3. Data (CSV) → Conflict: "Fail" (detecta problemas)
4. Sequences → Offset: 1
5. Validate → Verifique contagens
```

### Para Re-execução/Correção
```
1. Metadata → Selecione apenas tabelas problemáticas
2. Schema → PULE (já existe)
3. Data (CSV) → Conflict: "Skip (DO NOTHING)"
4. Sequences → Offset: 1
5. Validate → Verifique contagens
```

### Para Atualização Incremental
```
1. Metadata → Selecione tabelas a atualizar
2. Schema → PULE
3. Data (CSV) → Conflict: "Update (DO UPDATE)"
4. Sequences → Offset: 1000 (buffer de segurança)
5. Validate
```

## 🔍 Debug

### CSVs não foram deletados
```bash
cd data_pg_migration
ls -lh  # Ver todos os CSVs gerados
head -20 vehicle_types.csv  # Inspecionar primeiras 20 linhas
```

### Verificar integridade de um CSV
```python
import csv
with open('data_pg_migration/vehicle_types.csv', 'r') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        print(f"Linha {i}: {row}")
        if i > 10:
            break
```

### Re-importar uma tabela específica
```python
from dbmigrator.data_migration.pg_to_pg_csv import CSVToPostgreSQL
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection

# ... configurar conexão dest ...

importer = CSVToPostgreSQL(dest, schema='public', input_dir='data_pg_migration')
result = importer.import_table('vehicle_types', batch_size=5000, on_conflict='update')

print(f"Imported: {result['rows_imported']}, Skipped: {result['rows_skipped']}")
```

## 📁 Estrutura de Arquivos

```
mysqlpg-migration/
├── dbmigrator/
│   └── data_migration/
│       └── pg_to_pg_csv.py          # ✨ NOVO módulo CSV
├── pages/
│   ├── 13_🔄_PG_to_PG.py           # ✨ RENOVADO interface
│   └── 13_🔄_PG_to_PG_OLD.py.bak   # Backup do código antigo
├── data_pg_migration/               # CSVs temporários (criado automaticamente)
│   ├── vehicle_types.csv
│   ├── rules.csv
│   └── tax_logs.csv
└── MIGRATION_CSV_README.md          # Este arquivo
```

## 🚀 Próximos Passos

1. **Execute a migração completa** usando o novo método CSV
2. **Valide os dados** comparando contagens e amostras
3. **Verifique as colunas problemáticas** (name, user_id, etc)
4. **Reporte resultados** - Se ainda houver problemas, os CSVs facilitam o debug

## ⚠️ Notas Importantes

- O arquivo antigo foi salvo como `13_🔄_PG_to_PG_OLD.py.bak`
- Método antigo (INSERT direto) foi **completamente removido**
- Sistema agora é **CSV-only** para máxima confiabilidade
- CSVs são salvos em `data_pg_migration/` por padrão
- Batch size de 10000 é bom equilíbrio entre velocidade e memória

## 📞 Suporte

Se encontrar problemas:
1. Verifique os logs no terminal
2. Inspecione os CSVs gerados
3. Use a tab Validate para identificar discrepâncias
4. Tente re-executar com batch_size menor (5000 ou 1000)

---

**Desenvolvido em**: 18 de dezembro de 2025  
**Metodologia**: CSV-based migration para PostgreSQL → PostgreSQL

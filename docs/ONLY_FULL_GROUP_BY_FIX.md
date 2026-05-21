# Solução para Erro ONLY_FULL_GROUP_BY

## 🐛 Problema

Ao tentar carregar as tabelas do MySQL, você pode encontrar este erro:

```
mysql.connector.errors.ProgrammingError: 1055 (42000): Expression #3 of SELECT list is not in GROUP BY clause and contains nonaggregated column 'information_schema.KEY_COLUMN_USAGE.REFERENCED_TABLE_SCHEMA' which is not functionally dependent on columns in GROUP BY clause; this is incompatible with sql_mode=only_full_group_by
```

## 🔍 Causa

O MySQL 8.0+ tem o modo `ONLY_FULL_GROUP_BY` ativado por padrão, que requer que todas as colunas não agregadas no `SELECT` estejam presentes na cláusula `GROUP BY` ou sejam funcionalmente dependentes das colunas do `GROUP BY`.

Queries antigas que funcionavam no MySQL 5.7 podem falhar no MySQL 8.0+ devido a essa restrição mais rigorosa.

## ✅ Solução Implementada

As queries foram corrigidas em dois arquivos:

### 1. Query de Constraints (`fetch_constraints_info`)

**Antes:**
```sql
SELECT CONSTRAINT_NAME, GROUP_CONCAT(COLUMN_NAME) as COLUMN_NAME, 
       REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_NAME = 'table' AND TABLE_SCHEMA = 'db'
GROUP BY CONSTRAINT_NAME
```

**Depois:**
```sql
SELECT 
    CONSTRAINT_NAME, 
    GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION) as COLUMN_NAME, 
    MAX(REFERENCED_TABLE_SCHEMA) as REFERENCED_TABLE_SCHEMA, 
    MAX(REFERENCED_TABLE_NAME) as REFERENCED_TABLE_NAME, 
    MAX(REFERENCED_COLUMN_NAME) as REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_NAME = 'table' AND TABLE_SCHEMA = 'db'
GROUP BY CONSTRAINT_NAME
ORDER BY CONSTRAINT_NAME
```

### 2. Query de Indexes (`fetch_indexes_info`)

**Antes:**
```sql
SELECT INDEX_NAME, GROUP_CONCAT(COLUMN_NAME) as COLUMN_NAME, 
       NULLABLE, INDEX_TYPE, NON_UNIQUE
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_NAME = 'table' AND TABLE_SCHEMA = 'db' 
GROUP BY INDEX_NAME
```

**Depois:**
```sql
SELECT 
    INDEX_NAME, 
    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) as COLUMN_NAME, 
    MAX(NULLABLE) as NULLABLE, 
    MAX(INDEX_TYPE) as INDEX_TYPE, 
    MAX(NON_UNIQUE) as NON_UNIQUE
FROM INFORMATION_SCHEMA.STATISTICS
WHERE TABLE_NAME = 'table' AND TABLE_SCHEMA = 'db' 
GROUP BY INDEX_NAME
ORDER BY INDEX_NAME
```

## 🎯 O que Mudou

1. **Uso de `MAX()`**: Colunas que não são parte do `GROUP BY` agora usam a função agregada `MAX()`, que é segura para estes casos pois todos os valores dentro de um mesmo grupo (CONSTRAINT_NAME ou INDEX_NAME) são idênticos.

2. **`ORDER BY` no `GROUP_CONCAT`**: Adicionado ordenação explícita (`ORDINAL_POSITION` e `SEQ_IN_INDEX`) para garantir que as colunas sejam concatenadas na ordem correta.

3. **`ORDER BY` final**: Adicionado ordenação ao resultado final para consistência.

## 🔧 Alternativa (Não Recomendada)

Se você preferir desabilitar o `ONLY_FULL_GROUP_BY` (não recomendado), pode executar:

### Temporariamente (apenas para a sessão atual):
```sql
SET sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));
```

### Permanentemente (modificar `my.cnf` ou `my.ini`):
```ini
[mysqld]
sql_mode=STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION
```

### No Docker Compose:
```yaml
mysql:
  image: mysql:8.0
  command: --sql-mode=STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION
```

## ⚠️ Por que Não Desabilitar?

1. **Padrão SQL**: `ONLY_FULL_GROUP_BY` segue o padrão SQL e previne queries ambíguas
2. **Segurança**: Evita resultados inesperados em queries mal escritas
3. **Compatibilidade**: Outras bases de dados (PostgreSQL, Oracle) também seguem essa regra
4. **Já Corrigido**: As queries já foram corrigidas para serem compatíveis

## 🧪 Testando a Solução

1. **Reinicie a aplicação:**
   ```bash
   python app.py
   ```

2. **Acesse a interface web:**
   http://localhost:5000

3. **Na aba "Conversion":**
   - Clique em "Load Tables"
   - As tabelas devem carregar sem erro

4. **Verifique os logs:**
   - Deve mostrar as queries sendo executadas com sucesso
   - Não deve haver mais erros relacionados a `ONLY_FULL_GROUP_BY`

## 📝 Arquivos Modificados

- `dbmigrator/data_access/mysql_metadata_reader.py`
  - Função `fetch_constraints_info()` - linha ~131
  - Função `fetch_indexes_info()` - linha ~173

## 🎓 Referências

- [MySQL 8.0 Reference Manual - ONLY_FULL_GROUP_BY](https://dev.mysql.com/doc/refman/8.0/en/group-by-handling.html)
- [MySQL 8.0 SQL Modes](https://dev.mysql.com/doc/refman/8.0/en/sql-mode.html)
- [Stack Overflow - Expression #1 of SELECT list is not in GROUP BY clause](https://stackoverflow.com/questions/34115174/)

## ✅ Status

**Problema:** ✅ Resolvido  
**Versão Corrigida:** Atual  
**Compatibilidade:** MySQL 5.7+ e MySQL 8.0+

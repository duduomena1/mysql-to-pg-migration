"""
Módulo para migração parcial de tabelas com filtro temporal.
Permite migrar janelas de tempo específicas de tabelas grandes sem executar COUNT(*).
"""

import csv
import json
import os
import time
import traceback
from datetime import datetime
from typing import Optional, Callable

from dbmigrator.migration_logging.log import MigrationLogger
from dbmigrator.data_access.mysql_metadata_reader import mysql_metadata_table
from dbmigrator.data_access.mysql_data_access import MySQLTableIterator
from dbmigrator.data_access.postgresql_data_access import PostgreSQLWriter, postgres_execute_DDL
from dbmigrator.structure_conversion.table_to_sql import table_to_postgres_ddl, constraints_to_sql, indexes_to_sql
from dbmigrator.structure_conversion.csv_utils import (
    deserialize_row_with_columns,
    serialize_value,
    folder_name,
)
from dbmigrator.data_access.metadata_models import Table


class PartialTableMigrator:
    """
    Orquestra migração parcial de tabelas com filtro temporal.
    Suporta:
    - Validação e criação automática de tabela no PostgreSQL
    - Filtro WHERE por intervalo de datas
    - Retry automático com backoff exponencial
    - Checkpointing para retomada após falhas
    - Desabilitação temporária de FKs
    """
    
    def __init__(self, mysql_conn, postgres_conn, schema_name="public"):
        self.mysql_conn = mysql_conn
        self.postgres_conn = postgres_conn
        self.schema_name = schema_name
        self.progress_file = "partial_progress.json"
        self.log_file = "partial_migration.log"
        self.max_retries = 5
        self.retry_backoff = [1, 2, 4, 8, 16]  # segundos
        
    def migrate_table_partial(
        self,
        table_name: str,
        filter_column: str,
        start_date: str,
        end_date: str,
        mysql_batch_size: int = 5000,
        postgres_bulk_size: int = 5000,
        strategy: str = "append",
        use_csv: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """
        Executa migração parcial de uma tabela.
        
        Args:
            table_name: Nome da tabela a migrar
            filter_column: Nome da coluna temporal para filtro
            start_date: Data inicial (formato ISO: YYYY-MM-DD HH:MM:SS)
            end_date: Data final (formato ISO: YYYY-MM-DD HH:MM:SS)
            mysql_batch_size: Tamanho do batch de leitura do MySQL
            postgres_bulk_size: Tamanho do bulk de escrita no PostgreSQL
            strategy: 'append' ou 'truncate'
            progress_callback: Função callback para progresso (recebe mensagem, nível)
            
        Returns:
            dict com resultado da migração
        """
        try:
            self._log(f"Starting partial migration for table {table_name}", progress_callback)
            self._log(f"Filter: {filter_column} BETWEEN '{start_date}' AND '{end_date}'", progress_callback)
            self._log(f"Strategy: {strategy}, MySQL batch: {mysql_batch_size}, PostgreSQL bulk: {postgres_bulk_size}", progress_callback)
            
            # 1. Verificar progresso existente
            existing_progress = self._load_progress(table_name, filter_column, start_date, end_date)
            last_batch = existing_progress.get('last_successful_batch', 0) if existing_progress else 0
            offset = last_batch * mysql_batch_size
            
            if existing_progress and existing_progress.get('status') == 'in_progress':
                self._log(f"Resuming migration from batch {last_batch} (offset {offset})", progress_callback)
            
            # 2. Carregar metadata da tabela do MySQL
            self._log(f"Loading table metadata from MySQL...", progress_callback)
            table_metadata = self._get_table_metadata(table_name)
            
            # 3. Validar e criar tabela no PostgreSQL se necessário
            self._log(f"Validating/creating table in PostgreSQL...", progress_callback)
            table_exists = self._ensure_table_exists(table_metadata, strategy, progress_callback)
            
            # 4. Desabilitar FKs temporariamente se modo truncate
            if strategy == "truncate" and table_exists:
                self._disable_foreign_keys(table_name, progress_callback)
            
            # 5. Executar migração com retry
            result = self._migrate_with_retry(
                table_metadata=table_metadata,
                filter_column=filter_column,
                start_date=start_date,
                end_date=end_date,
                mysql_batch_size=mysql_batch_size,
                postgres_bulk_size=postgres_bulk_size,
                use_csv=use_csv,
                offset=offset,
                last_batch=last_batch,
                progress_callback=progress_callback
            )
            
            # 6. Reabilitar FKs
            if strategy == "truncate":
                self._enable_foreign_keys(table_name, progress_callback)
            
            # 7. Salvar progresso final
            self._save_progress(
                table_name=table_name,
                filter_column=filter_column,
                start_date=start_date,
                end_date=end_date,
                last_batch=result['total_batches'],
                total_rows=result['total_rows'],
                status='completed'
            )
            
            self._log(f"Migration completed successfully! Total rows: {result['total_rows']}", progress_callback)
            return {
                'success': True,
                'table': table_name,
                'rows_migrated': result['total_rows'],
                'batches': result['total_batches']
            }
            
        except Exception as e:
            error_msg = f"Error in partial migration: {str(e)}\n{traceback.format_exc()}"
            self._log(error_msg, progress_callback, level="ERROR")
            MigrationLogger().log_error(error_msg)
            
            # Salvar progresso com status de erro
            self._save_progress(
                table_name=table_name,
                filter_column=filter_column,
                start_date=start_date,
                end_date=end_date,
                last_batch=last_batch,
                total_rows=0,
                status='failed',
                error=str(e)
            )
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_table_metadata(self, table_name: str) -> Table:
        """Busca metadata completo da tabela do MySQL."""
        try:
            return mysql_metadata_table(self.mysql_conn, table_name)
        except Exception as e:
            raise Exception(f"Failed to fetch metadata for table {table_name}: {str(e)}")
    
    def _ensure_table_exists(self, table: Table, strategy: str, progress_callback) -> bool:
        """
        Verifica se tabela existe no PostgreSQL.
        Se não existir, cria com estrutura completa (PKs, indexes, FKs).
        Se existir e strategy='truncate', trunca a tabela.
        
        Returns:
            bool: True se tabela já existia, False se foi criada
        """
        try:
            # Verificar se tabela existe
            cursor = self.postgres_conn.connection.cursor()
            query = f"""
                SELECT EXISTS (
                    SELECT FROM pg_tables 
                    WHERE schemaname = '{self.schema_name}' 
                    AND tablename = '{table.name}'
                )
            """
            cursor.execute(query)
            exists = cursor.fetchone()[0]
            cursor.close()
            
            if exists:
                self._log(f"Table {table.name} already exists in PostgreSQL", progress_callback)
                
                if strategy == "truncate":
                    self._log(f"Truncating table {table.name}...", progress_callback)
                    truncate_sql = f"TRUNCATE TABLE {self.schema_name}.{table.name} CASCADE"
                    postgres_execute_DDL(self.postgres_conn, truncate_sql)
                    self.postgres_conn.connection.commit()
                    
                return True
            
            # Criar tabela com estrutura completa
            self._log(f"Table {table.name} does not exist. Creating...", progress_callback)
            
            # 1. Criar ENUMs se necessário
            table_sql, enum_sqls = table_to_postgres_ddl(table, schema=self.schema_name)
            for enum_sql in enum_sqls:
                self._log(f"Creating ENUM: {enum_sql[:80]}...", progress_callback)
                try:
                    postgres_execute_DDL(self.postgres_conn, enum_sql)
                except Exception as e:
                    # ENUM pode já existir, ignorar erro
                    if "already exists" not in str(e).lower():
                        raise
            
            # 2. Criar tabela
            self._log(f"Creating table structure...", progress_callback)
            postgres_execute_DDL(self.postgres_conn, table_sql)
            
            # 3. Criar constraints e primary keys
            constraints_sql, primary_keys_sql = constraints_to_sql(
                table.constraints, 
                table=table.name, 
                schema=self.schema_name
            )
            
            if primary_keys_sql:
                self._log(f"Creating primary keys...", progress_callback)
                postgres_execute_DDL(self.postgres_conn, primary_keys_sql)
            
            if constraints_sql:
                self._log(f"Creating foreign keys...", progress_callback)
                postgres_execute_DDL(self.postgres_conn, constraints_sql)
            
            # 4. Criar indexes
            indexes_sql = indexes_to_sql(
                table.indexes,
                table=table.name,
                schema=self.schema_name,
                GIST_indexes=[]  # Pode ser parametrizado se necessário
            )
            
            if indexes_sql:
                self._log(f"Creating indexes...", progress_callback)
                postgres_execute_DDL(self.postgres_conn, indexes_sql)
            
            self.postgres_conn.connection.commit()
            self._log(f"Table {table.name} created successfully with full structure", progress_callback)
            
            return False
            
        except Exception as e:
            raise Exception(f"Failed to ensure table exists: {str(e)}")
    
    def _disable_foreign_keys(self, table_name: str, progress_callback):
        """Desabilita triggers de FK temporariamente."""
        try:
            self._log(f"Disabling foreign key triggers for {table_name}...", progress_callback)
            sql = f"ALTER TABLE {self.schema_name}.{table_name} DISABLE TRIGGER ALL"
            postgres_execute_DDL(self.postgres_conn, sql)
            self.postgres_conn.connection.commit()
        except Exception as e:
            self._log(f"Warning: Could not disable FK triggers: {str(e)}", progress_callback, level="WARNING")
    
    def _enable_foreign_keys(self, table_name: str, progress_callback):
        """Reabilita triggers de FK."""
        try:
            self._log(f"Re-enabling foreign key triggers for {table_name}...", progress_callback)
            sql = f"ALTER TABLE {self.schema_name}.{table_name} ENABLE TRIGGER ALL"
            postgres_execute_DDL(self.postgres_conn, sql)
            self.postgres_conn.connection.commit()
        except Exception as e:
            self._log(f"Warning: Could not enable FK triggers: {str(e)}", progress_callback, level="WARNING")
    
    def _migrate_with_retry(
        self,
        table_metadata: Table,
        filter_column: str,
        start_date: str,
        end_date: str,
        mysql_batch_size: int,
        postgres_bulk_size: int,
        use_csv: bool,
        offset: int,
        last_batch: int,
        progress_callback
    ) -> dict:
        """
        Executa migração com retry automático em caso de falha de conexão.
        """
        for attempt in range(self.max_retries):
            try:
                # Escolher método de migração
                if use_csv:
                    return self._execute_migration_csv(
                        table_metadata=table_metadata,
                        filter_column=filter_column,
                        start_date=start_date,
                        end_date=end_date,
                        mysql_batch_size=mysql_batch_size,
                        offset=offset,
                        last_batch=last_batch,
                        progress_callback=progress_callback
                    )
                else:
                    return self._execute_migration(
                        table_metadata=table_metadata,
                        filter_column=filter_column,
                        start_date=start_date,
                        end_date=end_date,
                        mysql_batch_size=mysql_batch_size,
                        postgres_bulk_size=postgres_bulk_size,
                        offset=offset,
                        last_batch=last_batch,
                        progress_callback=progress_callback
                    )
            except Exception as e:
                error_msg = str(e).lower()
                
                # Verificar se é erro de conexão
                is_connection_error = any(keyword in error_msg for keyword in [
                    'connection', 'lost', 'closed', 'timeout', 'operational', 'interface'
                ])
                
                if is_connection_error and attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff[attempt]
                    self._log(
                        f"Connection error detected. Retry {attempt + 1}/{self.max_retries} in {wait_time}s...",
                        progress_callback,
                        level="WARNING"
                    )
                    time.sleep(wait_time)
                    
                    # Tentar reconectar
                    try:
                        self._reconnect()
                    except Exception as reconnect_error:
                        self._log(f"Reconnection failed: {str(reconnect_error)}", progress_callback, level="ERROR")
                else:
                    raise
        
        raise Exception(f"Migration failed after {self.max_retries} retries")
    
    def _reconnect(self):
        """Tenta reconectar aos bancos de dados."""
        try:
            self.mysql_conn.create()
            self.postgres_conn.create()
        except Exception as e:
            raise Exception(f"Failed to reconnect: {str(e)}")
    
    def _execute_migration_csv(
        self,
        table_metadata: Table,
        filter_column: str,
        start_date: str,
        end_date: str,
        mysql_batch_size: int,
        offset: int,
        last_batch: int,
        progress_callback
    ) -> dict:
        """
        Executa migração otimizada usando CSV e COPY do PostgreSQL.
        Performance: 10-20x mais rápida que INSERTs em batch.
        """
        # Criar diretório para CSVs temporários
        csv_dir = os.path.join(folder_name, "partial")
        os.makedirs(csv_dir, exist_ok=True)
        
        # Nome do arquivo CSV baseado na tabela e período
        safe_start = start_date.replace(' ', '_').replace(':', '-')
        safe_end = end_date.replace(' ', '_').replace(':', '-')
        csv_file = os.path.join(csv_dir, f"{table_metadata.name}_{safe_start}_to_{safe_end}.csv")
        
        # WHERE clause
        where_clause = f"`{filter_column}` BETWEEN %s AND %s"
        where_params = [start_date, end_date]
        
        # Iterator MySQL
        iterator = MySQLTableIterator(
            mysql=self.mysql_conn,
            table=table_metadata,
            batch_size=mysql_batch_size,
            where_clause=where_clause,
            where_params=where_params,
            skip_count=True,
            offset=offset
        )
        
        total_rows = 0
        current_batch = last_batch
        
        self._log(f"📝 Writing data to CSV: {csv_file}", progress_callback)
        
        try:
            # Fase 1: Exportar MySQL → CSV
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                
                for row in iterator:
                    # Serializar valores (tratar NULL, datetime, geometry, etc)
                    data_row = tuple(
                        serialize_value(value, col) 
                        for value, col in zip(row, table_metadata.columns)
                    )
                    writer.writerow(data_row)
                    total_rows += 1
                    
                    # Checkpoint a cada batch
                    if total_rows % mysql_batch_size == 0:
                        current_batch += 1
                        self._log(
                            f"📦 Exported batch {current_batch} ({total_rows:,} rows to CSV)...", 
                            progress_callback
                        )
                        
                        # Salvar checkpoint
                        self._save_progress(
                            table_name=table_metadata.name,
                            filter_column=filter_column,
                            start_date=start_date,
                            end_date=end_date,
                            last_batch=current_batch,
                            total_rows=total_rows,
                            status='exporting_csv'
                        )
            
            self._log(f"✅ CSV export complete: {total_rows:,} rows", progress_callback)
            self._log(f"🚀 Loading into PostgreSQL with conflict resolution...", progress_callback)
            
            # Fase 2: Carregar CSV → PostgreSQL usando INSERT com ON CONFLICT
            # Nota: COPY não suporta ON CONFLICT, então usamos INSERT batch que é quase tão rápido
            cursor = None
            try:
                # Garantir transação limpa
                self.postgres_conn.connection.rollback()
                self.postgres_conn.connection.autocommit = False
                
                cursor = self.postgres_conn.connection.cursor()
                
                # Preparar lista de colunas (com aspas para nomes reservados)
                column_names = ', '.join([f'"{col.name}"' for col in table_metadata.columns])
                placeholders = ', '.join(['%s'] * len(table_metadata.columns))
                
                # SQL INSERT com ON CONFLICT para ignorar duplicatas
                insert_sql = f"""
                    INSERT INTO {self.schema_name}.{table_metadata.name} ({column_names})
                    VALUES ({placeholders})
                    ON CONFLICT DO NOTHING
                """
                
                self._log(f"📥 Inserting {total_rows:,} rows (skipping duplicates)...", progress_callback)
                
                # Ler CSV e inserir em batches
                import psycopg2.extras
                
                inserted_count = 0
                skipped_count = 0
                batch_size = 10000  # Batch otimizado para INSERT
                batch_data = []
                
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    
                    for idx, row in enumerate(reader, 1):
                        # Deserializar valores do CSV com coerção de tipos por coluna
                        data_tuple = deserialize_row_with_columns(row, table_metadata.columns)
                        batch_data.append(data_tuple)
                        
                        # Inserir batch quando atingir o tamanho
                        if len(batch_data) >= batch_size:
                            rows_before = self._get_table_count(cursor, table_metadata.name)
                            psycopg2.extras.execute_batch(cursor, insert_sql, batch_data, page_size=batch_size)
                            self.postgres_conn.connection.commit()
                            rows_after = self._get_table_count(cursor, table_metadata.name)
                            
                            inserted_this_batch = rows_after - rows_before
                            skipped_this_batch = len(batch_data) - inserted_this_batch
                            
                            inserted_count += inserted_this_batch
                            skipped_count += skipped_this_batch
                            
                            self._log(
                                f"📦 Batch {idx // batch_size}: +{inserted_this_batch:,} rows, ~{skipped_this_batch:,} skipped (total: {inserted_count:,}/{idx:,})",
                                progress_callback
                            )
                            batch_data = []
                    
                    # Inserir batch final
                    if batch_data:
                        rows_before = self._get_table_count(cursor, table_metadata.name)
                        psycopg2.extras.execute_batch(cursor, insert_sql, batch_data, page_size=len(batch_data))
                        self.postgres_conn.connection.commit()
                        rows_after = self._get_table_count(cursor, table_metadata.name)
                        
                        inserted_this_batch = rows_after - rows_before
                        skipped_this_batch = len(batch_data) - inserted_this_batch
                        
                        inserted_count += inserted_this_batch
                        skipped_count += skipped_this_batch
                
                self._log(f"✅ Import complete!", progress_callback)
                self._log(f"📊 Inserted: {inserted_count:,} rows", progress_callback)
                self._log(f"⏭️  Skipped (duplicates): {skipped_count:,} rows", progress_callback)
                self._log(f"📈 Total processed: {total_rows:,} rows", progress_callback)
                
            except Exception as insert_error:
                self._log(f"❌ Insert failed: {str(insert_error)}", progress_callback, level="ERROR")
                try:
                    self.postgres_conn.connection.rollback()
                except:
                    pass
                raise Exception(f"PostgreSQL INSERT failed: {str(insert_error)}")
            finally:
                if cursor:
                    cursor.close()
            
            # Opcional: Remover arquivo CSV temporário (comentar se quiser manter)
            # os.remove(csv_file)
            # self._log(f"🗑️ Temporary CSV removed", progress_callback)
            
            self._log(f"✅ Migration completed successfully!", progress_callback)
            self._log(f"📁 CSV file saved: {csv_file}", progress_callback)
            
            return {
                'success': True,
                'total_rows': total_rows,
                'total_batches': current_batch,
                'csv_file': csv_file,
                'method': 'csv_copy'
            }
            
        except Exception as e:
            error_msg = f"❌ Error in CSV migration: {str(e)}"
            self._log(error_msg, progress_callback, level="ERROR")
            # Adicionar traceback completo no log
            self._log(traceback.format_exc(), progress_callback, level="ERROR")
            raise
        finally:
            if 'iterator' in locals():
                iterator.close()
    
    def _execute_migration(
        self,
        table_metadata: Table,
        filter_column: str,
        start_date: str,
        end_date: str,
        mysql_batch_size: int,
        postgres_bulk_size: int,
        offset: int,
        last_batch: int,
        progress_callback
    ) -> dict:
        """
        Executa a migração de dados propriamente dita.
        """
        # Construir WHERE clause parametrizada
        where_clause = f"`{filter_column}` BETWEEN %s AND %s"
        where_params = [start_date, end_date]
        
        # Criar iterator com filtro e offset para retomada
        iterator = MySQLTableIterator(
            mysql=self.mysql_conn,
            table=table_metadata,
            batch_size=mysql_batch_size,
            where_clause=where_clause,
            where_params=where_params,
            skip_count=True,  # Não executar COUNT(*)
            offset=offset
        )
        
        # Criar writer
        writer = PostgreSQLWriter(
            postgresql=self.postgres_conn,
            table=table_metadata,
            schema=self.schema_name,
            buffer_size=postgres_bulk_size
        )
        
        # Migrar dados
        total_rows = 0
        current_batch = last_batch
        
        self._log(f"Starting data migration (batch {current_batch})...", progress_callback)
        
        try:
            for row in iterator:
                writer.insert_data(row)
                total_rows += 1
                
                # Checkpoint a cada batch completo
                if total_rows % mysql_batch_size == 0:
                    current_batch += 1
                    self._log(f"Migrated batch {current_batch} ({total_rows} rows so far)...", progress_callback)
                    
                    # Salvar checkpoint
                    self._save_progress(
                        table_name=table_metadata.name,
                        filter_column=filter_column,
                        start_date=start_date,
                        end_date=end_date,
                        last_batch=current_batch,
                        total_rows=total_rows,
                        status='in_progress'
                    )
            
            # Flush final
            writer.flush_buffer()
            self.postgres_conn.connection.commit()
            
            return {
                'total_rows': total_rows,
                'total_batches': current_batch
            }
            
        finally:
            iterator.close()
    
    def _load_progress(self, table_name: str, filter_column: str, start_date: str, end_date: str) -> Optional[dict]:
        """Carrega progresso existente do partial_progress.json."""
        try:
            if not os.path.exists(self.progress_file):
                return None
            
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
            
            # Buscar entrada correspondente
            for migration in data.get('migrations', []):
                if (migration.get('table') == table_name and
                    migration.get('column') == filter_column and
                    migration.get('start_date') == start_date and
                    migration.get('end_date') == end_date and
                    migration.get('status') == 'in_progress'):
                    return migration
            
            return None
            
        except Exception as e:
            MigrationLogger().log_warning(f"Could not load progress: {str(e)}")
            return None
    
    def _save_progress(
        self,
        table_name: str,
        filter_column: str,
        start_date: str,
        end_date: str,
        last_batch: int,
        total_rows: int,
        status: str,
        error: str = None
    ):
        """Salva progresso no partial_progress.json."""
        try:
            # Carregar dados existentes
            data = {'migrations': []}
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
            
            # Atualizar ou adicionar entrada
            entry = {
                'table': table_name,
                'column': filter_column,
                'start_date': start_date,
                'end_date': end_date,
                'last_successful_batch': last_batch,
                'total_rows_migrated': total_rows,
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            
            if error:
                entry['error'] = error
            
            # Remover entrada antiga se existir (mesma tabela/filtro)
            data['migrations'] = [
                m for m in data.get('migrations', [])
                if not (m.get('table') == table_name and
                       m.get('column') == filter_column and
                       m.get('start_date') == start_date and
                       m.get('end_date') == end_date and
                       m.get('status') == 'in_progress')
            ]
            
            # Adicionar nova entrada se não for remoção
            if status != 'removed':
                data['migrations'].append(entry)
            
            # Salvar
            with open(self.progress_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            MigrationLogger().log_warning(f"Could not save progress: {str(e)}")
    
    def _log(self, message: str, callback=None, level: str = "INFO"):
        """Log para arquivo e callback."""
        # Log no arquivo
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}\n"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_message)
        except Exception as e:
            print(f"Warning: Could not write to log file: {str(e)}")
        
        # Log via MigrationLogger
        if level == "ERROR":
            MigrationLogger().log_error(message)
        elif level == "WARNING":
            MigrationLogger().log_warning(message)
        else:
            MigrationLogger().log_info(message)
        
        # Callback para UI
        if callback:
            callback(message, level)
    
    def _get_table_count(self, cursor, table_name: str) -> int:
        """Helper para contar linhas na tabela PostgreSQL."""
        cursor.execute(f"SELECT COUNT(*) FROM {self.schema_name}.{table_name}")
        return cursor.fetchone()[0]

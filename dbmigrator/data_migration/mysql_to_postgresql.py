import csv
import os

import os.path
import sys
from itertools import islice

from dbmigrator.structure_conversion.csv_utils import (
    deserialize_row_with_columns,
    serialize_value,
    folder_name,
    csv_field_limit,
)
from dbmigrator.data_access.mysql_metadata_reader import mysql_fetch_tables
from dbmigrator.migration_logging.log import MigrationLogger
from dbmigrator.migration_logging.progress_log.progress_log import ProgressLog
from dbmigrator.migration_logging.progress_log.tables_log import TablesLog, TableState
from dbmigrator.structure_conversion.table_to_json import load_json_file, save_json_file
from dbmigrator.structure_conversion.table_to_sql import table_to_postgres_ddl, constraints_to_sql, indexes_to_sql, sequences_to_sql
from dbmigrator.data_access.postgresql_data_access import postgres_execute_DDL
from dbmigrator.data_access.postgresql_metadata_access import PostgreSQLTableManager
from dbmigrator.data_access.mysql_data_access import MySQLTableIterator
from dbmigrator.data_access.postgresql_data_access import PostgreSQLWriter
from dbmigrator.data_access.metadata_models import Table

from dbmigrator.configuration_management.configuration import MigrationConfig


migration_config = None
config_path = "config.json"

if os.path.exists(config_path):
    migration_config = MigrationConfig.from_json_file(config_path)
    MigrationLogger().log_info(f"Loaded configuration from file")
else:
    migration_config = MigrationConfig.default_config()
    migration_config.save_to_file(config_path)
    MigrationLogger().log_info(f"Loaded default configuration")

class MySQLToPostgreSQL:
    def __init__(self, mysql, postgresql):
        self.mysql_conn = mysql
        self.postgres_conn = postgresql
        self.tables = None
        self.GIST_indexes = None
        self.excluded_tables = migration_config.excluded_tables
        self.only_tables = []
        self.buffer_tables = ""
        self.buffer_enum = ""
        self.buffer_constraints = ""
        self.buffer_primary_keys = ""
        self.buffer_indexes = ""
        self.bulk_commit = migration_config.bulk_commit
        self.postgresql_bulk_size = migration_config.postgres_bulk_size
        self.mysql_batch_size = migration_config.mysql_batch_size
        csv.field_size_limit(csv_field_limit)
        if csv.field_size_limit == csv_field_limit:
            MigrationLogger().log_info(f"Field size successfully set to {sys.maxsize}")

    def load_mysql_metadata_json(self, filename):
        tables_json = load_json_file(filename)
        if tables_json is None:
            tables_json = mysql_fetch_tables(self.mysql_conn, self.excluded_tables)
            save_json_file(tables_json, filename)
        self.tables = tables_json
        return tables_json

    def save_mysql_metadata_json(self, tables_json, filename):
        if tables_json is not None:
            save_json_file(tables_json, filename)

    def table_to_sql(self, table: Table, schema, buffer=True, constraints_names_already_used=[]):
        buffer_enum_sql = ""
        table_sql, enum_sql = table_to_postgres_ddl(table, schema=schema)
        constraints, primary_keys = constraints_to_sql(table.constraints, table=table.name, schema=schema, constraints_names_already_used=constraints_names_already_used)
        indexes = indexes_to_sql(table.indexes, table=table.name, schema=schema, GIST_indexes=self.GIST_indexes)
        sequences = sequences_to_sql(table.constraints, table=table.name, schema=schema)

        for enum in enum_sql:
            buffer_enum_sql += enum + '\n'

        if buffer:
            self.buffer_tables += table_sql
            self.buffer_enum += buffer_enum_sql
            self.buffer_constraints += constraints
            self.buffer_primary_keys += primary_keys
            self.buffer_indexes += indexes

        return table_sql, buffer_enum_sql, constraints, primary_keys, indexes, sequences

    def generate_DDLs(self, schema):
        self.buffer_tables = ""
        self.buffer_enum = ""
        self.buffer_constraints = ""
        self.buffer_primary_keys = ""
        self.buffer_indexes = ""

        if self.only_tables is not None and len(self.only_tables) > 0:
            for table in self.tables:
                if table.name in self.only_tables:
                    self.table_to_sql(table, schema)
        else:
            for table in self.tables:
                if table.name not in self.excluded_tables or table.excluded is False:
                    self.table_to_sql(table, schema)

    def execute_DDL_enums(self):
        postgres_execute_DDL(self.postgres_conn, self.buffer_enum)

    def execute_DDL_tables(self):
        postgres_execute_DDL(self.postgres_conn, self.buffer_tables)

    def execute_DDL_constraints(self):
        postgres_execute_DDL(self.postgres_conn, self.buffer_constraints)

    def execute_DDL_primary_keys(self):
        postgres_execute_DDL(self.postgres_conn, self.buffer_primary_keys)

    def execute_DDL_indexes(self):
        postgres_execute_DDL(self.postgres_conn, self.buffer_indexes)

    def set_sequence_table(self, table, schema):
        pg_manager = PostgreSQLTableManager(self.postgres_conn, table.name, schema=schema)
        max_id = pg_manager.get_max_id('id')
        # Se a tabela está vazia, max_id será None, então usar 1
        next_value = (max_id + 1) if max_id is not None else 1
        pg_manager.set_sequence_value(next_value)

    def set_sequences(self, schema):
        if self.only_tables is not None and len(self.only_tables) > 0:
            for table in self.tables:
                if table.name in self.only_tables:
                    self.set_sequence_table(table, schema)
        else:
            for table in self.tables:
                if table.name not in self.excluded_tables:
                    self.set_sequence_table(table, schema)

    def truncate_table(self, table, schema):
        pg_manager = PostgreSQLTableManager(self.postgres_conn, table.name, schema=schema)
        pg_manager.truncate_table()

    def truncate_tables(self, schema):
        if self.only_tables is not None and len(self.only_tables) > 0:
            for table in self.tables:
                if table.name in self.only_tables:
                    self.truncate_table(table, schema)
        else:
            for table in self.tables:
                if table.name not in self.excluded_tables:
                    self.truncate_table(table, schema)

    def read_from_csv(self, table: Table, schema, callback=None):
        # Rename table to lowercase if needed before migration
        original_name = table.name
        lowercase_name = original_name.lower()
        needs_rename = original_name != lowercase_name
        
        if needs_rename:
            schema_prefix = f"{schema}." if schema else ""
            cursor = self.postgres_conn.connection.cursor()
            try:
                rename_sql = f"ALTER TABLE {schema_prefix}\"{original_name}\" RENAME TO {lowercase_name}"
                MigrationLogger().log_info(f"Temporarily renaming table for migration: {rename_sql}")
                cursor.execute(rename_sql)
                self.postgres_conn.connection.commit()
                cursor.close()
            except Exception as e:
                cursor.close()
                MigrationLogger().log_warning(f"Table might already be lowercase: {e}")
        
        postgres_writer = PostgreSQLWriter(self.postgres_conn, table, schema=schema,
                                           buffer_size=self.postgresql_bulk_size, bulk_commit=True)

        file_path = os.path.join(folder_name, table.name + '.csv')
        MigrationLogger().log_info(f"reading from file {file_path}")
        table_state = TablesLog().get_table(table.name)
        if table_state is None:
            table_state = TableState(table.name)
            TablesLog().update_or_add_table(table_state)

        count = table_state.last_migrated_block * self.postgresql_bulk_size

        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                csvreader = csv.reader(csvfile)
                for row in islice(csvreader, table_state.last_migrated_block * self.postgresql_bulk_size, None):
                    data_tuple = deserialize_row_with_columns(row, table.columns)
                    if postgres_writer.insert_data(data_tuple):
                        table_state.last_migrated_block += 1
                        TablesLog().update_or_add_table(table_state)
                    count += 1
                    if callback:
                        callback(count)
                if postgres_writer.flush_buffer():
                    table_state.last_migrated_block += 1
                table_state.fully_migrated = True
                TablesLog().update_or_add_table(table_state)
                if callback:
                    callback(table.num_tuples)
        except Exception as e:
            # Limpar buffer e fazer rollback
            try:
                postgres_writer.buffer.clear()
                postgres_writer.close_cursor()
                self.postgres_conn.connection.rollback()
            except:
                pass
            
            error_detail = str(e)
            # Extrair detalhes mais específicos do erro do PostgreSQL
            if hasattr(e, 'pgerror') and e.pgerror:
                error_detail = e.pgerror
            MigrationLogger().log_error(f"Error reading from CSV for table {table.name}: {error_detail}")
            raise Exception(f"{error_detail}")
        
        # Restore original name after migration
        if needs_rename:
            cursor = self.postgres_conn.connection.cursor()
            try:
                restore_sql = f"ALTER TABLE {schema_prefix}{lowercase_name} RENAME TO \"{original_name}\""
                MigrationLogger().log_info(f"Restoring original table name: {restore_sql}")
                cursor.execute(restore_sql)
                self.postgres_conn.connection.commit()
            except Exception as e:
                MigrationLogger().log_error(f"Error restoring table name: {e}")
            finally:
                cursor.close()

    def save_table_to_csv(self, table: Table, callback=None):
        table_iterator = MySQLTableIterator(self.mysql_conn, table, batch_size=self.mysql_batch_size)

        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        MigrationLogger().log_info(f"saving to file {table.name}")
        # Full path for the CSV file
        file_path = os.path.join(folder_name, table.name + ".csv")
        count = 0
        # Sempre sobrescrever para evitar reutilizar CSV legado com datas ambíguas
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            MigrationLogger().log_info(f"saving to file {file_path}")
            writer = csv.writer(file)
            for row in table_iterator:
                data_row = tuple(serialize_value(value, col) for value, col in zip(row, table.columns))
                writer.writerow(data_row)
                count += 1
                if callback is not None:
                    callback(count)
            MigrationLogger().log_info(f"migrated from file {file_path} successfully,with {table.num_tuples}")

    # Deprecated
    def execute_csv_to_postgres(self, schema):

        if self.only_tables is not None and len(self.only_tables) > 0:
            for table in self.tables:
                if table.name in self.only_tables:
                    self.read_from_csv(table, schema)

        else:
            for table in self.tables:
                if table.name not in self.excluded_tables:
                    self.read_from_csv(table, schema)

    def execute_save_to_csv(self):

        if self.only_tables is not None and len(self.only_tables) > 0:
            for table in self.tables:
                if table.name in self.only_tables:
                    self.save_table_to_csv(table)

        else:
            for table in self.tables:
                if table.name not in self.excluded_tables:
                    self.save_table_to_csv(table)

    def migrate_table(self, table, schema, bulk_commit=False):
        table_iterator = MySQLTableIterator(self.mysql_conn, table, batch_size=self.mysql_batch_size)
        postgres_writer = PostgreSQLWriter(self.postgres_conn, table, schema=schema,
                                           buffer_size=self.postgresql_bulk_size, bulk_commit=bulk_commit)

        for row in table_iterator:
            # print(row)
            postgres_writer.insert_data(row)

        table_iterator.close()
        postgres_writer.flush_buffer()  # flush is mandatory to insert the last rows

    def execute_data_migration(self, schema, progress_log: ProgressLog = None):

        ignore_tables = progress_log.migrated_tables if progress_log is not None else []

        bulk_commit = self.bulk_commit
        if self.only_tables is not None and len(self.only_tables) > 0:
            for table in self.tables:
                if table.name in self.only_tables and table.name not in ignore_tables:
                    self.migrate_table(table, schema, bulk_commit=bulk_commit)
                    if progress_log is not None:
                        progress_log.add_migrated_table(table.name)
        else:
            for table in self.tables:
                if table.name not in self.excluded_tables and table.name not in ignore_tables:
                    self.migrate_table(table, schema, bulk_commit=bulk_commit)
                    if progress_log is not None:
                        progress_log.add_migrated_table(table.name)

    def restore_original_table_names(self, schema="", tables=None):
        """Rename migrated PostgreSQL tables back to their original case-sensitive names."""
        tables_to_restore = tables if tables is not None else self.tables

        if not tables_to_restore:
            return

        schema_prefix = f"{schema}." if schema else ""
        connection = self.postgres_conn.connection
        cursor = connection.cursor()

        try:
            renamed_any = False
            for table in tables_to_restore:
                original_name = table.name
                lowercase_name = original_name.lower()

                if original_name == lowercase_name:
                    continue

                sql = f"ALTER TABLE {schema_prefix}{lowercase_name} RENAME TO \"{original_name}\""
                MigrationLogger().log_info(f"Restoring table name with original case: {sql}")
                cursor.execute(sql)
                renamed_any = True

            if renamed_any:
                connection.commit()

        except Exception as e:
            connection.rollback()
            MigrationLogger().log_error(f"Error restoring original table names: {e}")
            raise e
        finally:
            cursor.close()
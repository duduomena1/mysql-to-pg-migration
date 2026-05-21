"""
PostgreSQL to PostgreSQL Migration using CSV as intermediate format

This module provides migration between PostgreSQL databases using CSV files
as an intermediate format, which ensures data integrity and handles special
cases better than direct INSERT operations.
"""

import csv
import os
import json
from typing import List, Dict, Optional, Callable
from pathlib import Path

from dbmigrator.structure_conversion.csv_utils import serialize_value, deserialize_value, csv_field_limit
from dbmigrator.migration_logging.log import MigrationLogger


class PostgreSQLToCSV:
    """Export PostgreSQL table data to CSV files"""
    
    def __init__(self, pg_connection, schema: str = 'public', output_dir: str = 'data'):
        """
        Initialize PostgreSQL to CSV exporter
        
        Args:
            pg_connection: PostgreSQL connection object
            schema: PostgreSQL schema name
            output_dir: Directory to save CSV files
        """
        self.connection = pg_connection
        self.schema = schema
        self.output_dir = output_dir
        self.logger = MigrationLogger()
        
        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Set CSV field size limit
        csv.field_size_limit(csv_field_limit)
    
    def get_table_columns(self, table_name: str) -> List[Dict]:
        """
        Get column information for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of dicts with column info (name, type, etc)
        """
        cursor = self.connection.connection.cursor()
        
        cursor.execute(f"""
            SELECT 
                column_name,
                data_type,
                udt_name,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = '{self.schema}'
            AND table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row[0],
                'data_type': row[1],
                'udt_name': row[2],
                'max_length': row[3],
                'nullable': row[4],
                'default': row[5]
            })
        
        cursor.close()
        return columns
    
    def export_table(
        self,
        table_name: str,
        batch_size: int = 10000,
        progress_callback: Optional[Callable] = None,
        filter_column: Optional[str] = None,
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
    ) -> Dict:
        """
        Export a table to CSV file
        
        Args:
            table_name: Name of the table to export
            batch_size: Number of rows to fetch at a time
            progress_callback: Optional callback function for progress updates
            filter_column: Optional date/time column to filter by
            start_datetime: Inclusive start datetime (YYYY-MM-DD HH:MM:SS)
            end_datetime: Inclusive end datetime (YYYY-MM-DD HH:MM:SS)
            
        Returns:
            Dict with export statistics
        """
        self.logger.log_info(f"Starting export of table {table_name} to CSV")
        
        # Get column information
        columns = self.get_table_columns(table_name)
        column_names = [col['name'] for col in columns]

        # Validate optional filter
        if filter_column:
            if filter_column not in column_names:
                raise ValueError(f"Column '{filter_column}' not found in table {table_name}")
            if not (start_datetime and end_datetime):
                raise ValueError("Both start_datetime and end_datetime are required when filter_column is set")
        where_clause = ""
        params: List = []
        if filter_column and start_datetime and end_datetime:
            where_clause = f'WHERE "{filter_column}" BETWEEN %s AND %s'
            params = [start_datetime, end_datetime]
            self.logger.log_info(
                f"Applying date filter on {filter_column}: {start_datetime} to {end_datetime}"
            )
        
        # Get total row count
        cursor = self.connection.connection.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM {self.schema}."{table_name}" {where_clause}', params)
        total_rows = cursor.fetchone()[0]
        
        self.logger.log_info(f"Table {table_name} has {total_rows:,} rows")
        
        # Prepare CSV file
        csv_filename = f"{table_name}.csv"
        csv_filepath = os.path.join(self.output_dir, csv_filename)
        
        # Create empty CSV file with headers even if no data
        if total_rows == 0:
            with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
                # Write header row with column names
                writer.writerow(column_names)
            
            cursor.close()
            self.logger.log_info(f"Created empty CSV file for table {table_name}")
            return {
                'table': table_name,
                'rows_exported': 0,
                'file_path': csv_filepath,
                'status': 'empty'
            }
        
        # Export data in batches
        column_list = ', '.join([f'"{col}"' for col in column_names])
        order_column = f'"{filter_column}"' if filter_column else '1'
        rows_exported = 0
        
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_MINIMAL)
            
            # Write header row with column names
            writer.writerow(column_names)
            
            offset = 0
            while offset < total_rows:
                cursor.execute(
                    f"""
                        SELECT {column_list}
                        FROM {self.schema}."{table_name}"
                        {where_clause}
                        ORDER BY {order_column}
                        LIMIT {batch_size} OFFSET {offset}
                    """,
                    params,
                )
                
                rows = cursor.fetchall()
                if not rows:
                    break
                
                # Serialize each row properly
                for row in rows:
                    serialized_row = []
                    for idx, value in enumerate(row):
                        col_info = columns[idx]
                        
                        # Handle NULL values
                        if value is None:
                            serialized_row.append('')
                        # Handle JSON/JSONB
                        elif col_info['data_type'] in ('json', 'jsonb') or col_info['udt_name'] in ('json', 'jsonb'):
                            if isinstance(value, (dict, list)):
                                serialized_row.append(json.dumps(value, ensure_ascii=False))
                            else:
                                serialized_row.append(str(value) if value is not None else '')
                        # Handle arrays
                        elif col_info['data_type'] == 'ARRAY' or col_info['udt_name'].startswith('_'):
                            if isinstance(value, list):
                                # PostgreSQL array format: {elem1,elem2,elem3}
                                serialized_row.append(json.dumps(value, ensure_ascii=False))
                            else:
                                serialized_row.append(str(value) if value is not None else '')
                        # Handle boolean
                        elif col_info['data_type'] == 'boolean':
                            serialized_row.append('t' if value else 'f')
                        # Handle other types
                        else:
                            serialized_row.append(str(value) if value is not None else '')
                    
                    writer.writerow(serialized_row)
                    rows_exported += 1
                
                offset += batch_size
                
                if progress_callback:
                    progress_callback(rows_exported, total_rows)
        
        cursor.close()
        
        self.logger.log_info(f"Successfully exported {rows_exported:,} rows from {table_name} to {csv_filepath}")
        
        return {
            'table': table_name,
            'rows_exported': rows_exported,
            'file_path': csv_filepath,
            'status': 'success'
        }


class CSVToPostgreSQL:
    """Import CSV files into PostgreSQL tables"""
    
    def __init__(self, pg_connection, schema: str = 'public', input_dir: str = 'data'):
        """
        Initialize CSV to PostgreSQL importer
        
        Args:
            pg_connection: PostgreSQL connection object
            schema: PostgreSQL schema name
            input_dir: Directory containing CSV files
        """
        self.connection = pg_connection
        self.schema = schema
        self.input_dir = input_dir
        self.logger = MigrationLogger()
        
        # Set CSV field size limit
        csv.field_size_limit(csv_field_limit)
    
    def get_table_columns(self, table_name: str) -> List[Dict]:
        """
        Get column information for a table
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of dicts with column info (name, type, etc)
        """
        cursor = self.connection.connection.cursor()
        
        cursor.execute(f"""
            SELECT 
                column_name,
                data_type,
                udt_name,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = '{self.schema}'
            AND table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row[0],
                'data_type': row[1],
                'udt_name': row[2],
                'max_length': row[3],
                'nullable': row[4],
                'default': row[5]
            })
        
        cursor.close()
        return columns
    
    def import_table(self, table_name: str, batch_size: int = 10000,
                    on_conflict: str = 'do_nothing',
                    progress_callback: Optional[Callable] = None) -> Dict:
        """
        Import CSV file into PostgreSQL table
        
        Args:
            table_name: Name of the table to import
            batch_size: Number of rows to insert at a time
            on_conflict: How to handle conflicts ('do_nothing', 'update', or None)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dict with import statistics
        """
        csv_filename = f"{table_name}.csv"
        csv_filepath = os.path.join(self.input_dir, csv_filename)
        
        if not os.path.exists(csv_filepath):
            self.logger.log_error(f"CSV file not found: {csv_filepath}")
            return {
                'table': table_name,
                'rows_imported': 0,
                'rows_skipped': 0,
                'status': 'file_not_found'
            }
        
        self.logger.log_info(f"Starting import of {table_name} from {csv_filepath}")
        
        # Get column information
        columns = self.get_table_columns(table_name)
        column_names = [col['name'] for col in columns]
        column_list = ', '.join([f'"{col}"' for col in column_names])
        
        # Get primary key columns for ON CONFLICT
        pk_columns = self._get_primary_key_columns(table_name)
        
        # Prepare INSERT statement
        placeholders = ', '.join(['%s'] * len(column_names))
        
        if on_conflict == 'do_nothing' and pk_columns:
            pk_list = ', '.join([f'"{pk}"' for pk in pk_columns])
            insert_sql = f"""
                INSERT INTO {self.schema}."{table_name}" ({column_list})
                VALUES ({placeholders})
                ON CONFLICT ({pk_list}) DO NOTHING
            """
        elif on_conflict == 'update' and pk_columns:
            pk_list = ', '.join([f'"{pk}"' for pk in pk_columns])
            update_list = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in column_names if col not in pk_columns])
            insert_sql = f"""
                INSERT INTO {self.schema}."{table_name}" ({column_list})
                VALUES ({placeholders})
                ON CONFLICT ({pk_list}) DO UPDATE SET {update_list}
            """
        else:
            insert_sql = f"""
                INSERT INTO {self.schema}."{table_name}" ({column_list})
                VALUES ({placeholders})
            """
        
        # Import data in batches
        rows_imported = 0
        rows_skipped = 0
        batch = []
        
        cursor = self.connection.connection.cursor()
        
        try:
            with open(csv_filepath, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                
                # Read header row to get CSV column names
                try:
                    csv_header = next(reader)
                except StopIteration:
                    # Empty file
                    return {
                        'table': table_name,
                        'rows_imported': 0,
                        'rows_skipped': 0,
                        'status': 'empty'
                    }
                
                # Create mapping from CSV columns to table columns
                csv_to_table_mapping = {}
                for csv_idx, csv_col_name in enumerate(csv_header):
                    # Find matching column in table
                    for tbl_idx, col_info in enumerate(columns):
                        if col_info['name'] == csv_col_name:
                            csv_to_table_mapping[csv_idx] = tbl_idx
                            break
                
                row_number = 1  # Start at 1 (header is row 0)
                for row in reader:
                    row_number += 1
                    # Deserialize row - map CSV columns to table columns
                    deserialized_row = [None] * len(columns)  # Initialize with NULLs
                    has_null_violation = False
                    null_violation_columns = []
                    
                    for csv_idx, value in enumerate(row):
                        if csv_idx not in csv_to_table_mapping:
                            continue  # Skip columns not in target table
                        
                        tbl_idx = csv_to_table_mapping[csv_idx]
                        col_info = columns[tbl_idx]
                        
                        # Handle empty strings (NULL)
                        if value == '':
                            deserialized_row[tbl_idx] = None
                            # Check NOT NULL constraint
                            if col_info['nullable'] == 'NO' and col_info['default'] is None:
                                has_null_violation = True
                                null_violation_columns.append(col_info['name'])
                        # Handle JSON/JSONB
                        elif col_info['data_type'] in ('json', 'jsonb') or col_info['udt_name'] in ('json', 'jsonb'):
                            try:
                                deserialized_row[tbl_idx] = json.loads(value)
                            except:
                                deserialized_row[tbl_idx] = value
                        # Handle arrays
                        elif col_info['data_type'] == 'ARRAY' or col_info['udt_name'].startswith('_'):
                            try:
                                deserialized_row[tbl_idx] = json.loads(value)
                            except:
                                deserialized_row[tbl_idx] = value
                        # Handle boolean
                        elif col_info['data_type'] == 'boolean':
                            deserialized_row[tbl_idx] = value in ('t', 'true', 'True', '1', 'yes')
                        # Handle numeric types
                        elif col_info['data_type'] in ('integer', 'bigint', 'smallint'):
                            try:
                                deserialized_row[tbl_idx] = int(value)
                            except:
                                deserialized_row[tbl_idx] = None
                        elif col_info['data_type'] in ('numeric', 'decimal', 'real', 'double precision'):
                            try:
                                deserialized_row[tbl_idx] = float(value)
                            except:
                                deserialized_row[tbl_idx] = None
                        # Other types
                        else:
                            deserialized_row[tbl_idx] = value
                    
                    # Skip row if it violates NOT NULL constraints
                    if has_null_violation:
                        rows_skipped += 1
                        if rows_skipped <= 5:  # Log first 5 violations
                            self.logger.log_warning(
                                f"Row {row_number} skipped: NULL value in NOT NULL column(s): {', '.join(null_violation_columns)}"
                            )
                        continue
                    
                    batch.append(tuple(deserialized_row))
                    
                    # Execute batch
                    if len(batch) >= batch_size:
                        try:
                            import psycopg2.extras
                            psycopg2.extras.execute_batch(cursor, insert_sql, batch, page_size=len(batch))
                            self.connection.connection.commit()
                            rows_imported += len(batch)
                        except Exception as e:
                            self.logger.log_warning(f"Batch insert failed: {str(e)[:200]}")
                            self.connection.connection.rollback()
                            
                            # Try inserting one by one with detailed logging
                            for row_idx, single_row in enumerate(batch):
                                try:
                                    cursor.execute(insert_sql, single_row)
                                    self.connection.connection.commit()
                                    rows_imported += 1
                                except Exception as row_error:
                                    self.connection.connection.rollback()
                                    rows_skipped += 1
                                    # Log first 5 skipped rows with details
                                    if rows_skipped <= 5:
                                        # Show first few values for debugging
                                        sample_values = str(single_row[:5])[:100]
                                        self.logger.log_error(
                                            f"Row {rows_imported + rows_skipped} failed: {str(row_error)[:150]}. "
                                            f"Sample values: {sample_values}"
                                        )
                        
                        batch = []
                        
                        if progress_callback:
                            progress_callback(rows_imported + rows_skipped)
            
            # Insert remaining rows
            if batch:
                try:
                    import psycopg2.extras
                    psycopg2.extras.execute_batch(cursor, insert_sql, batch, page_size=len(batch))
                    self.connection.connection.commit()
                    rows_imported += len(batch)
                except Exception as e:
                    self.logger.log_warning(f"Final batch insert failed: {str(e)[:200]}")
                    self.connection.connection.rollback()
                    
                    # Try inserting one by one with detailed logging
                    for row_idx, single_row in enumerate(batch):
                        try:
                            cursor.execute(insert_sql, single_row)
                            self.connection.connection.commit()
                            rows_imported += 1
                        except Exception as row_error:
                            self.connection.connection.rollback()
                            rows_skipped += 1
                            # Log first 5 skipped rows with details
                            if rows_skipped <= 5:
                                # Show first few values for debugging
                                sample_values = str(single_row[:5])[:100]
                                self.logger.log_error(
                                    f"Row {rows_imported + rows_skipped} failed: {str(row_error)[:150]}. "
                                    f"Sample values: {sample_values}"
                                )
                
                if progress_callback:
                    progress_callback(rows_imported + rows_skipped)
            
            cursor.close()
            
            self.logger.log_info(f"Successfully imported {rows_imported:,} rows into {table_name} ({rows_skipped:,} skipped)")
            
            return {
                'table': table_name,
                'rows_imported': rows_imported,
                'rows_skipped': rows_skipped,
                'status': 'success'
            }
            
        except Exception as e:
            cursor.close()
            self.logger.log_error(f"Error importing {table_name}: {str(e)}")
            return {
                'table': table_name,
                'rows_imported': rows_imported,
                'rows_skipped': rows_skipped,
                'status': 'error',
                'error': str(e)
            }
    
    def _get_primary_key_columns(self, table_name: str) -> List[str]:
        """Get primary key column names for a table"""
        cursor = self.connection.connection.cursor()
        
        try:
            # Get table OID
            cursor.execute(f"""
                SELECT c.oid
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = '{self.schema}'
                AND c.relname = '{table_name}'
            """)
            
            oid_result = cursor.fetchone()
            if not oid_result:
                return []
            
            table_oid = oid_result[0]
            
            # Get primary key columns
            cursor.execute(f"""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = {table_oid}
                AND i.indisprimary
                ORDER BY a.attnum
            """)
            
            pk_columns = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return pk_columns
            
        except Exception as e:
            cursor.close()
            self.logger.log_warning(f"Could not get primary key for {table_name}: {str(e)}")
            return []

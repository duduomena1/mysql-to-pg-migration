from dbmigrator.migration_logging.log import MigrationLogger
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_access.metadata_models import Table, Column, Constraint, Index, Partition


def mysql_fetch_tables(mysql: MySQLConnection, excluded_tables=[]) -> list[Table]:
    table_data: list[Table] = []
    for table in mysql_database_info(mysql):
        if table not in excluded_tables:
            table_data.append(mysql_metadata_table(mysql, table))
    return table_data


def mysql_database_info(mysql: MySQLConnection) -> list[str]:
    try:
        with mysql.connection.cursor(dictionary=False) as cursor:

            sql = f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{mysql.database}' ORDER BY TABLE_NAME ASC"
            MigrationLogger().log_info(f"Query: {sql}")

            cursor.execute(sql)

            # Fetch all the rows in a list of lists.
            return [table[0] for table in cursor.fetchall()]


    except Exception as e:
        MigrationLogger().log_error(f"Error searching metadata for database {mysql.database}: {e}")
        raise e


def mysql_metadata_table(mysql: MySQLConnection, table_name) -> Table:
    try:
        table = fetch_table_info(mysql, table_name)
        if table is None:
            return None
        
        sequence = fetch_sequence_info(mysql, table_name)

        columns = fetch_columns_info(mysql, table_name)
        # if columns is None:
        #     return None
        
        constraints = fetch_constraints_info(mysql, table_name)
        
        # if constraints is None:
        #     return None
        
        indexes = fetch_indexes_info(mysql, table_name)
        
        # if indexes is None:
        #     return None

        partitions = fetch_partitions_info(mysql, table_name)
        
        # if partitions is None:
        #     return None
        
        table.num_sequence = sequence
        table.partitions = partitions
        table.columns = columns
        table.constraints = sorted(
            constraints,
            key=lambda idx: 0 if idx.name.lower() == "primary" else 1
        )

        constraint_names = {c.name for c in constraints}
        filteredIndexes = [
            index for index in indexes if index.name not in constraint_names
        ]
        table.indexes = filteredIndexes

        return table
    except Exception as e:
        MigrationLogger().log_error(f"Error searching metadata for table {mysql.database}.{table_name}: {e}")
        raise e


def fetch_table_info(mysql: MySQLConnection, table_name) -> Table:
    try:

        cursor = mysql.connection.cursor(dictionary=True)

        try:
            sql = f"""
            SELECT COUNT(*) as num_tuples FROM {mysql.database}.{table_name};
            """
            MigrationLogger().log_info(f"Query: {sql}")
            cursor.execute(sql)
            result = cursor.fetchone()
            num_tuples = result['num_tuples']
            table = Table(name=table_name, num_tuples=num_tuples)
            return table
        finally:
            MigrationLogger().log_info(f"Closing the {mysql.database}.{table_name} table count cursor")
            cursor.close()
    except Exception as e:
        MigrationLogger().log_error(f"Error searching metadata for table {mysql.database}.{table_name}: {e}")
        raise e


def fetch_columns_info(mysql: MySQLConnection, table_name) -> list[Column]:
    try:
        # Consulta para obter informações sobre as colunas da tabela
        sql = f"""
        DESCRIBE {mysql.database}.{table_name};
        """
        MigrationLogger().log_info(f"Query: {sql}")

        cursor = mysql.connection.cursor(dictionary=True)

        columns: list[Column] = []
        try:
            cursor.execute(sql)
            for row in cursor.fetchall():
                column_name = row['Field']
                data_type = row['Type']
                nullable = row['Null'] == 'YES'
                default = row['Default']
                extra = row['Extra']
                
                # Filtrar colunas inválidas (comentários SQL ou nomes estranhos)
                # Ignorar silenciosamente sem adicionar à lista
                if not column_name or column_name.strip().startswith('--') or column_name.strip().startswith('/*') or 'for debian' in column_name.lower() or 'mariadb dump' in column_name.lower():
                    continue
                
                column = Column(name=column_name, data_type=data_type, nullable=nullable, default=default, extra=extra or None)
                columns.append(column)
            return columns
        finally:
            cursor.close()
    except Exception as e:
        MigrationLogger().log_error(f"Error fetching columns info for table {mysql.database}.{table_name}: {e}")
        raise e


def fetch_constraints_info(mysql: MySQLConnection, table_name) -> list[Constraint]:
    try:
        # Consulta para obter informações sobre as constraints da tabela
        sql = f"""
        SELECT CONSTRAINT_NAME, GROUP_CONCAT(COLUMN_NAME) as COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_NAME = '{table_name}' AND TABLE_SCHEMA = '{mysql.database}'
        GROUP BY CONSTRAINT_NAME
        ORDER BY COLUMN_NAME;
        """
        MigrationLogger().log_info(f"Query: {sql}")

        cursor = mysql.connection.cursor(dictionary=True)

        constraints: list[Constraint] = []
        try:
            cursor.execute(sql)
            for row in cursor.fetchall():
                print('rooow', row)
                constraint_name = row['CONSTRAINT_NAME']
                column_name = row['COLUMN_NAME']
                referenced_table_schema = row['REFERENCED_TABLE_SCHEMA']
                referenced_table_name = row['REFERENCED_TABLE_NAME']
                referenced_column_name = row['REFERENCED_COLUMN_NAME']
                constraint = Constraint(name=constraint_name, column_name=column_name,
                                        referenced_table_schema=referenced_table_schema,
                                        referenced_table_name=referenced_table_name,
                                        referenced_column_name=referenced_column_name)
                constraints.append(constraint)
            return constraints
        finally:
            cursor.close()
    except Exception as e:
        MigrationLogger().log_error(f"Error fetching constraints info for table {mysql.database}.{table_name}: {e}")
        raise e


def fetch_indexes_info(mysql: MySQLConnection, table_name) -> list[Index]:
    try:
        # Consulta para obter informações sobre os índices da tabela
        sql = f"""
        SELECT INDEX_NAME, GROUP_CONCAT(COLUMN_NAME) as COLUMN_NAME, NULLABLE, INDEX_TYPE, NON_UNIQUE
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_NAME = '{table_name}' AND TABLE_SCHEMA = '{mysql.database}' GROUP BY INDEX_NAME;
        """
        MigrationLogger().log_info(f"Query: {sql}")

        cursor = mysql.connection.cursor(dictionary=True)

        indexes: list[Index] = []
        try:
            cursor.execute(sql)
            for row in cursor.fetchall():
                index_name = row['INDEX_NAME']
                column_name = row['COLUMN_NAME']
                nullable = row['NULLABLE'] == 'YES'
                index_type = row['INDEX_TYPE']
                non_unique = row['NON_UNIQUE']
                index = Index(name=index_name, column_name=column_name, nullable=nullable,
                              index_type=index_type, non_unique=non_unique, excluded=False)
                indexes.append(index)
            return indexes
        finally:
            cursor.close()
    except Exception as e:
        MigrationLogger().log_error(f"Error fetching indexes info for table {mysql.database}.{table_name}: {e}")
        raise e
    

def fetch_partitions_info(mysql: MySQLConnection, table_name) -> list[Partition]:
    try:
        # Consulta para obter informações sobre os índices da tabela
        sql = f"""
        SELECT PARTITION_ORDINAL_POSITION,PARTITION_NAME,PARTITION_METHOD,PARTITION_EXPRESSION,PARTITION_DESCRIPTION
        FROM INFORMATION_SCHEMA.PARTITIONS
        WHERE TABLE_NAME = '{table_name}' AND TABLE_SCHEMA = '{mysql.database}' ORDER BY PARTITION_ORDINAL_POSITION ASC;
        """
        MigrationLogger().log_info(f"Query: {sql}")

        cursor = mysql.connection.cursor(dictionary=True)

        partitions: list[Partition] = []
        try:
            cursor.execute(sql)
            for row in cursor.fetchall():
                position = row['PARTITION_ORDINAL_POSITION']
                name = row['PARTITION_NAME']
                method = row['PARTITION_METHOD']
                expression = row['PARTITION_EXPRESSION']
                description = row['PARTITION_DESCRIPTION']

                if (position is not None):
                    partition = Partition(position=position,name=name,method=method,description=description,expression=expression)
                    partitions.append(partition)
                    
            return partitions
        finally:
            cursor.close()
    except Exception as e:
        MigrationLogger().log_error(f"Error fetching partitions info for table {mysql.database}.{table_name}: {e}")
        raise e


def fetch_sequence_info(mysql: MySQLConnection, table_name) -> Table:
    try:

        cursor = mysql.connection.cursor(dictionary=True)
        columns = []
        try:
            sql = f"""
            SELECT COLUMN_NAME as column_name
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = '{mysql.database}'
                AND TABLE_NAME = '{table_name}' 
                AND CONSTRAINT_NAME = 'PRIMARY'
                AND COLUMN_NAME IN (
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = '{mysql.database}' 
                    AND TABLE_NAME = '{table_name}' 
                    AND DATA_TYPE = 'int' 
                    AND COLUMN_KEY = 'PRI'
                )
            """
            MigrationLogger().log_info(f"Query: {sql}")
            cursor.execute(sql)
            result = cursor.fetchone()
            
            if result:
                column_name = result['column_name']
                columns.append(column_name)
                # Importante: usar crases para identificar o nome da coluna/tabela no MySQL.
                # Aspas duplas fariam a expressão ser interpretada como string literal (ex.: MAX("id") -> "id"),
                # causando ValueError ao converter para int.
                sql = f"""
                SELECT COALESCE(MAX(`{column_name}`), 1) as num_sequence FROM `{mysql.database}`.`{table_name}`;
                """
                MigrationLogger().log_info(f"Query: {sql}")
                cursor.execute(sql)
                result = cursor.fetchone()
                num_sequence = int(result['num_sequence'])

                return num_sequence
            else:
                return -1

        finally:
            print('UNIQUE SEQ', list(set(columns)))
            MigrationLogger().log_info(f"Closing the {mysql.database}.{table_name} table max id cursor")
            cursor.close()
    except Exception as e:
        MigrationLogger().log_error(f"Error searching metadata for table {mysql.database}.{table_name}: {e}")
        raise e
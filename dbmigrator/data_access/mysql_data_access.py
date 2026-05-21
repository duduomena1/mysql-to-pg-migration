from dbmigrator.migration_logging.log import MigrationLogger

class MySQLTableIterator:
    def __init__(self, mysql, table, batch_size=10000, where_clause=None, where_params=None, skip_count=False, offset=0):
        self.mysql = mysql
        self.table = table
        self.batch_size = batch_size
        self.cursor = None
        self.current_batch = []
        
        # Novos parâmetros para migração parcial
        self.where_clause = where_clause
        self.where_params = where_params or []
        self.skip_count = skip_count
        self.offset = offset
        self.current_offset = offset

        self.columns = []
        for column in self.table.columns:
            if column.data_type.lower() == 'geometry' or column.data_type.lower() == 'polygon':
                self.columns.append(f"ST_AsText(`{column.name}`) AS `{column.name}`")
            elif column.data_type.lower() == 'point':
                #self.columns.append(f"`{column.name}`")
                self.columns.append(f"ST_AsText(`{column.name}`) AS `{column.name}`")
            else:
                self.columns.append(f"`{column.name}`")

        self.columns = ", ".join(self.columns)

    def __iter__(self):
        return self

    def __next__(self):
        if self.cursor is None:
            self.cursor = self.mysql.connection.cursor(buffered=False)
            database = self.mysql.connection.database
            if database != "":
                database += "."
            
            # Construir query base
            sql = f"SELECT {self.columns} FROM {database}{self.table.name}"
            
            # Adicionar WHERE clause se fornecida (para migração parcial)
            if self.where_clause:
                sql += f" WHERE {self.where_clause}"
            
            # Adicionar LIMIT/OFFSET para retomada (migração parcial)
            if self.offset > 0:
                sql += f" LIMIT {self.batch_size} OFFSET {self.current_offset}"
            
            MigrationLogger().log_info(f"Query: {sql}")
            
            # Executar com parâmetros se fornecidos
            if self.where_params:
                self.cursor.execute(sql, self.where_params)
            else:
                self.cursor.execute(sql)

        if not self.current_batch:
            self.current_batch = self.cursor.fetchmany(self.batch_size)
            if not self.current_batch:
                self.cursor.close()
                raise StopIteration
            
            # Atualizar offset para próximo batch (se usando offset)
            if self.offset > 0:
                self.current_offset += self.batch_size

        row = self.current_batch.pop(0)
        return row

    def close(self):
        if self.cursor:
            # Consumir resultados não lidos antes de fechar
            try:
                while self.cursor.nextset():
                    pass
            except:
                pass
            finally:
                self.cursor.close()

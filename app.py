from dbmigrator.configuration_management.db_credentials import  mysql_credentials, postgres_credentials
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection
from dbmigrator.data_access.postgresql_data_access import postgres_execute_DDL

from dbmigrator.configuration_management.configuration import MigrationConfig
from dbmigrator.migration_logging.log import MigrationLogger
from dbmigrator.data_migration.mysql_to_postgresql import MySQLToPostgreSQL
from dbmigrator.configuration_management.utils import postgresql_GIST_indexes
from dbmigrator.structure_conversion.csv_utils import folder_name
from dbmigrator.structure_conversion.table_to_json import table_to_json, save_migration_order, load_migration_order
from dbmigrator.migration_logging.progress_log.tables_log import TablesLog
from dbmigrator.data_access.postgresql_metadata_access import PostgreSQLTableManager
from dbmigrator.structure_conversion.dependency_resolver import DependencyResolver


from flask import Flask, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

import os
import shutil
import io
import time

import traceback
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.console import Console

app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas as rotas
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')  # Configurar CORS para SocketIO

migration_config = None
config_path = "config.json"

if os.path.exists(config_path):
    migration_config = MigrationConfig.from_json_file(config_path)
    MigrationLogger().log_info(f"Loaded configuration from file")
else:
    migration_config = MigrationConfig.default_config()
    migration_config.save_to_file(config_path)
    MigrationLogger().log_info(f"Loaded default configuration")


migration = MySQLToPostgreSQL(None, None)

@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    #print('Client connected')
    pass


@socketio.on('test_connections')
def handle_test_connections():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    STATUS = {
        'mysql': status_mysql,
        'postgres': status_postgres
    }
    socketio.emit('status', (STATUS))

@socketio.on('configure')
def handle_configurations(configurations):
    if configurations is not None:
        migration_config.schema_name = configurations['schema_name']
        migration_config.postgres_bulk_size = configurations['postgres_bulk_size']
        migration_config.mysql_batch_size = configurations['mysql_batch_size']
        migration_config.save_to_file(config_path)
        MigrationLogger().log_info(f"Config File Updated")
    STATUS = {
       'configure': {
            'schema_name': migration_config.schema_name,
            'postgres_bulk_size': migration_config.postgres_bulk_size,
            'mysql_batch_size': migration_config.mysql_batch_size,
        }
    }
    socketio.emit('status', (STATUS))

@socketio.on('generate_migration_order')
def handle_generate_migration_order():
    """
    Gera a ordem de migração baseada nas dependências de Foreign Keys.
    Salva o resultado em migration_order.json
    """
    try:
        if not migration.tables:
            migration.load_mysql_metadata_json(migration_config.json_name)
        
        if migration.tables:
            # Cria o resolver de dependências
            resolver = DependencyResolver(migration.tables)
            
            # Gera a ordem de migração
            excluded_tables = set(migration.excluded_tables) if migration.excluded_tables else set()
            migration_order = resolver.get_migration_order(excluded_tables)
            
            # Salva a ordem de migração
            save_migration_order(migration_order, "migration_order.json")
            
            # Gera análise de dependências
            analysis = resolver.analyze_dependencies()
            
            MigrationLogger().log_info(f"Migration order generated with {len(migration_order)} tables")
            MigrationLogger().log_info(f"Root tables (no dependencies): {analysis['root_tables']}")
            if analysis['circular_dependencies']:
                MigrationLogger().log_warning(f"Circular dependencies found: {analysis['circular_dependencies']}")
            
            STATUS = {
                'migration_order_generated': True,
                'total_tables': len(migration_order),
                'analysis': analysis
            }
            socketio.emit('status', STATUS)
        else:
            MigrationLogger().log_error("No tables loaded to generate migration order")
            socketio.emit('status', {'migration_order_generated': False, 'error': 'No tables loaded'})
            
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error generating migration order: {str(e)}")
        socketio.emit('status', {'migration_order_generated': False, 'error': str(e)})

@socketio.on('load_metadata')
def handle_load_metadata(reload):
    if reload:
        mysql, status_mysql = open_mysql_connection()
        postgres, status_postgres = open_postgres_connection()
        open_migration(mysql, postgres)
        if not mysql:
            return
        migration.load_mysql_metadata_json(migration_config.json_name)

        try:
            if mysql:
                mysql.close()
            if postgres:
                postgres.close()
        except Exception as e:
            pass

    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))
    elif reload is None:
        MigrationLogger().log_warning(f"Table metadata missing; conversion step may have been skipped.")
        STATUS = {'tables': []}
        socketio.emit('status', (STATUS))

@socketio.on('update_table_metadata')
def handle_update_table_metadata(table):
    table_name = None
    excluded = None
    if table:
        table_name = table['name']
        excluded = table['excluded']
        type_t = table['type']

    if table_name and migration.tables:
        for t in migration.tables:
            if t.name == table_name:
                #t.excluded = excluded
                if type_t is not None:
                    type_t = str(type_t)
                    #value = getattr(t, type_t)
                    setattr(t, type_t, False)
                    #t.excluded = True
                else:
                    t.excluded = excluded

                break

        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))



@socketio.on('update_table_metadata_select_all')
def handle_update_table_metadata_select_all():
    if migration.tables:
        json_list = []
        for table in migration.tables:
            table.excluded = False
            json_list.append(table_to_json(table))

        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)
        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))
    else:
        MigrationLogger().log_warning(f"Table metadata missing")

@socketio.on('update_table_metadata_deselect_all')
def handle_update_table_metadata_deselect_all():
    if migration.tables:
        json_list = []
        for table in migration.tables:
            table.excluded = True
            json_list.append(table_to_json(table))

        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)
        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))
    else:
        MigrationLogger().log_warning(f"Table metadata missing")


@socketio.on('handle_sequences')
def handle_sequences(table, new_value):
    if migration.tables:
        for t in migration.tables:
            if t.name == table:
                postgres, status_postgres = open_postgres_connection()
                if not postgres:
                    return

                pg_manager = PostgreSQLTableManager(postgres, t.name, schema=migration_config.schema_name)

                if new_value is None:
                    new_value = pg_manager.get_sequence_current_value()
                else:
                    pg_manager.set_sequence_value(new_value)

                if postgres:
                    postgres.close()

                socketio.emit('update_sequence', (table, new_value) )
                return

        MigrationLogger().log_info(f"Table: {table} not found in metadata")
    else:
        MigrationLogger().log_warning(f"Table metadata missing")

@socketio.on('handle_specific_index')
def handle_specific_index(table_name, index_name, excluded):
    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
            if table.name == table_name:
                for index in table.indexes:
                    if index.name == index_name:
                        index.excluded = excluded
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)
        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))
    else:
        MigrationLogger().log_warning(f"Table metadata missing")

@socketio.on('clear_metadata')
def handle_clear_metadata():

    if os.path.exists(migration_config.json_name):
        MigrationLogger().log_warning(f"Clearing metadata file: {migration_config.json_name}")
        os.remove(migration_config.json_name)
    else:
        MigrationLogger().log_warning(f"File {migration_config.json_name} does not exist")

    if os.path.exists(migration_config.progress_json_name):
        MigrationLogger().log_warning(f"Clearing metadata file: {migration_config.progress_json_name}")
        os.remove(migration_config.progress_json_name)
    else:
        MigrationLogger().log_warning(f"File {migration_config.progress_json_name} does not exist")

    migration.tables = []
    STATUS = {'tables': []}
    socketio.emit('status', (STATUS))


@socketio.on('clear_files')
def handle_clear_files():
    if os.path.exists(folder_name):
        MigrationLogger().log_warning(f"Clearing folder: {folder_name}")
        shutil.rmtree(folder_name)
    else:
        MigrationLogger().log_warning(f"Folder {folder_name} does not exist")


@socketio.on('clear_database')
def handle_clear_files():
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        MigrationLogger().log_error(f"Could not connect to Postgres")
        return

    if migration_config.schema_name:
        postgres_execute_DDL(postgres, "DROP SCHEMA IF EXISTS " + migration_config.schema_name + " CASCADE;")
        postgres_execute_DDL(postgres, "CREATE SCHEMA " + migration_config.schema_name + ";")
        postgres.connection.commit()
    else:
        MigrationLogger().log_warning(f"Target schema name not set")

    try:
        if postgres:
            postgres.close()
    except Exception as e:
        pass

@socketio.on('migrate_tables')
def handle_migrate_tables():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        return
    open_migration(mysql, postgres)
    #migration.load_mysql_metadata_json(migration_config.json_name)
    table_sql_error = ""
    enum_sql_error = ""
    table_name_error = ""
    try:
        if migration.tables:
            for t in migration.tables:
                if t.excluded is False and t.table_commited is False:
                    table_name_error = t.name
                    table_sql, enum_sql, constraints, primary_keys, indexes, sequences = migration.table_to_sql(table=t, schema=migration_config.schema_name, buffer=False)
                    table_sql_error = table_sql
                    enum_sql_error = enum_sql
                    #MigrationLogger().log_error(f"sql: {enum_sql_error} {table_sql_error}")

                    if enum_sql is not None and enum_sql != "":
                        postgres_execute_DDL(postgres, enum_sql)
                    postgres_execute_DDL(postgres, table_sql)
                    postgres.connection.commit()
                    t.table_commited = True
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error migrating table [{table_name_error}] sql: {enum_sql_error} {table_sql_error} -> {str(e)}")

    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))

@socketio.on('migrate_primary_keys')
def handle_migrate_primary_keys():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        return
    open_migration(mysql, postgres)
    #migration.load_mysql_metadata_json(migration_config.json_name)
    primary_keys_error = ""
    table_name_error = ""
    try:
        if migration.tables:
            for t in migration.tables:
                if t.excluded is False and t.primary_key_commited is False:
                    table_name_error = t.name
                    table_sql, enum_sql, constraints, primary_keys, indexes, sequences = migration.table_to_sql(table=t, schema=migration_config.schema_name, buffer=False)


                    primary_keys_error = primary_keys
                    if primary_keys is not None and primary_keys != "":
                        postgres_execute_DDL(postgres, primary_keys)
                    postgres.connection.commit()
                    t.primary_key_commited = True
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error migrating primary key [{table_name_error}] sql: {primary_keys_error} -> {str(e)}")

    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))

@socketio.on('migrate_constraints')
def handle_migrate_constraints():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        return
    open_migration(mysql, postgres)
    #migration.load_mysql_metadata_json(migration_config.json_name)
    constraints_error = ""
    table_name_error = ""
    constraints_names_already_used = []
    try:
        if migration.tables:
            for t in migration.tables:
                if t.excluded is False and t.constraints_commited is False:
                    table_name_error = t.name
                    table_sql, enum_sql, constraints, primary_keys, indexes, sequences = migration.table_to_sql(table=t, schema=migration_config.schema_name, buffer=False, constraints_names_already_used=constraints_names_already_used)

                    constraints_error = constraints
                    if constraints is not None and constraints != "":
                        postgres_execute_DDL(postgres, constraints)
                    postgres.connection.commit()
                    t.constraints_commited = True
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error migrating constraint [{table_name_error}] sql: {constraints_error} -> {str(e)}")

    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))

@socketio.on('migrate_indexes')
def handle_migrate_indexes():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        return
    open_migration(mysql, postgres)
    #migration.load_mysql_metadata_json(migration_config.json_name)
    indexes_error = ""
    table_name_error = ""
    try:
        if migration.tables:
            for t in migration.tables:
                if t.excluded is False and t.indexes_commited is False:
                    table_name_error = t.name
                    table_sql, enum_sql, constraints, primary_keys, indexes, sequences = migration.table_to_sql(table=t, schema=migration_config.schema_name, buffer=False)
                    indexes_error = indexes
                    if indexes is not None and indexes != "":
                        postgres_execute_DDL(postgres, indexes)
                    postgres.connection.commit()
                    t.indexes_commited = True
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error migrating index [{table_name_error}] sql: {indexes_error} -> {str(e)}")

    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))

@socketio.on('migrate_tuples')
def handle_migrate_tuples():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        return
    open_migration(mysql, postgres)

    tuples_error = ""
    table_name_error = ""
    
    # Calcular total de tuplas a migrar
    migration_order = load_migration_order("migration_order.json")
    tables_to_migrate = []
    total_tuples = 0
    
    # Silenciar logs do console durante a migração (para não interferir com Rich Progress)
    import logging
    logging.getLogger("DBMigrator").setLevel(logging.ERROR)
    
    MigrationLogger().log_info("Starting tuple migration with Rich Progress")
    
    try:
        if migration.tables:
            if migration_order:
                MigrationLogger().log_info(f"Using migration order from migration_order.json with {len(migration_order)} tables")
                table_dict = {table.name: table for table in migration.tables}
                
                for order_info in migration_order:
                    table_name = order_info['table_name']
                    if table_name in table_dict:
                        t = table_dict[table_name]
                        table_log = TablesLog().get_table(t.name)
                        if t.excluded is False and table_log.fully_migrated is False:
                            tables_to_migrate.append((t, order_info))
                            total_tuples += t.num_tuples
            else:
                MigrationLogger().log_warning("migration_order.json not found, using original table order")
                for t in migration.tables:
                    table_log = TablesLog().get_table(t.name)
                    if t.excluded is False and table_log.fully_migrated is False:
                        tables_to_migrate.append((t, None))
                        total_tuples += t.num_tuples
            
            MigrationLogger().log_info(f"Found {len(tables_to_migrate)} tables to migrate with {total_tuples} total tuples")
            
            if len(tables_to_migrate) == 0:
                MigrationLogger().log_warning("No tables to migrate")
                logging.getLogger("DBMigrator").setLevel(logging.INFO)  # Restaurar logs
                return
            
            # Criar StringIO para capturar saída do Rich para o frontend
            string_buffer = io.StringIO()
            console_web = Console(file=string_buffer, force_terminal=True, width=100, legacy_windows=False)
            
            # Console para o terminal do servidor
            console_terminal = Console(force_terminal=True, width=120)
            
            MigrationLogger().log_info("Rich Progress initialized - Dual output (Terminal + Web)")
            
            # Marcar tempo de início
            start_time = time.time()
            
            # Função auxiliar para enviar progresso para o frontend
            def send_progress_to_frontend():
                """Envia o progresso atual para o frontend via WebSocket"""
                # Forçar refresh do progress web
                progress_web.refresh()
                console_web.file.flush()
                
                # Capturar o buffer completo
                terminal_output = string_buffer.getvalue()
                
                # IMPORTANTE: Limpar o buffer para a próxima renderização
                # Isso evita acumular múltiplas renderizações
                string_buffer.truncate(0)
                string_buffer.seek(0)
                
                if terminal_output:
                    # Remover linhas vazias extras e manter apenas as últimas linhas relevantes
                    lines = terminal_output.split('\n')
                    # Filtrar linhas vazias
                    lines = [line for line in lines if line.strip()]
                    # Pegar apenas as últimas 10 linhas (ajustável)
                    lines = lines[-10:] if len(lines) > 10 else lines
                    terminal_output = '\n'.join(lines)
                    
                    socketio.emit('rich_terminal', {
                        'output': terminal_output,
                        'action': 'update'
                    })
                    socketio.sleep(0)  # Permite que o eventlet processe o evento
            
            # Iniciar Rich Progress com console para o TERMINAL
            with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console_terminal,
                refresh_per_second=4
            ) as progress_terminal:
                
                # Iniciar Rich Progress com console para o FRONTEND
                with Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(bar_width=40),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=console_web,
                    refresh_per_second=4
                ) as progress_web:
                    
                    # Adicionar tasks em ambos os progress bars
                    overall_task_terminal = progress_terminal.add_task(f"[cyan]Migrando {len(tables_to_migrate)} tabelas ({total_tuples:,} tuplas)", total=total_tuples)
                    overall_task_web = progress_web.add_task(f"[cyan]Migrando {len(tables_to_migrate)} tabelas ({total_tuples:,} tuplas)", total=total_tuples)
                    
                    # Enviar output inicial
                    send_progress_to_frontend()
                    
                    socketio.emit('rich_terminal', {
                        'output': 'Iniciando migração...\n',
                        'action': 'start'
                    })
                    socketio.sleep(0)
                    
                    tuples_migrated = 0
                    
                    for idx, (t, order_info) in enumerate(tables_to_migrate, 1):
                        table_name_error = t.name
                        
                        # Atualizar descrição da tarefa em AMBOS os progress
                        progress_terminal.update(overall_task_terminal, description=f"[cyan]Tabela {idx}/{len(tables_to_migrate)}: [bold]{t.name}[/bold] ({t.num_tuples:,} tuplas)")
                        progress_web.update(overall_task_web, description=f"[cyan]Tabela {idx}/{len(tables_to_migrate)}: [bold]{t.name}[/bold] ({t.num_tuples:,} tuplas)")
                        send_progress_to_frontend()
                        
                        # Rastrear progresso da tabela atual
                        table_start_progress = tuples_migrated
                        last_callback_value = 0
                        
                        # Callbacks de progresso
                        def progress_file_callback(prog):
                            # Não atualizar barra durante escrita do CSV (muito rápido)
                            pass
                        
                        def progress_migration_callback(prog):
                            nonlocal last_callback_value
                            
                            # Calcular quantas tuplas foram adicionadas desde o último callback
                            tuplas_novas = prog - last_callback_value
                            last_callback_value = prog
                            
                            # Atualizar a barra com o número exato de tuplas novas
                            progress_terminal.update(overall_task_terminal, advance=tuplas_novas)
                            progress_web.update(overall_task_web, advance=tuplas_novas)
                            
                            # Enviar update para frontend a cada 5000 registros (bulk_size)
                            if prog % migration_config.postgres_bulk_size == 0 or prog == t.num_tuples:
                                send_progress_to_frontend()
                        
                        # Migrar tabela
                        migration.save_table_to_csv(t, progress_file_callback)
                        migration.read_from_csv(t, migration_config.schema_name, progress_migration_callback)
                        
                        # GARANTIR que a barra completou 100% desta tabela
                        # (em caso de arredondamento ou último batch menor que bulk_size)
                        tuplas_desta_tabela = last_callback_value
                        if tuplas_desta_tabela < t.num_tuples:
                            diferenca = t.num_tuples - tuplas_desta_tabela
                            progress_terminal.update(overall_task_terminal, advance=diferenca)
                            progress_web.update(overall_task_web, advance=diferenca)
                        
                        t.tuples_commited = True
                        tuples_migrated += t.num_tuples
                        
                        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)
                        
                        json_list = []
                        for table in migration.tables:
                            json_list.append(table_to_json(table))
                        
                        STATUS = {'tables': json_list}
                        socketio.emit('status', (STATUS))
                        socketio.sleep(0)
                        
                        # Atualizar progresso final da tabela
                        send_progress_to_frontend()
                    
                    # Calcular tempo total
                    end_time = time.time()
                    total_time = end_time - start_time
                    
                    # Formatar tempo total (HH:MM:SS)
                    hours = int(total_time // 3600)
                    minutes = int((total_time % 3600) // 60)
                    seconds = int(total_time % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    
                    # Emitir conclusão geral com tempo total
                    final_message = f"✓ Concluído! {len(tables_to_migrate)} tabelas ({total_tuples:,} tuplas) - Tempo: {time_str}"
                    progress_terminal.update(overall_task_terminal, description=f"[bold green]{final_message}")
                    progress_web.update(overall_task_web, description=f"[bold green]{final_message}")
                    progress_terminal.refresh()
                    send_progress_to_frontend()
                    
                    socketio.emit('rich_terminal', {
                        'output': f'\n{final_message}\n',
                        'action': 'complete'
                    })
                    socketio.sleep(0)
            
            # Restaurar logs do console
            logging.getLogger("DBMigrator").setLevel(logging.INFO)
            MigrationLogger().log_info(f"Migration completed successfully: {len(tables_to_migrate)} tables, {total_tuples} tuples in {time_str}")

    except Exception as e:
        # Restaurar logs em caso de erro
        logging.getLogger("DBMigrator").setLevel(logging.INFO)
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error migrating tuple [{table_name_error}] sql: {tuples_error} -> {str(e)}")

    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    # Atualização final do status
    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))



@socketio.on('migrate_sequences')
def handle_migrate_sequences():
    mysql, status_mysql = open_mysql_connection()
    postgres, status_postgres = open_postgres_connection()
    if not postgres:
        return
    open_migration(mysql, postgres)
    #migration.load_mysql_metadata_json(migration_config.json_name)
    sequences_error = ""
    table_name_error = ""
    try:
        if migration.tables:
            for t in migration.tables:
                if t.num_sequence >= 0: # Só inserir quando tiver valor 0 ou maior
                    if t.excluded is False and t.sequences_commited is False:
                        table_name_error = t.name
                        table_sql, enum_sql, constraints, primary_keys, indexes, sequences = migration.table_to_sql(table=t, schema=migration_config.schema_name, buffer=False)

                        sequences_error = sequences
                        if sequences is not None and sequences != "":
                            postgres_execute_DDL(postgres, sequences)
                        postgres.connection.commit()
                        t.sequences_commited = True
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error migrating sequences [{table_name_error}] sql: {sequences_error} -> {str(e)}")

    try:
        if mysql:
            mysql.close()
        if postgres:
            postgres.close()
    except Exception as e:
        pass

    if migration.tables:
        json_list = []
        for table in migration.tables:
            json_list.append(table_to_json(table))
        migration.save_mysql_metadata_json(migration.tables, migration_config.json_name)

        STATUS = {'tables': json_list}
        socketio.emit('status', (STATUS))




def open_mysql_connection():
    mysql_conn = MySQLConnection(mysql_credentials())
    status = {
        'MYSQL_DATABASE': mysql_conn.db_credentials.database,
        'MYSQL_USER': mysql_conn.db_credentials.user,
        'MYSQL_HOST': mysql_conn.db_credentials.host,
        'MYSQL_PORT': mysql_conn.db_credentials.port,
    }
    try:
        mysql_conn.create()
        status['connected'] = True if mysql_conn.connection else False
        return mysql_conn, status
    except Exception as e:
        status['connected'] = False
        status['error'] = str(e)
        return None, status

def open_postgres_connection():
    postgres_conn = PostgreSQLConnection(postgres_credentials())
    print('postgres_conn', vars(postgres_conn.db_credentials))
    status = {
        'POSTGRES_DBNAME': postgres_conn.db_credentials.database,
        'POSTGRES_USER': postgres_conn.db_credentials.user,
        'POSTGRES_HOST': postgres_conn.db_credentials.host,
        'POSTGRES_PORT': postgres_conn.db_credentials.port,
    }
    try:
        postgres_conn.create()
        status['connected'] = True if postgres_conn.connection else False
        return postgres_conn, status
    except Exception as e:
        status['connected'] = False
        status['error'] = str(e)
        return None, status



def open_migration(mysql, postgresql):

    migration.mysql_conn = mysql
    migration.postgres_conn = postgresql

    migration.GIST_indexes = postgresql_GIST_indexes()
    migration.bulk_commit = False #migration_config.bulk_commit
    migration.postgresql_bulk_size = migration_config.postgres_bulk_size
    migration.mysql_batch_size = migration_config.mysql_batch_size
    migration.excluded_tables = migration_config.excluded_tables

    return migration


# ============================================================================
# PARTIAL MIGRATION ENDPOINTS
# ============================================================================

@socketio.on('get_table_names_only')
def handle_get_table_names_only():
    """
    Retorna apenas os nomes das tabelas do banco MySQL.
    Query leve para popular dropdown inicial da aba Partial.
    """
    try:
        mysql, status_mysql = open_mysql_connection()
        if not mysql:
            MigrationLogger().log_error("Failed to connect to MySQL")
            socketio.emit('partial_table_names', {'success': False, 'error': 'MySQL connection failed'})
            return
        
        cursor = mysql.connection.cursor()
        database = mysql.connection.database
        
        query = f"""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = '{database}'
            ORDER BY TABLE_NAME
        """
        
        cursor.execute(query)
        tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        mysql.close()
        
        MigrationLogger().log_info(f"Found {len(tables)} tables in database")
        socketio.emit('partial_table_names', {'success': True, 'tables': tables})
        
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error fetching table names: {str(e)}")
        socketio.emit('partial_table_names', {'success': False, 'error': str(e)})


@socketio.on('get_table_columns_by_name')
def handle_get_table_columns_by_name(table_name):
    """
    Retorna apenas as colunas de tipo temporal (DATE, DATETIME, TIMESTAMP) de uma tabela específica.
    """
    try:
        if not table_name:
            socketio.emit('partial_table_columns', {'success': False, 'error': 'Table name not provided'})
            return
            
        mysql, status_mysql = open_mysql_connection()
        if not mysql:
            MigrationLogger().log_error("Failed to connect to MySQL")
            socketio.emit('partial_table_columns', {'success': False, 'error': 'MySQL connection failed'})
            return
        
        cursor = mysql.connection.cursor()
        database = mysql.connection.database
        
        query = f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = '{database}'
            AND TABLE_NAME = '{table_name}'
            AND DATA_TYPE IN ('date', 'datetime', 'timestamp')
            ORDER BY ORDINAL_POSITION
        """
        
        cursor.execute(query)
        columns = [{'name': row[0], 'type': row[1]} for row in cursor.fetchall()]
        cursor.close()
        mysql.close()
        
        MigrationLogger().log_info(f"Found {len(columns)} temporal columns in table {table_name}")
        socketio.emit('partial_table_columns', {'success': True, 'table': table_name, 'columns': columns})
        
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error fetching columns for table {table_name}: {str(e)}")
        socketio.emit('partial_table_columns', {'success': False, 'error': str(e)})


@socketio.on('reset_partial_progress')
def handle_reset_partial_progress(data):
    """
    Remove entrada específica do partial_progress.json para permitir reinício de migração.
    """
    try:
        import json
        
        table_name = data.get('table_name')
        if not table_name:
            socketio.emit('partial_reset_result', {'success': False, 'error': 'Table name not provided'})
            return
        
        progress_file = 'partial_progress.json'
        
        # Carrega progresso existente
        progress_data = {'migrations': []}
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
        
        # Filtra removendo entradas da tabela especificada que estão em progresso
        original_count = len(progress_data.get('migrations', []))
        progress_data['migrations'] = [
            m for m in progress_data.get('migrations', [])
            if not (m.get('table') == table_name and m.get('status') == 'in_progress')
        ]
        removed_count = original_count - len(progress_data['migrations'])
        
        # Salva de volta
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        MigrationLogger().log_info(f"Reset progress for table {table_name} - removed {removed_count} entries")
        socketio.emit('partial_reset_result', {'success': True, 'table': table_name, 'removed': removed_count})
        
    except Exception as e:
        print(traceback.print_exc())
        MigrationLogger().log_error(f"Error resetting progress: {str(e)}")
        socketio.emit('partial_reset_result', {'success': False, 'error': str(e)})


@socketio.on('migrate_partial_table')
def handle_migrate_partial_table(data):
    """
    Executa migração parcial de tabela com filtro temporal.
    Roda em thread separada para não bloquear a UI.
    """
    import eventlet
    from dbmigrator.data_migration.partial_table_migration import PartialTableMigrator
    
    def run_migration():
        mysql = None
        postgres = None
        
        try:
            # Validar parâmetros
            table_name = data.get('table_name')
            filter_column = data.get('filter_column')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            mysql_batch_size = int(data.get('mysql_batch_size', 5000))
            postgres_bulk_size = int(data.get('postgres_bulk_size', 5000))
            strategy = data.get('strategy', 'append')
            
            if not all([table_name, filter_column, start_date, end_date]):
                socketio.emit('partial_migration_result', {
                    'success': False,
                    'error': 'Missing required parameters'
                })
                return
            
            # Conectar aos bancos
            MigrationLogger().log_info(f"Connecting to databases for partial migration...")
            mysql, status_mysql = open_mysql_connection()
            postgres, status_postgres = open_postgres_connection()
            
            if not mysql or not postgres:
                socketio.emit('partial_migration_result', {
                    'success': False,
                    'error': 'Database connection failed'
                })
                return
            
            # Criar migrator
            migrator = PartialTableMigrator(
                mysql_conn=mysql,
                postgres_conn=postgres,
                schema_name=migration_config.schema_name
            )
            
            # Callback para enviar logs para frontend
            def progress_callback(message, level="INFO"):
                # Emitir log via rich terminal
                socketio.emit('rich_terminal', {
                    'output': f"{message}\n",
                    'action': 'append'
                })
                socketio.sleep(0)
            
            # Executar migração
            MigrationLogger().log_info(f"Starting partial migration: {table_name} WHERE {filter_column} BETWEEN {start_date} AND {end_date}")
            
            result = migrator.migrate_table_partial(
                table_name=table_name,
                filter_column=filter_column,
                start_date=start_date,
                end_date=end_date,
                mysql_batch_size=mysql_batch_size,
                postgres_bulk_size=postgres_bulk_size,
                strategy=strategy,
                progress_callback=progress_callback
            )
            
            # Emitir resultado
            socketio.emit('partial_migration_result', result)
            
        except Exception as e:
            error_msg = f"Error in partial migration: {str(e)}\n{traceback.format_exc()}"
            MigrationLogger().log_error(error_msg)
            print(error_msg)
            
            socketio.emit('partial_migration_result', {
                'success': False,
                'error': str(e)
            })
            
        finally:
            # Fechar conexões
            try:
                if mysql:
                    mysql.close()
                if postgres:
                    postgres.close()
            except Exception as e:
                MigrationLogger().log_warning(f"Error closing connections: {str(e)}")
    
    # Executar em thread separada
    eventlet.spawn(run_migration)


from dbmigrator.migration_logging.log import MigrationLogger
from dbmigrator.migration_logging.observer.i_observer import ILoggingObserver
from dbmigrator.migration_logging.observer.logging_level import LoggingLevel

if __name__ == '__main__':
    class NewObserver(ILoggingObserver):
            def __init__(self):
                pass

            def push(self, message, level: LoggingLevel):
                LOG = {
                    'log_level': str(level).split('.')[-1],
                    'message': message
                }
                socketio.emit('log', (LOG))

    newObserver = NewObserver()
    MigrationLogger().register_observer(newObserver)


    socketio.run(app, host='0.0.0.0', debug=True, allow_unsafe_werkzeug=True, port=5005)

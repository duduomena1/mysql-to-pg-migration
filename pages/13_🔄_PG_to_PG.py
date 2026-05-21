"""
🔄 PostgreSQL to PostgreSQL Migration Page - CSV Method
Complete migration from one PostgreSQL database to another using CSV as intermediate format
"""

import streamlit as st
import os
import sys
import shutil
import logging
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection
from dbmigrator.data_migration.pg_to_pg_csv import PostgreSQLToCSV, CSVToPostgreSQL
from dbmigrator.configuration_management.db_credentials import DBCredentials
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

# Configurar logging detalhado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('pg_to_pg_migration')

st.title("🔄 PostgreSQL → PostgreSQL Migration (CSV Method)")

st.success("""
**✨ New CSV-Based Migration Method**

Benefits:
- ✅ Better handling of NULL values
- ✅ Preserves all data types correctly (JSON, arrays, special types)
- ✅ More reliable for large datasets
- ✅ Handles duplicates gracefully with ON CONFLICT
- ✅ Easier to debug and resume failed migrations
- ✅ Creates backup CSV files automatically
""")

# Inicializar configurações
if 'pg_source_config' not in st.session_state:
    st.session_state.pg_source_config = {
        'host': '', 'port': '5432', 'database': '',
        'user': 'postgres', 'password': '', 'schema': 'public'
    }

if 'pg_dest_config' not in st.session_state:
    st.session_state.pg_dest_config = {
        'host': '', 'port': '5432', 'database': '',
        'user': 'postgres', 'password': '', 'schema': 'public'
    }

# === CONEXÕES ===
st.markdown("---")
st.subheader("🔌 Database Connections")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📤 Source Database")
    with st.expander("⚙️ Settings", expanded=True):
        pg_src_host = st.text_input("Host", value=st.session_state.pg_source_config['host'], key="pg_src_host")
        pg_src_port = st.number_input("Port", value=int(st.session_state.pg_source_config['port']), min_value=1, max_value=65535, key="pg_src_port")
        pg_src_database = st.text_input("Database", value=st.session_state.pg_source_config['database'], key="pg_src_db")
        pg_src_user = st.text_input("User", value=st.session_state.pg_source_config['user'], key="pg_src_user")
        pg_src_password = st.text_input("Password", value=st.session_state.pg_source_config['password'], type="password", key="pg_src_pass")
        pg_src_schema = st.text_input("Schema", value=st.session_state.pg_source_config['schema'], key="pg_src_schema")
    
    if st.button("🔍 Test Source", key="test_src", use_container_width=True):
        logger.info("="*80)
        logger.info("Testing SOURCE database connection")
        logger.info(f"Host: {pg_src_host}:{pg_src_port}")
        logger.info(f"Database: {pg_src_database}")
        logger.info(f"User: {pg_src_user}")
        logger.info(f"Schema: {pg_src_schema}")
        logger.info("-"*80)
        
        try:
            logger.info("Creating credentials...")
            credentials = DBCredentials(database=pg_src_database, user=pg_src_user, password=pg_src_password, host=pg_src_host, port=str(pg_src_port))
            
            logger.info("Connecting to PostgreSQL...")
            conn = PostgreSQLConnection(credentials)
            conn.create()
            logger.info("✅ Connection established")
            
            logger.info(f"Checking if schema '{pg_src_schema}' exists...")
            cursor = conn.connection.cursor()
            cursor.execute(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{pg_src_schema}'")
            if cursor.fetchone():
                logger.info(f"✅ Schema '{pg_src_schema}' found")
                st.success(f"✅ Connected to {pg_src_database}")
                st.session_state.pg_source_config = {'host': pg_src_host, 'port': str(pg_src_port), 'database': pg_src_database, 'user': pg_src_user, 'password': pg_src_password, 'schema': pg_src_schema}
                st.session_state.pg_source_conn = credentials
                logger.info("✅ Source configuration saved")
            else:
                logger.error(f"❌ Schema '{pg_src_schema}' not found in database")
                st.error(f"❌ Schema '{pg_src_schema}' not found!")
            cursor.close()
            conn.close()
            logger.info("Connection closed")
            logger.info("="*80)
        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            logger.exception("Full error traceback:")
            logger.info("="*80)
            st.error(f"❌ Connection failed: {str(e)}")

with col2:
    st.markdown("### 📥 Destination Database")
    with st.expander("⚙️ Settings", expanded=True):
        pg_dest_host = st.text_input("Host", value=st.session_state.pg_dest_config['host'], key="pg_dest_host")
        pg_dest_port = st.number_input("Port", value=int(st.session_state.pg_dest_config['port']), min_value=1, max_value=65535, key="pg_dest_port")
        pg_dest_database = st.text_input("Database", value=st.session_state.pg_dest_config['database'], key="pg_dest_db")
        pg_dest_user = st.text_input("User", value=st.session_state.pg_dest_config['user'], key="pg_dest_user")
        pg_dest_password = st.text_input("Password", value=st.session_state.pg_dest_config['password'], type="password", key="pg_dest_pass")
        pg_dest_schema = st.text_input("Schema", value=st.session_state.pg_dest_config['schema'], key="pg_dest_schema")
    
    if st.button("🔍 Test Destination", key="test_dest", use_container_width=True):
        logger.info("="*80)
        logger.info("Testing DESTINATION database connection")
        logger.info(f"Host: {pg_dest_host}:{pg_dest_port}")
        logger.info(f"Database: {pg_dest_database}")
        logger.info(f"User: {pg_dest_user}")
        logger.info(f"Schema: {pg_dest_schema}")
        logger.info("-"*80)
        
        try:
            logger.info("Creating credentials...")
            credentials = DBCredentials(database=pg_dest_database, user=pg_dest_user, password=pg_dest_password, host=pg_dest_host, port=str(pg_dest_port))
            
            logger.info("Connecting to PostgreSQL...")
            conn = PostgreSQLConnection(credentials)
            conn.create()
            logger.info("✅ Connection established")
            
            logger.info(f"Checking if schema '{pg_dest_schema}' exists...")
            cursor = conn.connection.cursor()
            cursor.execute(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{pg_dest_schema}'")
            schema_exists = cursor.fetchone() is not None
            
            if not schema_exists:
                logger.info(f"Schema '{pg_dest_schema}' not found, creating...")
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {pg_dest_schema}")
                conn.connection.commit()
                logger.info(f"✅ Schema '{pg_dest_schema}' created")
                st.info(f"📝 Schema '{pg_dest_schema}' created")
            else:
                logger.info(f"✅ Schema '{pg_dest_schema}' already exists")
                st.info(f"📋 Schema '{pg_dest_schema}' already exists")
            
            st.success(f"✅ Connected to {pg_dest_database}")
            st.session_state.pg_dest_config = {'host': pg_dest_host, 'port': str(pg_dest_port), 'database': pg_dest_database, 'user': pg_dest_user, 'password': pg_dest_password, 'schema': pg_dest_schema}
            st.session_state.pg_dest_conn = credentials
            logger.info("✅ Destination configuration saved")
            cursor.close()
            conn.close()
            logger.info("Connection closed")
            logger.info("="*80)
        except Exception as e:
            logger.error(f"❌ Connection failed: {str(e)}")
            logger.exception("Full error traceback:")
            logger.info("="*80)
            st.error(f"❌ Connection failed: {str(e)}")

st.markdown("---")

if 'pg_source_conn' not in st.session_state or 'pg_dest_conn' not in st.session_state:
    st.warning("⚠️ Configure both connections first")
    st.stop()

st.success("✅ Both connections ready!")

# Optional per-table date filters for data migration
if 'pg_time_filters' not in st.session_state:
    st.session_state.pg_time_filters = {}
if 'pg_temporal_columns' not in st.session_state:
    st.session_state.pg_temporal_columns = {}

# === TABS DE MIGRAÇÃO ===
tab1, tab2, tab3, tab4, tab5 = st.tabs(["1️⃣ Metadata", "2️⃣ Schema", "3️⃣ Data (CSV)", "4️⃣ Sequences", "5️⃣ Validate"])

with tab1:
    st.markdown("### 📋 Load Source Tables")
    
    if st.button("🔄 Scan Tables", key="load_metadata", use_container_width=True):
        logger.info("="*80)
        logger.info("PHASE: Loading Metadata from Source")
        logger.info("="*80)
        
        try:
            logger.info("Connecting to source database...")
            source = PostgreSQLConnection(st.session_state.pg_source_conn)
            source.create()
            logger.info("✅ Connected to source")
            
            cursor = source.connection.cursor()
            schema = st.session_state.pg_source_config['schema']
            
            # Get tables
            logger.info(f"Fetching tables from schema '{schema}'...")
            cursor.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE' ORDER BY table_name")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"✅ Found {len(tables)} tables")
            
            if not tables:
                logger.error(f"❌ No tables found in schema '{schema}'")
                st.error(f"❌ No tables in schema '{schema}'")
                cursor.close()
                source.close()
                st.stop()
            
            # Get FK dependencies
            logger.info("Analyzing foreign key relationships...")
            cursor.execute(f"""
                SELECT tc.table_name, ccu.table_name AS referenced_table
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = '{schema}'
            """)
            fk_relations = cursor.fetchall()
            logger.info(f"✅ Found {len(fk_relations)} FK relationships")
            
            # Build dependency graph
            logger.info("Building dependency graph...")
            dependencies = {table: [] for table in tables}
            for child, parent in fk_relations:
                if child in dependencies and parent in tables:
                    dependencies[child].append(parent)
            logger.info("✅ Dependency graph built")
            
            # Topological sort
            logger.info("Performing topological sort to determine migration order...")
            def topo_sort(deps):
                in_degree = {t: 0 for t in deps}
                for t, parents in deps.items():
                    for p in parents:
                        if p in in_degree:
                            in_degree[t] += 1
                queue = sorted([t for t, d in in_degree.items() if d == 0])
                result = []
                while queue:
                    t = queue.pop(0)
                    result.append(t)
                    for other, parents in deps.items():
                        if t in parents:
                            in_degree[other] -= 1
                            if in_degree[other] == 0:
                                queue.append(other)
                    queue.sort()
                if len(result) != len(deps):
                    result.extend(sorted([t for t in deps if t not in result]))
                return result
            
            ordered = topo_sort(dependencies)
            logger.info(f"✅ Migration order determined (first 10): {', '.join(ordered[:10])}")
            
            # Get row counts
            logger.info("Counting rows in each table...")
            table_info = []
            for idx, table in enumerate(ordered, 1):
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM {schema}."{table}"')
                    count = cursor.fetchone()[0]
                    logger.info(f"  [{idx}/{len(ordered)}] {table}: {count:,} rows")
                except Exception as count_err:
                    logger.warning(f"  [{idx}/{len(ordered)}] {table}: Could not count rows - {str(count_err)}")
                    count = 0
                table_info.append({'name': table, 'rows': count, 'deps': dependencies.get(table, [])})
            
            logger.info("Closing source connection...")
            cursor.close()
            source.close()
            logger.info("✅ Source connection closed")
            
            logger.info("Saving metadata to session state...")
            st.session_state.pg_tables = table_info
            st.session_state.pg_selected_tables = [t['name'] for t in table_info]
            st.session_state.pg_migration_order = ordered
            logger.info("✅ Metadata saved")
            
            total_rows = sum(t['rows'] for t in table_info)
            logger.info(f"✅ METADATA LOAD COMPLETE: {len(tables)} tables, {total_rows:,} total rows")
            logger.info("="*80)
            
            st.success(f"✅ Loaded {len(tables)} tables (FK-ordered)")
            st.balloons()
        except Exception as e:
            logger.error(f"❌ METADATA LOAD FAILED: {str(e)}")
            logger.exception("Full error traceback:")
            logger.info("="*80)
            st.error(f"❌ Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    
    if 'pg_tables' in st.session_state:
        st.markdown("---")
        total_rows = sum(t['rows'] for t in st.session_state.pg_tables if t['name'] in st.session_state.pg_selected_tables)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Tables", len(st.session_state.pg_tables))
        col2.metric("Selected", len(st.session_state.pg_selected_tables))
        col3.metric("Total Rows", f"{total_rows:,}")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        if col1.button("✅ Select All", use_container_width=True):
            st.session_state.pg_selected_tables = [t['name'] for t in st.session_state.pg_tables]
            st.rerun()
        if col2.button("❌ Clear", use_container_width=True):
            st.session_state.pg_selected_tables = []
            st.rerun()
        
        st.markdown("#### 📋 Tables (FK-ordered)")
        for idx, t in enumerate(st.session_state.pg_tables):
            col1, col2 = st.columns([3, 1])
            with col1:
                selected = st.checkbox(f"#{idx+1} {t['name']}", value=t['name'] in st.session_state.pg_selected_tables, key=f"tbl_{t['name']}")
                if selected and t['name'] not in st.session_state.pg_selected_tables:
                    st.session_state.pg_selected_tables.append(t['name'])
                elif not selected and t['name'] in st.session_state.pg_selected_tables:
                    st.session_state.pg_selected_tables.remove(t['name'])
                if t['deps']:
                    st.caption(f"   ↳ Depends on: {', '.join(t['deps'])}")
            with col2:
                st.caption(f"{t['rows']:,} rows")

with tab2:
    st.markdown("### 🏗️ Migrate Schema (DDL)")
    st.info("Creates ONLY table structures (columns and types). Sequences, constraints and indexes are migrated in their specific tabs.")
    st.warning("⚠️ Do NOT create sequences here - they will be created in the Sequences tab after data migration")
    
    if 'pg_selected_tables' not in st.session_state or not st.session_state.pg_selected_tables:
        st.warning("⚠️ Load tables first (Metadata tab)")
    else:
        st.markdown(f"**{len(st.session_state.pg_selected_tables)} tables selected**")
        
        if st.button("🚀 Migrate Table Structures Only", key="migrate_schema", type="primary", use_container_width=True):
            logger.info("="*80)
            logger.info("PHASE: Migrating Schema (Table Structures)")
            logger.info("="*80)
            
            progress = st.progress(0)
            status = st.empty()
            logs = st.empty()
            log_list = []
            
            try:
                logger.info("Connecting to source and destination...")
                source = PostgreSQLConnection(st.session_state.pg_source_conn)
                source.create()
                dest = PostgreSQLConnection(st.session_state.pg_dest_conn)
                dest.create()
                logger.info("✅ Connected to both databases")
                
                src_schema = st.session_state.pg_source_config['schema']
                dst_schema = st.session_state.pg_dest_config['schema']
                total = len(st.session_state.pg_selected_tables)
                
                logger.info(f"Source schema: {src_schema}")
                logger.info(f"Destination schema: {dst_schema}")
                logger.info(f"Tables to migrate: {total}")
                logger.info("-"*80)
                
                # STEP 1: Detectar e criar tipos ENUM/customizados PRIMEIRO
                logger.info("STEP 1: Detecting custom types (ENUMs, extensions) used by tables...")
                src_cur = source.connection.cursor()
                
                # Buscar todos os tipos customizados usados pelas tabelas selecionadas
                tables_list = "', '".join(st.session_state.pg_selected_tables)
                src_cur.execute(f"""
                    SELECT DISTINCT 
                        c.udt_name, 
                        t.typtype, 
                        n.nspname as type_schema,
                        t.typname
                    FROM information_schema.columns c
                    JOIN pg_type t ON t.typname = c.udt_name
                    JOIN pg_namespace n ON t.typnamespace = n.oid
                    WHERE c.table_schema = '{src_schema}'
                    AND c.table_name IN ('{tables_list}')
                    AND c.data_type = 'USER-DEFINED'
                    ORDER BY c.udt_name
                """)
                
                custom_types = src_cur.fetchall()
                logger.info(f"✅ Found {len(custom_types)} custom types to analyze")
                
                # Separar tipos por categoria
                user_types = []  # ENUMs e outros tipos do schema de origem
                extension_types = []  # Tipos de extensões (PostGIS, etc)
                system_types = []  # Tipos do sistema (pg_catalog)
                
                for type_name, type_type, type_schema, type_name2 in custom_types:
                    logger.info(f"  Type: {type_name} | Category: {type_type} | Schema: {type_schema}")
                    
                    if type_schema == src_schema:
                        user_types.append((type_name, type_type, type_schema))
                        logger.info(f"    → User type (will be created in {dst_schema})")
                    elif type_schema in ('public', 'pg_catalog'):
                        if type_name in ('geometry', 'geography', 'box2d', 'box3d'):
                            extension_types.append(type_name)
                            logger.info(f"    → PostGIS extension type")
                        else:
                            system_types.append(type_name)
                            logger.info(f"    → System type")
                    else:
                        logger.info(f"    → Extension type from schema: {type_schema}")
                        extension_types.append(type_name)
                
                logger.info(f"Summary: {len(user_types)} user types, {len(extension_types)} extension types, {len(system_types)} system types")
                
                # Criar extensões necessárias (PostGIS)
                if extension_types:
                    dst_cur = dest.connection.cursor()
                    logger.info("Creating required extensions...")
                    
                    # Verificar se PostGIS é necessário
                    if any(t in extension_types for t in ['geometry', 'geography', 'box2d', 'box3d']):
                        try:
                            dst_cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                            dest.connection.commit()
                            logger.info("  ✅ PostGIS extension enabled")
                            log_list.append("✅ PostGIS extension enabled")
                        except Exception as e:
                            logger.warning(f"  ⚠️ PostGIS extension error: {str(e)}")
                            log_list.append(f"⚠️ PostGIS: {str(e)}")
                    
                    dst_cur.close()
                    logs.text_area("Log", "\n".join(log_list[-10:]), height=200)
                
                if user_types:
                    dst_cur = dest.connection.cursor()
                    logger.info("Creating user-defined types...")
                    
                    for type_name, type_type, type_schema in user_types:
                        logger.info(f"  Creating ENUM type: {type_name}")
                        
                        # Buscar valores do ENUM (apenas do schema de origem)
                        src_cur.execute(f"""
                            SELECT DISTINCT e.enumlabel
                            FROM pg_enum e
                            JOIN pg_type t ON e.enumtypid = t.oid
                            JOIN pg_namespace n ON t.typnamespace = n.oid
                            WHERE t.typname = '{type_name}'
                            AND n.nspname = '{src_schema}'
                            ORDER BY e.enumlabel
                        """)
                        
                        # Remover duplicatas mantendo a ordem
                        enum_values_raw = [row[0] for row in src_cur.fetchall()]
                        enum_values = list(dict.fromkeys(enum_values_raw))  # Remove duplicatas preservando ordem
                        
                        if enum_values:
                            enum_values_sql = "', '".join(enum_values)
                            
                            # Dropar tipo se já existe e recriar (garante consistência)
                            try:
                                drop_enum_sql = f"DROP TYPE IF EXISTS {dst_schema}.{type_name} CASCADE"
                                logger.info(f"    Dropping existing type: {drop_enum_sql}")
                                dst_cur.execute(drop_enum_sql)
                                dest.connection.commit()
                                
                                create_enum_sql = f"CREATE TYPE {dst_schema}.{type_name} AS ENUM ('{enum_values_sql}')"
                                logger.info(f"    Creating type: {create_enum_sql}")
                                dst_cur.execute(create_enum_sql)
                                dest.connection.commit()
                                logger.info(f"  ✅ ENUM {type_name} created with {len(enum_values)} values")
                                log_list.append(f"✅ Created ENUM: {type_name}")
                            except Exception as e:
                                logger.error(f"  ❌ Error creating ENUM {type_name}: {str(e)}")
                                log_list.append(f"❌ ENUM error: {type_name}")
                                st.error(f"Erro ao criar ENUM {type_name}: {str(e)}")
                                raise
                    
                    dst_cur.close()
                    logs.text_area("Log", "\n".join(log_list[-10:]), height=200)
                
                src_cur.close()
                
                # Criar set de tipos que pertencem ao schema de destino (para qualificação)
                user_type_names = {type_name for type_name, _, _ in user_types} if user_types else set()
                logger.info(f"User types to qualify: {user_type_names}")
                
                logger.info("-"*80)
                logger.info("STEP 2: Creating tables...")
                
                for idx, table in enumerate(st.session_state.pg_selected_tables):
                    logger.info(f"[{idx+1}/{total}] Processing table: {table}")
                    status.text(f"📦 [{idx+1}/{total}] {table}")
                    
                    src_cur = source.connection.cursor()
                    src_cur.execute(f"""
                        SELECT column_name, data_type, character_maximum_length, is_nullable, udt_name
                        FROM information_schema.columns
                        WHERE table_schema = '{src_schema}' AND table_name = '{table}'
                        ORDER BY ordinal_position
                    """)
                    
                    cols = []
                    for col_name, dtype, max_len, nullable, udt in src_cur.fetchall():
                        # Usar tipo real (udt_name) para USER-DEFINED e ARRAY
                        # Qualificar apenas tipos criados pelo usuário (ENUMs do schema)
                        if dtype == 'USER-DEFINED':
                            # Se é tipo criado pelo usuário, qualificar com schema
                            if udt in user_type_names:
                                actual_type = f"{dst_schema}.{udt}"
                            else:
                                # Tipo de extensão ou sistema (geometry, etc) - não qualificar
                                actual_type = udt
                        elif dtype == 'ARRAY':
                            actual_type = udt
                        else:
                            actual_type = dtype
                        col_def = f'"{col_name}" {actual_type}'
                        
                        # Adicionar tamanho máximo apenas para tipos que precisam
                        if max_len and dtype not in ('USER-DEFINED', 'ARRAY', 'text', 'integer', 'bigint', 'smallint', 'boolean', 'timestamp', 'date', 'time'):
                            col_def = f'"{col_name}" {actual_type}({max_len})'
                        
                        # Adicionar NOT NULL se necessário
                        if nullable == 'NO':
                            col_def += ' NOT NULL'
                        
                        cols.append(col_def)
                    
                    # Criar tabela SEM defaults, sequences, constraints ou indexes
                    create_sql = f"CREATE TABLE IF NOT EXISTS {dst_schema}.{table} ({', '.join(cols)})"
                    logger.info(f"  Creating table with {len(cols)} columns...")
                    
                    dst_cur = dest.connection.cursor()
                    dst_cur.execute(create_sql)
                    dest.connection.commit()
                    logger.info(f"  ✅ Table {table} created successfully")
                    dst_cur.close()
                    src_cur.close()
                    
                    log_list.append(f"✅ {table} - structure created")
                    logs.text_area("Log", "\n".join(log_list[-10:]), height=200)
                    progress.progress((idx+1)/total)
                
                logger.info("-"*80)
                logger.info("Closing connections...")
                source.close()
                dest.close()
                logger.info("✅ Connections closed")
                
                logger.info(f"✅ SCHEMA MIGRATION COMPLETE: {total} tables created")
                logger.info("="*80)
                
                status.text("✅ Schema migration complete!")
                st.success(f"✅ Migrated {total} tables!")
                st.balloons()
            except Exception as e:
                logger.error(f"❌ SCHEMA MIGRATION FAILED: {str(e)}")
                logger.exception("Full error traceback:")
                logger.info("="*80)
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

with tab3:
    st.markdown("### 📦 Migrate Data (CSV Method)")
    st.success("Uses CSV files as intermediate format for maximum reliability")
    
    if 'pg_selected_tables' not in st.session_state or not st.session_state.pg_selected_tables:
        st.warning("⚠️ Load tables first")
    else:
        with st.expander("⚙️ Settings"):
            csv_dir = st.text_input("CSV Directory", value="data_pg_migration")
            batch_size = st.number_input("Batch Size", min_value=1000, max_value=50000, value=10000, step=1000)
            conflict = st.selectbox("Duplicate Handling", ["Skip (DO NOTHING)", "Update (DO UPDATE)", "Fail"])
            keep_csv = st.checkbox("Keep CSV files after migration", value=False)

        with st.expander("📅 Optional Date Filter (per table)"):
            st.caption("Use this to migrate only a time window for large tables. Leave empty to migrate everything.")
            filter_table = st.selectbox(
                "Table to filter",
                options=st.session_state.pg_selected_tables,
                key="pg_filter_table"
            )
            if st.button("🔍 Load date/time columns", key="pg_load_temporal_cols"):
                try:
                    source = PostgreSQLConnection(st.session_state.pg_source_conn)
                    source.create()
                    schema = st.session_state.pg_source_config['schema']
                    cur = source.connection.cursor()
                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s
                          AND table_name = %s
                          AND (
                            data_type IN (
                                'date',
                                'timestamp without time zone',
                                'timestamp with time zone',
                                'time without time zone',
                                'time with time zone'
                            )
                            OR udt_name IN ('date', 'timestamp', 'timestamptz', 'timetz')
                          )
                        ORDER BY ordinal_position
                        """,
                        (schema, filter_table)
                    )
                    cols = [row[0] for row in cur.fetchall()]
                    cur.close()
                    source.close()
                    st.session_state.pg_temporal_columns[filter_table] = cols
                    if cols:
                        st.success(f"✅ Found {len(cols)} date/time columns")
                    else:
                        st.warning("⚠️ No date/time columns found for this table")
                except Exception as e:
                    st.error(f"❌ Error loading columns: {str(e)}")
            temporal_cols = st.session_state.pg_temporal_columns.get(filter_table, [])
            if temporal_cols:
                existing_filter = st.session_state.pg_time_filters.get(filter_table)
                default_start = (datetime.now() - timedelta(days=30)).date()
                default_end = datetime.now().date()
                if existing_filter:
                    try:
                        default_start = datetime.fromisoformat(existing_filter['start']).date()
                        default_end = datetime.fromisoformat(existing_filter['end']).date()
                    except Exception:
                        pass
                filter_col = st.selectbox(
                    "Date/Time column",
                    options=temporal_cols,
                    index=temporal_cols.index(existing_filter['column']) if existing_filter and existing_filter['column'] in temporal_cols else 0,
                    key=f"pg_filter_col_{filter_table}"
                )
                col_date1, col_date2 = st.columns(2)
                with col_date1:
                    start_date = st.date_input(
                        "Start date",
                        value=default_start,
                        key=f"pg_filter_start_{filter_table}"
                    )
                    st.caption("⏰ Time will be set to 00:00:00")
                with col_date2:
                    end_date = st.date_input(
                        "End date",
                        value=default_end,
                        key=f"pg_filter_end_{filter_table}"
                    )
                    st.caption("⏰ Time will be set to 23:59:59")
                if start_date > end_date:
                    st.error("❌ Start date must be before or equal to end date")
                col_save, col_remove = st.columns([2, 1])
                with col_save:
                    if st.button("💾 Save filter for this table", key=f"pg_save_filter_{filter_table}"):
                        if start_date > end_date:
                            st.error("❌ Fix the date range before saving")
                        else:
                            start_dt = datetime.combine(start_date, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
                            end_dt = datetime.combine(end_date, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")
                            st.session_state.pg_time_filters[filter_table] = {
                                'column': filter_col,
                                'start': start_dt,
                                'end': end_dt
                            }
                            st.success(f"✅ Filter saved for {filter_table}")
                with col_remove:
                    if filter_table in st.session_state.pg_time_filters:
                        if st.button("❌ Remove", key=f"pg_remove_filter_{filter_table}"):
                            st.session_state.pg_time_filters.pop(filter_table, None)
                            st.info(f"Filter removed for {filter_table}")
            if st.session_state.pg_time_filters:
                st.markdown("**Active filters**")
                import pandas as pd
                rows = [
                    {
                        'Table': tbl,
                        'Column': cfg['column'],
                        'Start': cfg['start'],
                        'End': cfg['end']
                    }
                    for tbl, cfg in st.session_state.pg_time_filters.items()
                ]
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
        
        if st.button("🚀 Migrate Data", key="migrate_data", type="primary", use_container_width=True):
            progress = st.progress(0)
            status = st.empty()
            logs = st.empty()
            log_list = []
            
            success_tables = []
            failed_tables = []
            
            logger.info("="*80)
            logger.info("PHASE: Data Migration (CSV Method)")
            logger.info("="*80)
            
            try:
                logger.info("Connecting to source and destination...")
                source = PostgreSQLConnection(st.session_state.pg_source_conn)
                source.create()
                dest = PostgreSQLConnection(st.session_state.pg_dest_conn)
                dest.create()
                logger.info("✅ Connected to both databases")
                
                src_schema = st.session_state.pg_source_config['schema']
                dst_schema = st.session_state.pg_dest_config['schema']
                
                tables = [t for t in st.session_state.pg_migration_order if t in st.session_state.pg_selected_tables]
                total = len(tables)
                
                logger.info(f"Configuration:")
                logger.info(f"  CSV Directory: {csv_dir}")
                logger.info(f"  Batch Size: {batch_size:,}")
                logger.info(f"  Conflict Mode: {conflict}")
                logger.info(f"  Keep CSV: {keep_csv}")
                logger.info(f"  Tables to migrate: {total}")
                logger.info(f"  Migration order: {', '.join(tables[:10])}{'...' if len(tables) > 10 else ''}")
                logger.info("-"*80)
                
                exporter = PostgreSQLToCSV(source, schema=src_schema, output_dir=csv_dir)
                importer = CSVToPostgreSQL(dest, schema=dst_schema, input_dir=csv_dir)
                
                on_conflict = 'do_nothing' if 'Skip' in conflict else ('update' if 'Update' in conflict else None)
                
                # PHASE 1: Export
                logger.info("="*80)
                logger.info("PHASE 1: Exporting to CSV")
                logger.info("="*80)
                log_list.append("📤 PHASE 1: Exporting to CSV")
                logs.text_area("Log", "\n".join(log_list[-15:]), height=300)
                
                for idx, table in enumerate(tables):
                    try:
                        logger.info(f"[{idx+1}/{total}] Exporting table: {table}")
                        status.text(f"📤 [{idx+1}/{total}] Exporting: {table}")
                        filter_cfg = st.session_state.pg_time_filters.get(table)
                        export_kwargs = {'batch_size': batch_size}
                        if filter_cfg:
                            logger.info(
                                f"Applying filter for {table}: {filter_cfg['column']} between {filter_cfg['start']} and {filter_cfg['end']}"
                            )
                            export_kwargs.update({
                                'filter_column': filter_cfg['column'],
                                'start_datetime': filter_cfg['start'],
                                'end_datetime': filter_cfg['end']
                            })
                        result = exporter.export_table(table, **export_kwargs)
                        
                        if result['status'] == 'success':
                            log_list.append(f"✅ {table}: {result['rows_exported']:,} rows")
                        elif result['status'] == 'empty':
                            log_list.append(f"⏭️ {table}: empty")
                        else:
                            log_list.append(f"❌ {table}: export failed")
                            failed_tables.append({'name': table, 'error': 'Export failed'})
                        
                        logs.text_area("Log", "\n".join(log_list[-15:]), height=300)
                        progress.progress((idx+0.5)/total)
                    except Exception as e:
                        log_list.append(f"❌ {table}: {str(e)[:80]}")
                        failed_tables.append({'name': table, 'error': str(e)})
                        logs.text_area("Log", "\n".join(log_list[-15:]), height=300)
                
                # PHASE 2: Import
                log_list.append("📥 PHASE 2: Importing from CSV")
                logs.text_area("Log", "\n".join(log_list[-15:]), height=300)
                
                for idx, table in enumerate(tables):
                    if any(ft['name'] == table for ft in failed_tables):
                        continue
                    
                    try:
                        status.text(f"📥 [{idx+1}/{total}] Importing: {table}")
                        result = importer.import_table(table, batch_size=batch_size, on_conflict=on_conflict)
                        
                        if result['status'] == 'success':
                            log_list.append(f"✅ {table}: +{result['rows_imported']:,} ~{result['rows_skipped']:,}")
                            success_tables.append(table)
                        else:
                            error_msg = result.get('error', 'Unknown')
                            log_list.append(f"❌ {table}: {error_msg[:80]}")
                            failed_tables.append({'name': table, 'error': error_msg})
                        
                        logs.text_area("Log", "\n".join(log_list[-15:]), height=300)
                        progress.progress((idx+1)/total)
                    except Exception as e:
                        log_list.append(f"❌ {table}: {str(e)[:80]}")
                        failed_tables.append({'name': table, 'error': str(e)})
                        logs.text_area("Log", "\n".join(log_list[-15:]), height=300)
                
                # Cleanup
                if not keep_csv:
                    try:
                        shutil.rmtree(csv_dir)
                        log_list.append(f"🧹 Cleaned up: {csv_dir}")
                    except:
                        log_list.append(f"⚠️ Could not cleanup {csv_dir}")
                
                source.close()
                dest.close()
                
                st.markdown("---")
                st.subheader("📊 Summary")
                col1, col2 = st.columns(2)
                col1.metric("✅ Success", len(success_tables))
                col2.metric("❌ Failed", len(failed_tables))
                
                if failed_tables:
                    st.error(f"⚠️ {len(failed_tables)} failed")
                    import pandas as pd
                    st.dataframe(pd.DataFrame(failed_tables))
                else:
                    st.success(f"🎉 All {len(success_tables)} tables migrated!")
                    st.balloons()
                
            except Exception as e:
                st.error(f"❌ Migration failed: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

with tab4:
    st.markdown("### 🔢 Create & Synchronize Sequences")
    st.info("Creates sequences from source and sets them to MAX(id) + 1 to prevent duplicate key errors")
    st.warning("⚠️ Run this AFTER migrating data to set correct sequence values")
    
    if 'pg_selected_tables' not in st.session_state or not st.session_state.pg_selected_tables:
        st.warning("⚠️ Load tables first")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔍 Scan Sequences from Source", use_container_width=True):
                try:
                    source = PostgreSQLConnection(st.session_state.pg_source_conn)
                    source.create()
                    src_schema = st.session_state.pg_source_config['schema']
                    cursor = source.connection.cursor()
                    
                    sequences = []
                    for table in st.session_state.pg_selected_tables:
                        cursor.execute(f"""
                            SELECT column_name, column_default
                            FROM information_schema.columns
                            WHERE table_schema = '{src_schema}' AND table_name = '{table}' AND column_default LIKE 'nextval%'
                        """)
                        
                        import re
                        for col_name, col_default in cursor.fetchall():
                            seq_match = re.search(r"nextval\('(?:.*?\.)?([^']+)'", col_default)
                            if seq_match:
                                seq_name = seq_match.group(1).strip('"')
                            else:
                                seq_name = f"{table}_{col_name}_seq"
                            sequences.append({'table': table, 'column': col_name, 'sequence': seq_name})
                    
                    cursor.close()
                    source.close()
                    
                    st.session_state.pg_sequences = sequences
                    
                    if sequences:
                        st.success(f"✅ Found {len(sequences)} sequences in source")
                    else:
                        st.warning("⚠️ No sequences found")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with col2:
            if st.button("🏗️ Create Sequences in Destination", use_container_width=True):
                if 'pg_sequences' not in st.session_state or not st.session_state.pg_sequences:
                    st.warning("⚠️ Scan sequences first")
                else:
                    try:
                        source = PostgreSQLConnection(st.session_state.pg_source_conn)
                        source.create()
                        dest = PostgreSQLConnection(st.session_state.pg_dest_conn)
                        dest.create()
                        
                        src_schema = st.session_state.pg_source_config['schema']
                        dst_schema = st.session_state.pg_dest_config['schema']
                        
                        results = []
                        for seq in st.session_state.pg_sequences:
                            try:
                                dst_cur = dest.connection.cursor()
                                
                                # Criar sequence
                                dst_cur.execute(f"CREATE SEQUENCE IF NOT EXISTS {dst_schema}.{seq['sequence']}")
                                
                                # Associar sequence à coluna
                                dst_cur.execute(f"""
                                    ALTER TABLE {dst_schema}.{seq['table']} 
                                    ALTER COLUMN "{seq['column']}" 
                                    SET DEFAULT nextval('{dst_schema}.{seq['sequence']}'::regclass)
                                """)
                                
                                # Transferir ownership
                                dst_cur.execute(f"""
                                    ALTER SEQUENCE {dst_schema}.{seq['sequence']} 
                                    OWNED BY {dst_schema}.{seq['table']}."{seq['column']}"
                                """)
                                
                                dest.connection.commit()
                                dst_cur.close()
                                
                                results.append({'Table': seq['table'], 'Sequence': seq['sequence'], 'Status': '✅ Created'})
                            except Exception as e:
                                results.append({'Table': seq['table'], 'Sequence': seq['sequence'], 'Status': f'❌ {str(e)[:40]}'})
                        
                        source.close()
                        dest.close()
                        
                        st.markdown("---")
                        import pandas as pd
                        st.dataframe(pd.DataFrame(results))
                        
                        success = sum(1 for r in results if '✅' in r['Status'])
                        st.success(f"✅ Created {success}/{len(results)} sequences")
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        if 'pg_sequences' in st.session_state and st.session_state.pg_sequences:
            st.markdown("---")
            st.markdown("### 📋 Detected Sequences")
            import pandas as pd
            st.dataframe(pd.DataFrame(st.session_state.pg_sequences))
            
            st.markdown("---")
            st.markdown("### 🔄 Synchronize Sequence Values")
            st.caption("Sets sequence values based on MAX(id) from source + offset")
            offset = st.number_input("Offset (adds to MAX)", min_value=0, max_value=10000, value=1,
                                    help="1 = next value will be MAX+1 (recommended)")
            
            if st.button("🚀 Synchronize All Sequences", type="primary", use_container_width=True):
                try:
                    source = PostgreSQLConnection(st.session_state.pg_source_conn)
                    source.create()
                    dest = PostgreSQLConnection(st.session_state.pg_dest_conn)
                    dest.create()
                    
                    src_schema = st.session_state.pg_source_config['schema']
                    dst_schema = st.session_state.pg_dest_config['schema']
                    
                    results = []
                    for seq in st.session_state.pg_sequences:
                        try:
                            src_cur = source.connection.cursor()
                            src_cur.execute(f'SELECT MAX("{seq["column"]}") FROM {src_schema}.{seq["table"]}')
                            max_id = src_cur.fetchone()[0] or 0
                            src_cur.close()
                            
                            next_val = max_id + offset
                            
                            dst_cur = dest.connection.cursor()
                            dst_cur.execute(f"SELECT setval('{dst_schema}.{seq['sequence']}', {next_val}, false)")
                            dest.connection.commit()
                            dst_cur.close()
                            
                            results.append({'Table': seq['table'], 'Sequence': seq['sequence'], 'MAX': max_id, 'Next': next_val, 'Status': '✅'})
                        except Exception as e:
                            results.append({'Table': seq['table'], 'Sequence': seq['sequence'], 'MAX': 'N/A', 'Next': 'N/A', 'Status': f'❌ {str(e)[:30]}'})
                    
                    source.close()
                    dest.close()
                    
                    st.markdown("---")
                    st.dataframe(pd.DataFrame(results))
                    
                    success = sum(1 for r in results if '✅' in r['Status'])
                    col1, col2 = st.columns(2)
                    col1.metric("✅ Synced", success)
                    col2.metric("❌ Failed", len(results) - success)
                    
                    if success == len(results):
                        st.success("🎉 All sequences synced!")
                        st.balloons()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

with tab5:
    st.markdown("### ✅ Validate Migration")
    st.info("Compare row counts to verify data integrity")
    
    if 'pg_selected_tables' not in st.session_state or not st.session_state.pg_selected_tables:
        st.warning("⚠️ Load tables first")
    else:
        if st.button("🔍 Validate", type="primary", use_container_width=True):
            try:
                source = PostgreSQLConnection(st.session_state.pg_source_conn)
                source.create()
                dest = PostgreSQLConnection(st.session_state.pg_dest_conn)
                dest.create()
                
                src_schema = st.session_state.pg_source_config['schema']
                dst_schema = st.session_state.pg_dest_config['schema']
                
                results = []
                progress = st.progress(0)
                
                for idx, table in enumerate(st.session_state.pg_selected_tables):
                    try:
                        src_cur = source.connection.cursor()
                        src_cur.execute(f'SELECT COUNT(*) FROM {src_schema}."{table}"')
                        src_count = src_cur.fetchone()[0]
                        src_cur.close()
                        
                        dst_cur = dest.connection.cursor()
                        dst_cur.execute(f'SELECT COUNT(*) FROM {dst_schema}."{table}"')
                        dst_count = dst_cur.fetchone()[0]
                        dst_cur.close()
                        
                        match = src_count == dst_count
                        results.append({'Table': table, 'Source': src_count, 'Destination': dst_count, 'Status': '✅ Match' if match else '❌ Mismatch'})
                    except:
                        results.append({'Table': table, 'Source': 'N/A', 'Destination': 'N/A', 'Status': '⚠️ Error'})
                    
                    progress.progress((idx+1)/len(st.session_state.pg_selected_tables))
                
                source.close()
                dest.close()
                
                st.markdown("---")
                import pandas as pd
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True)
                
                matched = sum(1 for r in results if '✅' in r['Status'])
                col1, col2 = st.columns(2)
                col1.metric("✅ Matched", matched)
                col2.metric("❌ Mismatched", len(results) - matched)
                
                if matched == len(results):
                    st.success("🎉 All tables validated!")
                    st.balloons()
                else:
                    st.warning(f"⚠️ {len(results) - matched} tables have issues")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

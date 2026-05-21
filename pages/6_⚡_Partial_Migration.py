"""
⚡ Partial Migration Page
Migrate specific date ranges with CSV optimization (10-20x faster)
"""

import streamlit as st
import os
import json
from datetime import datetime, timedelta
from dbmigrator.configuration_management.configuration import MigrationConfig
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection
from dbmigrator.data_migration.partial_table_migration import PartialTableMigrator
from dbmigrator.migration_logging.log import MigrationLogger

# Adicionar path para importar módulos
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pages import ensure_config_loaded

st.title("⚡ Partial Migration")

# Sempre carregar configuração do arquivo
ensure_config_loaded()
config = st.session_state.config

# Informação sobre performance
st.info("""
🚀 **CSV Mode**: 10-20x faster than regular INSERT mode!  
📊 **Use case**: Migrate large tables by date ranges  
✅ **Safe**: Checkpointing allows resume after failures  
""")

# Layout principal
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📋 Migration Settings")
    
    # Conectar ao MySQL para listar tabelas
    if st.button("🔄 Load Tables", key="load_tables"):
        try:
            # Verificar se temos conexão
            if 'mysql_conn' not in st.session_state or st.session_state.mysql_conn is None:
                st.error("❌ Please configure MySQL connection first!")
                st.stop()
            
            with st.spinner("Loading tables from MySQL..."):
                mysql = MySQLConnection(st.session_state.mysql_conn)
                mysql.create()
                
                cursor = mysql.connection.cursor()
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
                cursor.close()
                mysql.close()
                
                st.session_state.tables = sorted(tables)
                st.success(f"✅ Loaded {len(tables)} tables")
        except Exception as e:
            st.error(f"❌ Error loading tables: {str(e)}")
    
    # Seleção de tabela
    if 'tables' in st.session_state and st.session_state.tables:
        table_name = st.selectbox(
            "📊 Select Table",
            options=st.session_state.tables,
            key="table_select"
        )
        
        # Carregar colunas temporais da tabela selecionada
        if st.button("🔍 Load Temporal Columns", key="load_columns"):
            try:
                with st.spinner(f"Analyzing table '{table_name}'..."):
                    mysql = MySQLConnection(st.session_state.mysql_conn)
                    mysql.create()
                    
                    cursor = mysql.connection.cursor(dictionary=True)
                    cursor.execute(f"DESCRIBE {st.session_state.mysql_conn.database}.{table_name}")
                    columns = cursor.fetchall()
                    cursor.close()
                    mysql.close()
                    
                    # Filtrar colunas de data/timestamp
                    temporal_cols = [
                        col['Field'] for col in columns
                        if any(t in col['Type'].lower() for t in ['date', 'time', 'timestamp'])
                    ]
                    
                    st.session_state.temporal_columns = temporal_cols
                    st.success(f"✅ Found {len(temporal_cols)} temporal columns")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
        
        # Seleção de coluna temporal
        if 'temporal_columns' in st.session_state and st.session_state.temporal_columns:
            filter_column = st.selectbox(
                "📅 Time Column",
                options=st.session_state.temporal_columns,
                key="column_select"
            )
            
            st.markdown("---")
            
            # Configuração de datas
            st.subheader("📅 Date Range")
            
            col_date1, col_date2 = st.columns(2)
            
            with col_date1:
                start_date = st.date_input(
                    "Start Date",
                    value=datetime.now() - timedelta(days=30),
                    key="start_date"
                )
                st.caption("⏰ Time will be set to 00:00:00")
            
            with col_date2:
                end_date = st.date_input(
                    "End Date",
                    value=datetime.now(),
                    key="end_date"
                )
                st.caption("⏰ Time will be set to 23:59:59")
            
            # Validação de datas
            if start_date > end_date:
                st.error("❌ Start date must be before or equal to end date!")
            
            st.markdown("---")
            
            # Configurações avançadas
            with st.expander("⚙️ Advanced Settings"):
                use_csv = st.checkbox(
                    "Use CSV Mode (10-20x faster)",
                    value=True,
                    help="Exports to CSV then uses PostgreSQL COPY for ultra-fast loading"
                )
                
                col_batch1, col_batch2 = st.columns(2)
                with col_batch1:
                    mysql_batch = st.number_input(
                        "MySQL Batch Size",
                        min_value=1000,
                        max_value=50000,
                        value=config.mysql_batch_size,
                        step=1000,
                        help="Number of rows to fetch from MySQL at once"
                    )
                
                with col_batch2:
                    postgres_bulk = st.number_input(
                        "PostgreSQL Bulk Size",
                        min_value=1000,
                        max_value=50000,
                        value=config.postgres_bulk_size,
                        step=1000,
                        help="Number of rows to insert into PostgreSQL at once"
                    )
                
                strategy = st.radio(
                    "Strategy",
                    options=["append", "truncate"],
                    help="append: Add to existing data | truncate: Clear table first"
                )

with col2:
    st.subheader("📊 Migration Progress")
    
    # Placeholder para progresso
    progress_container = st.container()

st.markdown("---")

# Botão de migração
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])

with col_btn2:
    if 'temporal_columns' in st.session_state and st.session_state.temporal_columns:
        if st.button("🚀 Start Migration", type="primary", width="stretch"):
            # Converter datas para formato completo
            start_datetime = f"{start_date.strftime('%Y-%m-%d')} 00:00:00"
            end_datetime = f"{end_date.strftime('%Y-%m-%d')} 23:59:59"
            
            # Container para logs
            log_area = st.empty()
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            logs = []
            
            def progress_callback(message, level="INFO"):
                """Callback para atualizar UI"""
                icon = "ℹ️" if level == "INFO" else "⚠️" if level == "WARNING" else "❌"
                logs.append(f"{icon} {message}")
                
                # Mostrar últimos 20 logs
                log_area.text_area(
                    "📝 Migration Log",
                    value="\n".join(logs[-20:]),
                    height=300,
                    key=f"log_{len(logs)}"
                )
            
            try:
                # Verificar conexões
                if 'mysql_conn' not in st.session_state or st.session_state.mysql_conn is None:
                    st.error("❌ Please configure MySQL connection first!")
                    st.stop()
                if 'postgres_conn' not in st.session_state or st.session_state.postgres_conn is None:
                    st.error("❌ Please configure PostgreSQL connection first!")
                    st.stop()
                
                # Conectar aos bancos
                status_text.text("🔌 Connecting to databases...")
                mysql = MySQLConnection(st.session_state.mysql_conn)
                mysql.create()
                
                postgres = PostgreSQLConnection(st.session_state.postgres_conn)
                postgres.create()
                
                status_text.text("✅ Databases connected!")
                
                # Criar migrator
                schema = st.session_state.get('schema_name', config.schema_name)
                migrator = PartialTableMigrator(
                    mysql_conn=mysql,
                    postgres_conn=postgres,
                    schema_name=schema
                )
                
                # Executar migração
                status_text.text("🚀 Starting migration...")
                progress_bar.progress(10)
                
                result = migrator.migrate_table_partial(
                    table_name=table_name,
                    filter_column=filter_column,
                    start_date=start_datetime,
                    end_date=end_datetime,
                    mysql_batch_size=mysql_batch,
                    postgres_bulk_size=postgres_bulk,
                    strategy=strategy,
                    use_csv=use_csv,
                    progress_callback=progress_callback
                )
                
                progress_bar.progress(100)
                
                # Mostrar resultado
                if result.get('success', True):
                    st.success(f"""
                    ✅ **Migration Completed Successfully!**
                    
                    📊 **Statistics:**
                    - Total Rows: {result.get('total_rows', 0):,}
                    - Total Batches: {result.get('total_batches', 0):,}
                    - Method: {'CSV+COPY (10-20x faster)' if use_csv else 'INSERT batch'}
                    {f"- CSV File: {result.get('csv_file', 'N/A')}" if use_csv else ''}
                    """)
                    st.balloons()
                else:
                    st.error(f"❌ Migration failed: {result.get('error', 'Unknown error')}")
                
                # Fechar conexões
                mysql.close()
                postgres.close()
                
            except Exception as e:
                st.error(f"❌ Error during migration: {str(e)}")
                progress_callback(f"Error: {str(e)}", level="ERROR")
    else:
        st.button("🚀 Start Migration", type="primary", width="stretch", disabled=True)
        st.caption("👆 Please load tables and columns first")

# Progresso de migrações anteriores
st.markdown("---")
st.subheader("📜 Migration History")

if os.path.exists("partial_progress.json"):
    with open("partial_progress.json", "r") as f:
        progress_data = json.load(f)
        
        if progress_data.get("migrations"):
            st.dataframe(
                progress_data["migrations"],
                width="stretch"
            )
        else:
            st.info("No migration history yet")
else:
    st.info("No migration history yet")

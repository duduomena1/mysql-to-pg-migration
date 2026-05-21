"""
📦 Tuples Migration Page
Migrate table data (with progress bar)
"""

import streamlit as st
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages import check_prerequisites
from dbmigrator.configuration_management.configuration import MigrationConfig
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection
from dbmigrator.data_migration.mysql_to_postgresql import MySQLToPostgreSQL

st.title("📦 Migrate Tuples (Data)")

# Verificar pré-requisitos e carregar config
check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True)
config = st.session_state.config

st.info("📊 Migrate table data from MySQL to PostgreSQL (with progress tracking)")

tables = st.session_state.tables_metadata
selected_tables = st.session_state.get('selected_tables', [t.name for t in tables])

# Resumo
tables_to_migrate = [t for t in tables if t.name in selected_tables]
total_rows = sum(t.num_tuples for t in tables_to_migrate)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Tables", len(tables_to_migrate))
with col2:
    st.metric("Total Rows", f"{total_rows:,}")
with col3:
    st.metric("Method", "CSV + COPY")

st.markdown("---")

# Opções de migração
with st.expander("⚙️ Migration Options"):
    use_csv = st.checkbox("Use CSV Mode (10-20x faster)", value=True)
    st.caption("CSV mode: Export to CSV then use PostgreSQL COPY for ultra-fast loading")

# Botão de migração
if st.button("🚀 Start Data Migration", type="primary", width="stretch"):
    try:
        # Verificar conexões
        if 'mysql_conn' not in st.session_state or st.session_state.mysql_conn is None:
            st.error("❌ Please configure MySQL connection first!")
            st.stop()
        if 'postgres_conn' not in st.session_state or st.session_state.postgres_conn is None:
            st.error("❌ Please configure PostgreSQL connection first!")
            st.stop()
        
        # Conectar
        with st.spinner("Connecting to databases..."):
            mysql = MySQLConnection(st.session_state.mysql_conn)
            mysql.create()
            
            postgres = PostgreSQLConnection(st.session_state.postgres_conn)
            postgres.create()
        
        # Criar migrator
        migration = MySQLToPostgreSQL(mysql, postgres)
        
        # Área de progresso
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()
        
        # Rastrear progresso acumulado e resultados
        migrated_rows = 0
        success_tables = []
        failed_tables = []
        
        # Migrar cada tabela
        for idx, table in enumerate(tables_to_migrate):
            # Garantir transação limpa ANTES de processar cada tabela
            try:
                # Rollback qualquer transação pendente
                postgres.connection.rollback()
                # Iniciar nova transação
                postgres.connection.autocommit = False
            except Exception as conn_error:
                # Se falhar, tentar reconectar
                try:
                    postgres.close()
                    postgres = PostgreSQLConnection(st.session_state.postgres_conn)
                    postgres.create()
                except:
                    st.error(f"❌ Failed to reconnect to PostgreSQL: {str(conn_error)}")
                    break
            
            try:
                status_text.text(f"📦 Migrating [{idx+1}/{len(tables_to_migrate)}]: {table.name} ({table.num_tuples:,} rows)")
                
                # Callback para atualizar progresso (apenas Streamlit, sem Rich)
                def progress_callback(current):
                    # Atualizar UI Streamlit - safe division
                    if total_rows > 0:
                        overall_progress = (migrated_rows + current) / total_rows
                    else:
                        overall_progress = (idx + 1) / len(tables_to_migrate)
                    
                    progress_bar.progress(min(overall_progress, 1.0))
                
                # Migrar
                if use_csv:
                    migration.save_table_to_csv(table, progress_callback)
                    migration.read_from_csv(table, config.schema_name, progress_callback)
                else:
                    migration.migrate_table_data(table, config.schema_name, progress_callback)
                
                # Commit após cada tabela
                postgres.connection.commit()
                
                # Atualizar contador de linhas migradas
                migrated_rows += table.num_tuples
                success_tables.append(table.name)
                
            except Exception as table_error:
                # Rollback em caso de erro
                try:
                    postgres.connection.rollback()
                except:
                    pass  # Ignorar erro no rollback
                
                error_msg = str(table_error)
                failed_tables.append({
                    'name': table.name,
                    'error': error_msg,
                    'rows': table.num_tuples
                })
                
                # Log imediato do erro
                with log_area.container():
                    st.warning(f"⚠️ Skipped table **{table.name}**: {error_msg}")
                
                # Continuar com a próxima tabela
                continue
        
        # Fechar conexões
        mysql.close()
        postgres.close()
        
        status_text.text("✅ Migration completed!")
        progress_bar.progress(1.0)
        
        # Mostrar resumo detalhado
        st.markdown("---")
        st.subheader("📊 Migration Summary")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("✅ Successful Tables", len(success_tables), delta=f"{migrated_rows:,} rows")
        with col2:
            st.metric("❌ Failed Tables", len(failed_tables), delta_color="inverse")
        
        if len(failed_tables) > 0:
            st.error(f"⚠️ {len(failed_tables)} table(s) failed to migrate:")
            
            import pandas as pd
            df_failed = pd.DataFrame(failed_tables)
            st.dataframe(df_failed, width="stretch")
            
            # Mostrar detalhes dos erros
            with st.expander("🔍 Error Details"):
                for failed in failed_tables:
                    st.markdown(f"**{failed['name']}** ({failed['rows']:,} rows)")
                    st.code(failed['error'])
                    st.markdown("---")
        else:
            st.success(f"🎉 All {len(success_tables)} tables migrated successfully!")
            st.balloons()
        
    except Exception as e:
        st.error(f"❌ Error during migration: {str(e)}")
else:
    # Mostrar tabelas
    with st.expander("📋 View Tables"):
        for table in tables_to_migrate:
            st.text(f"• {table.name} - {table.num_tuples:,} rows")

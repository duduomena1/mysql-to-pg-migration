"""
📑 Indexes Migration Page
Migrate indexes to PostgreSQL
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

st.title("📑 Migrate Indexes")

# Verificar pré-requisitos e carregar config
check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True)

config = st.session_state.config
tables = st.session_state.tables_metadata
selected_tables = st.session_state.get('selected_tables', [t.name for t in tables])

st.info("📑 Create indexes in PostgreSQL for faster queries")

tables_to_migrate = [t for t in tables if t.name in selected_tables]
total_indexes = sum(len(t.indexes) for t in tables_to_migrate)
st.metric("Total Indexes", total_indexes)

# Lista de tabelas selecionadas
with st.expander(f"📋 Tables to Process ({len(tables_to_migrate)} selected)"):
    cols = st.columns(4)
    for idx, table in enumerate(tables_to_migrate):
        with cols[idx % 4]:
            idx_count = len(table.indexes)
            icon = "📑" if idx_count > 0 else "➖"
            st.text(f"{icon} {table.name} ({idx_count} indexes)")

st.markdown("---")

with st.expander("⚙️ Advanced Options"):
    gist_indexes = st.text_area(
        "GIST Indexes (for geometry columns)",
        help="One per line, format: table.column"
    )

if st.button("🚀 Migrate Indexes", type="primary", width="stretch"):
    try:
        # Verificar conexões
        if 'mysql_conn' not in st.session_state or st.session_state.mysql_conn is None:
            st.error("❌ Please configure MySQL connection first!")
            st.stop()
        if 'postgres_conn' not in st.session_state or st.session_state.postgres_conn is None:
            st.error("❌ Please configure PostgreSQL connection first!")
            st.stop()
        
        mysql = MySQLConnection(st.session_state.mysql_conn)
        mysql.create()
        postgres = PostgreSQLConnection(st.session_state.postgres_conn)
        postgres.create()
        
        migration = MySQLToPostgreSQL(mysql, postgres)
        
        # Parse GIST indexes
        gist_list = [line.strip() for line in gist_indexes.split('\n') if line.strip()] if gist_indexes else []
        migration.GIST_indexes = gist_list
        
        progress_bar = st.progress(0)
        logs = []
        log_area = st.empty()
        
        # Definir tabelas a migrar
        migration.tables = tables_to_migrate
        migration.only_tables = [t.name for t in tables_to_migrate]
        
        # Gerar DDLs para indexes
        with st.spinner("Generating INDEX statements..."):
            migration.generate_DDLs(config.schema_name)
        
        # Executar indexes
        with st.spinner("Creating indexes..."):
            try:
                from dbmigrator.data_access.postgresql_data_access import postgres_execute_DDL
                
                # Executar os indexes
                if migration.buffer_indexes:
                    postgres_execute_DDL(postgres, migration.buffer_indexes)
                    postgres.connection.commit()
                    logs.append(f"✅ Successfully created {total_indexes} indexes for {len(tables_to_migrate)} tables")
                else:
                    logs.append("⚠️ No indexes found to migrate")
                
            except Exception as e:
                logs.append(f"❌ Error: {str(e)}")
                postgres.connection.rollback()
        
        progress_bar.progress(1.0)
        log_area.text_area("Log", "\n".join(logs), height=200)
        
        mysql.close()
        postgres.close()
        
        st.success("✅ Indexes migrated!")
        st.balloons()
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

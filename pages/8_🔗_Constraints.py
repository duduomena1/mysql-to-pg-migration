"""
🔗 Constraints Migration Page
Migrate foreign key constraints to PostgreSQL
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

st.title("🔗 Migrate Constraints (Foreign Keys)")

# Verificar pré-requisitos e carregar config
check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True)

config = st.session_state.config
tables = st.session_state.tables_metadata
selected_tables = st.session_state.get('selected_tables', [t.name for t in tables])

st.info("🔗 Create foreign key constraints in PostgreSQL")

tables_to_migrate = [t for t in tables if t.name in selected_tables]
total_fks = sum(len([c for c in t.constraints if c.referenced_table_name]) for t in tables_to_migrate)
st.metric("Total Foreign Keys", total_fks)

# Lista de tabelas selecionadas
with st.expander(f"📋 Tables to Process ({len(tables_to_migrate)} selected)"):
    cols = st.columns(4)
    for idx, table in enumerate(tables_to_migrate):
        with cols[idx % 4]:
            fk_count = len([c for c in table.constraints if c.referenced_table_name])
            icon = "🔗" if fk_count > 0 else "➖"
            st.text(f"{icon} {table.name} ({fk_count} FKs)")

st.markdown("---")

if st.button("🚀 Migrate Constraints", type="primary", width="stretch"):
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
        
        progress_bar = st.progress(0)
        logs = []
        log_area = st.empty()
        
        schema = st.session_state.get('schema_name', config.schema_name)
        
        # Definir tabelas a migrar
        migration.tables = tables_to_migrate
        migration.only_tables = [t.name for t in tables_to_migrate]
        
        # Gerar DDLs para constraints
        with st.spinner("Generating FOREIGN KEY statements..."):
            migration.generate_DDLs(schema)
        
        # Executar constraints
        with st.spinner("Executing FOREIGN KEY constraints..."):
            try:
                from dbmigrator.data_access.postgresql_data_access import postgres_execute_DDL
                
                # Executar as constraints
                if migration.buffer_constraints:
                    postgres_execute_DDL(postgres, migration.buffer_constraints)
                    postgres.connection.commit()
                    logs.append(f"✅ Successfully migrated {total_fks} foreign keys for {len(tables_to_migrate)} tables")
                else:
                    logs.append("⚠️ No foreign keys found to migrate")
                
            except Exception as e:
                logs.append(f"❌ Error: {str(e)}")
                postgres.connection.rollback()
        
        progress_bar.progress(1.0)
        log_area.text_area("Log", "\n".join(logs), height=200)
        
        mysql.close()
        postgres.close()
        
        st.success("✅ Constraints migrated!")
        st.balloons()
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

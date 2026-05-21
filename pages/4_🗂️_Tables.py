"""
🗂️ Tables Migration Page
Migrate table structures (DDL)
"""

import streamlit as st
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages import check_prerequisites
from dbmigrator.configuration_management.configuration import MigrationConfig
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection
from dbmigrator.data_migration.mysql_to_postgresql import MySQLToPostgreSQL

st.title("🗂️ Migrate Tables (Structure)")

# Verificar pré-requisitos e carregar config
check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True)
config = st.session_state.config

st.info("📝 Create table structures in PostgreSQL (CREATE TABLE statements)")

tables = st.session_state.tables_metadata
selected_tables = st.session_state.get('selected_tables', [t.name for t in tables])

st.subheader(f"📋 Tables to Migrate: {len([t for t in tables if t.name in selected_tables])}")

st.markdown("---")

# Botão de migração
if st.button("🚀 Migrate Table Structures", type="primary", width="stretch"):
    try:
        # Verificar conexões
        if 'mysql_conn' not in st.session_state or st.session_state.mysql_conn is None:
            st.error("❌ Please configure MySQL connection first!")
            st.stop()
        if 'postgres_conn' not in st.session_state or st.session_state.postgres_conn is None:
            st.error("❌ Please configure PostgreSQL connection first!")
            st.stop()
        
        # Criar conexões
        mysql = MySQLConnection(st.session_state.mysql_conn)
        mysql.create()
        
        postgres = PostgreSQLConnection(st.session_state.postgres_conn)
        postgres.create()
        
        # Área de progresso
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()
        
        logs = []
        
        # Tentar ativar PostGIS se houver colunas geometry
        status_text.text("Checking for geometry columns...")
        has_geometry = any(
            any('geometry' in col.data_type.lower() or 'point' in col.data_type.lower() 
                for col in t.columns if col.data_type)
            for t in [t for t in tables if t.name in selected_tables]
        )
        
        if has_geometry:
            status_text.text("Enabling PostGIS extension...")
            try:
                cursor = postgres.connection.cursor()
                cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
                postgres.connection.commit()
                cursor.close()
                logs.append("✅ PostGIS extension enabled")
                log_area.text_area("Migration Log", "\n".join(logs), height=300)
            except Exception as e:
                error_msg = str(e)
                logs.append(f"❌ PostGIS Error: {error_msg}")
                log_area.text_area("Migration Log", "\n".join(logs), height=300)
                
                st.error(f"❌ Failed to enable PostGIS extension: {error_msg}")
                st.info("""
                💡 **TIP**: PostGIS extension not available. Please check:
                
                1. **Install PostGIS on your system:**
                   ```bash
                   # Ubuntu/Debian
                   sudo apt-get install postgresql-15-postgis-3
                   
                   # CentOS/RHEL
                   sudo yum install postgis33_15
                   
                   # macOS
                   brew install postgis
                   ```
                
                2. **Verify installation:**
                   ```sql
                   SELECT * FROM pg_available_extensions WHERE name = 'postgis';
                   ```
                
                3. **Manual installation** if needed, then retry the migration.
                """)
                st.stop()
        
        # Criar migrator
        migration = MySQLToPostgreSQL(mysql, postgres)
        tables_to_migrate = [t for t in tables if t.name in selected_tables]
        migration.tables = tables_to_migrate
        schema = st.session_state.get('schema_name', config.schema_name)
        total = len(tables_to_migrate)
        
        # Gerar DDLs
        status_text.text("Generating DDL statements...")
        migration.generate_DDLs(schema)
        logs.append("✓ DDL statements generated")
        progress_bar.progress(0.2)
        
        # Executar ENUMs
        status_text.text("Creating ENUMs...")
        try:
            migration.execute_DDL_enums()
            logs.append("✅ ENUMs created")
        except Exception as e:
            logs.append(f"⚠️ ENUMs: {str(e)}")
        progress_bar.progress(0.4)
        log_area.text_area("Migration Log", "\n".join(logs[-20:]), height=300)
        
        # Executar tabelas
        status_text.text("Creating tables...")
        try:
            migration.execute_DDL_tables()
            # Fazer commit das mudanças
            postgres.connection.commit()
            logs.append(f"✅ {total} tables created successfully")
        except Exception as e:
            postgres.connection.rollback()
            logs.append(f"❌ Tables failed: {str(e)}")
        
        progress_bar.progress(1.0)
        log_area.text_area("Migration Log", "\n".join(logs[-20:]), height=300)
        
        # Fechar conexões
        mysql.close()
        postgres.close()
        
        status_text.text("✅ Migration completed!")
        st.success(f"✅ Migrated {total} table structures successfully!")
        st.balloons()
        
    except Exception as e:
        st.error(f"❌ Error during migration: {str(e)}")
else:
    # Mostrar prévia das tabelas
    with st.expander("📋 View Tables to Migrate"):
        for table in [t for t in tables if t.name in selected_tables]:
            st.text(f"• {table.name} ({table.num_tuples:,} rows, {len(table.columns)} columns)")

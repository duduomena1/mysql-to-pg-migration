"""
🔢 Sequences Migration Page
Migrate and synchronize auto-increment sequences
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

st.title("🔢 Migrate Sequences")

# Verificar pré-requisitos e carregar config
check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True)

config = st.session_state.config
tables = st.session_state.tables_metadata
selected_tables = st.session_state.get('selected_tables', [t.name for t in tables])

st.info("🔢 Synchronize auto-increment sequences from MySQL to PostgreSQL")

tables_to_migrate = [t for t in tables if t.name in selected_tables and t.num_sequence]
st.metric("Tables with Sequences", len(tables_to_migrate))

# Lista de tabelas selecionadas
if tables_to_migrate:
    with st.expander(f"📋 Tables to Process ({len(tables_to_migrate)} selected)"):
        cols = st.columns(4)
        for idx, table in enumerate(tables_to_migrate):
            with cols[idx % 4]:
                st.text(f"🔢 {table.name}")
    
    st.markdown("---")

if tables_to_migrate:
    if st.button("🚀 Migrate Sequences", type="primary", width="stretch"):
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
            
            for idx, table in enumerate(tables_to_migrate):
                try:
                    # Fazer rollback antes de cada operação para limpar transação abortada
                    try:
                        postgres.connection.rollback()
                    except:
                        pass
                    
                    # Verificar se a sequence existe, se não, criar
                    cursor = postgres.connection.cursor()
                    schema_prefix = f"{config.schema_name}." if config.schema_name else ""
                    
                    # Verificar se sequence existe
                    check_seq = f"""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_sequences 
                        WHERE schemaname = '{config.schema_name}' 
                        AND sequencename = '{table.name}_id_seq'
                    )
                    """
                    cursor.execute(check_seq)
                    sequence_exists = cursor.fetchone()[0]
                    
                    if not sequence_exists:
                        # Criar a sequence se não existir
                        create_seq = f"CREATE SEQUENCE {schema_prefix}{table.name}_id_seq"
                        cursor.execute(create_seq)
                        
                        # Vincular ao campo id
                        alter_table = f"ALTER TABLE {schema_prefix}{table.name} ALTER COLUMN id SET DEFAULT nextval('{schema_prefix}{table.name}_id_seq')"
                        cursor.execute(alter_table)
                        
                        logs.append(f"📝 Created sequence for {table.name}")
                    
                    cursor.close()
                    
                    # Agora sincronizar o valor da sequence
                    migration.set_sequence_table(table, config.schema_name)
                    postgres.connection.commit()
                    logs.append(f"✅ {table.name} (sequence: {table.num_sequence})")
                except Exception as e:
                    logs.append(f"❌ {table.name}: {str(e)}")
                    # Fazer rollback após erro
                    try:
                        postgres.connection.rollback()
                    except:
                        pass
                
                progress_bar.progress((idx + 1) / len(tables_to_migrate))
                log_area.text_area("Log", "\n".join(logs[-15:]), height=200)
            
            mysql.close()
            postgres.close()
            
            st.success("✅ Sequences migrated!")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
else:
    st.info("ℹ️ No tables with auto-increment sequences found")

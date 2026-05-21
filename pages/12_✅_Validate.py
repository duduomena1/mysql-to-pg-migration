"""
✅ Validate Page
Validate migration results
"""

import streamlit as st
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages import check_prerequisites
from dbmigrator.configuration_management.configuration import MigrationConfig
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection

st.title("✅ Validate Migration")

# Verificar pré-requisitos e carregar config
check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True)

config = st.session_state.config
mysql_credentials = st.session_state.mysql_conn
postgres_credentials = st.session_state.postgres_conn

st.info("✅ Compare row counts between MySQL and PostgreSQL")

tables = st.session_state.tables_metadata
selected_tables = st.session_state.get('selected_tables', [t.name for t in tables])

if st.button("🔍 Validate Migration", type="primary", width="stretch"):
    try:
        # Conectar aos bancos
        with st.spinner("Connecting..."):
            mysql = MySQLConnection(mysql_credentials)
            mysql.create()
            
            postgres = PostgreSQLConnection(postgres_credentials)
            postgres.create()
        
        results = []
        progress_bar = st.progress(0)
        
        for idx, table in enumerate([t for t in tables if t.name in selected_tables]):
            # Count MySQL
            mysql_cursor = mysql.connection.cursor()
            mysql_cursor.execute(f"SELECT COUNT(*) FROM {mysql_credentials.database}.{table.name}")
            mysql_count = mysql_cursor.fetchone()[0]
            mysql_cursor.close()
            
            # Count PostgreSQL
            pg_cursor = postgres.connection.cursor()
            pg_cursor.execute(f"SELECT COUNT(*) FROM {config.schema_name}.{table.name}")
            pg_count = pg_cursor.fetchone()[0]
            pg_cursor.close()
            
            # Comparar
            match = mysql_count == pg_count
            results.append({
                "Table": table.name,
                "MySQL": mysql_count,
                "PostgreSQL": pg_count,
                "Status": "✅ Match" if match else "❌ Mismatch"
            })
            
            progress_bar.progress((idx + 1) / len(selected_tables))
        
        mysql.close()
        postgres.close()
        
        # Mostrar resultados
        st.markdown("---")
        st.subheader("📊 Validation Results")
        
        import pandas as pd
        df = pd.DataFrame(results)
        
        # Estilo condicional
        def highlight_mismatch(row):
            if "❌" in row['Status']:
                return ['background-color: #ffcccc'] * len(row)
            return [''] * len(row)
        
        styled_df = df.style.apply(highlight_mismatch, axis=1)
        st.dataframe(styled_df, width="stretch")
        
        # Resumo
        total = len(results)
        matched = sum(1 for r in results if "✅" in r['Status'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Tables", total)
        with col2:
            st.metric("Matched", matched)
        with col3:
            st.metric("Mismatched", total - matched)
        
        if matched == total:
            st.success("🎉 All tables validated successfully!")
            st.balloons()
        else:
            st.warning(f"⚠️ {total - matched} table(s) have mismatched row counts")
            
    except Exception as e:
        st.error(f"❌ Error during validation: {str(e)}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())
        
    except Exception as e:
        st.error(f"❌ Error during validation: {str(e)}")

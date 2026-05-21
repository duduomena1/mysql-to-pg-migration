"""
📊 Conversion Page  
Load table metadata and manage table selection
"""

import streamlit as st
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pages import ensure_config_loaded
from dbmigrator.configuration_management.configuration import MigrationConfig
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_access.mysql_metadata_reader import mysql_fetch_tables
from dbmigrator.structure_conversion.table_to_json import save_json_file, save_migration_order, load_json_file
from dbmigrator.structure_conversion.dependency_resolver import DependencyResolver

st.title("📊 Conversion & Metadata")

# Sempre carregar config do arquivo
ensure_config_loaded()
config = st.session_state.config

# Tentar carregar metadata existente automaticamente
if 'tables_metadata' not in st.session_state and os.path.exists(config.json_name):
    try:
        st.session_state.tables_metadata = load_json_file(config.json_name)
        st.session_state.selected_tables = [t.name for t in st.session_state.tables_metadata]
    except:
        pass

st.info("📥 Load table metadata from MySQL and select tables for migration")

# Mostrar tabelas excluídas
if config.excluded_tables:
    with st.expander(f"🚫 Excluded Tables ({len(config.excluded_tables)})"):
        cols = st.columns(4)
        for idx, table in enumerate(config.excluded_tables):
            with cols[idx % 4]:
                st.text(f"• {table}")

# Botões de ação principais
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🔄 Load Metadata from MySQL", type="primary", width="stretch"):
        try:
            # Verificar se temos conexão MySQL
            if 'mysql_conn' not in st.session_state or st.session_state.mysql_conn is None:
                st.error("❌ Please configure MySQL connection first!")
                st.stop()
            
            with st.spinner("Loading table metadata from MySQL..."):
                # Conectar ao MySQL
                mysql = MySQLConnection(st.session_state.mysql_conn)
                mysql.create()
                
                # Carregar metadados JÁ filtrados pela função
                tables = mysql_fetch_tables(mysql, excluded_tables=config.excluded_tables)
                
                # Salvar em JSON
                save_json_file(tables, config.json_name)
                
                # Salvar no session state
                st.session_state.tables_metadata = tables
                st.session_state.selected_tables = [t.name for t in tables]
                
                mysql.close()
                
                # Mostrar quantas tabelas foram excluídas
                total_excluded = len(config.excluded_tables)
                st.success(f"✅ Loaded {len(tables)} tables successfully! ({total_excluded} excluded)")
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error loading metadata: {str(e)}")

with col2:
    if st.button("🔗 Generate Migration Order", width="stretch"):
        if 'tables_metadata' not in st.session_state:
            st.warning("⚠️ Please load metadata first")
        else:
            try:
                with st.spinner("Analyzing table dependencies..."):
                    tables = st.session_state.tables_metadata
                    resolver = DependencyResolver(tables)
                    migration_order = resolver.get_migration_order()
                    
                    # Salvar ordem
                    save_migration_order(migration_order, "migration_order.json")
                    
                    st.session_state.migration_order = migration_order
                    st.success(f"✅ Migration order generated with {len(migration_order)} levels!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

with col3:
    # Checkbox de confirmação ANTES do botão
    confirm_clear = st.checkbox("⚠️ Confirm deletion", key="confirm_clear")
    
    if st.button("🗑️ Clear Metadata", width="stretch", disabled=not confirm_clear):
        try:
            from dbmigrator.structure_conversion.csv_utils import folder_name
            
            removed_files = []
            
            # Remover arquivos de metadados
            if os.path.exists(config.json_name):
                os.remove(config.json_name)
                removed_files.append(config.json_name)
            if os.path.exists("migration_order.json"):
                os.remove("migration_order.json")
                removed_files.append("migration_order.json")
            if os.path.exists("progress.json"):
                os.remove("progress.json")
                removed_files.append("progress.json")
            
            # Remover arquivos CSV
            csv_count = 0
            if os.path.exists(folder_name):
                csv_files = [f for f in os.listdir(folder_name) if f.endswith('.csv')]
                for csv_file in csv_files:
                    os.remove(os.path.join(folder_name, csv_file))
                    csv_count += 1
            
            # Limpar session state
            if 'tables_metadata' in st.session_state:
                del st.session_state.tables_metadata
            if 'migration_order' in st.session_state:
                del st.session_state.migration_order
            if 'selected_tables' in st.session_state:
                del st.session_state.selected_tables
                
            st.success(f"✅ Cleared {len(removed_files)} metadata files and {csv_count} CSV files!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

st.markdown("---")

# Mostrar tabelas carregadas
if 'tables_metadata' in st.session_state:
    tables = st.session_state.tables_metadata
    
    st.subheader(f"📋 Loaded Tables ({len(tables)})")
    
    # Inicializar selected_tables se não existir
    if 'selected_tables' not in st.session_state:
        st.session_state.selected_tables = [t.name for t in tables]
    
    # Filtro de busca
    search = st.text_input("🔍 Search tables", placeholder="Type to filter...")
    
    # Mostrar contagem atual para debug
    st.caption(f"Currently selected: {len(st.session_state.selected_tables)} tables")
    
    # Inicializar contador de refresh se não existir
    if 'checkbox_refresh' not in st.session_state:
        st.session_state.checkbox_refresh = 0
    
    # Botões de seleção em massa
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        if st.button("✅ Select All", width="stretch", key="btn_select_all"):
            st.session_state.selected_tables = [t.name for t in tables]
            st.session_state.checkbox_refresh += 1  # Forçar refresh dos checkboxes
            st.toast(f"✅ Selected all {len(tables)} tables!")
            st.rerun()
    with col_sel2:
        if st.button("❌ Deselect All", width="stretch", key="btn_deselect_all"):
            st.session_state.selected_tables = []
            st.session_state.checkbox_refresh += 1  # Forçar refresh dos checkboxes
            st.toast("❌ Deselected all tables!")
            st.rerun()
    
    # Filtrar tabelas
    filtered_tables = [t for t in tables if not search or search.lower() in t.name.lower()]
    
    # Callback para atualizar seleção
    def toggle_table(table_name):
        if table_name in st.session_state.selected_tables:
            st.session_state.selected_tables.remove(table_name)
        else:
            st.session_state.selected_tables.append(table_name)
    
    # Exibir tabelas em grid (key única com refresh counter)
    cols_per_row = 3
    for i in range(0, len(filtered_tables), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < len(filtered_tables):
                table = filtered_tables[i + j]
                with col:
                    # Checkbox com callback e key dinâmica
                    st.checkbox(
                        f"**{table.name}**",
                        value=table.name in st.session_state.selected_tables,
                        key=f"table_{table.name}_{st.session_state.checkbox_refresh}",
                        on_change=toggle_table,
                        args=(table.name,)
                    )
                    
                    st.caption(f"📊 {table.num_tuples:,} rows")
                    st.caption(f"📋 {len(table.columns)} columns")
    
    # Resumo de seleção
    st.markdown("---")
    col_info1, col_info2, col_info3 = st.columns(3)
    
    with col_info1:
        st.metric("Total Tables", len(tables))
    with col_info2:
        st.metric("Selected", len(st.session_state.selected_tables))
    with col_info3:
        total_rows = sum(t.num_tuples for t in tables if t.name in st.session_state.selected_tables)
        st.metric("Total Rows", f"{total_rows:,}")
    
else:
    st.info("👆 Click 'Load Metadata from MySQL' to start")

# Mostrar ordem de migração se existir
if 'migration_order' in st.session_state:
    st.markdown("---")
    st.subheader("🔗 Migration Order (by FK dependencies)")
    
    migration_order = st.session_state.migration_order
    
    for level_idx, level_tables in enumerate(migration_order):
        with st.expander(f"**Level {level_idx + 1}** - {len(level_tables)} tables"):
            st.write(", ".join(level_tables))

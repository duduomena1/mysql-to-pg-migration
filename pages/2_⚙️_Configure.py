"""
⚙️ Configure Page
Configure migration options and settings
"""

import streamlit as st
from dbmigrator.configuration_management.configuration import MigrationConfig

st.title("⚙️ Configure Migration")

if 'config' not in st.session_state:
    st.error("❌ No configuration found. Please set up connections first!")
    st.stop()

config = st.session_state.config

st.info("📝 Configure migration settings, batch sizes, and table filters")

# Seção: Batch Sizes
st.subheader("📦 Batch & Bulk Sizes")

col1, col2 = st.columns(2)

with col1:
    st.markdown("##### MySQL Settings")
    mysql_batch = st.number_input(
        "MySQL Batch Size",
        min_value=100,
        max_value=50000,
        value=config.mysql_batch_size,
        step=100,
        help="Number of rows to read from MySQL at once"
    )
    
with col2:
    st.markdown("##### PostgreSQL Settings")
    postgres_bulk = st.number_input(
        "PostgreSQL Bulk Size",
        min_value=100,
        max_value=50000,
        value=config.postgres_bulk_size,
        step=100,
        help="Number of rows to write to PostgreSQL at once"
    )

st.markdown("---")

# Seção: Schema
st.subheader("🗂️ PostgreSQL Schema")

schema_name = st.text_input(
    "Schema Name",
    value=config.schema_name,
    help="PostgreSQL schema where tables will be created"
)

st.markdown("---")

# Seção: Table Filters
st.subheader("🎯 Table Filters")

st.markdown("##### Excluded Tables")
excluded_tables_input = st.text_area(
    "Tables to exclude (one per line)",
    value="\n".join(config.excluded_tables) if config.excluded_tables else "",
    height=100,
    help="These tables will NOT be migrated"
)

st.markdown("---")

# Seção: Advanced Options
with st.expander("🔧 Advanced Options"):
    st.markdown("##### File Paths")
    
    col_adv1, col_adv2 = st.columns(2)
    
    with col_adv1:
        metadata_json = st.text_input(
            "Metadata JSON File",
            value=getattr(config, 'json_name', 'metadata.json'),
            help="File to store table metadata"
        )
        
        progress_json = st.text_input(
            "Progress JSON File", 
            value=getattr(config, 'progress_json_name', 'progress.json'),
            help="File to track migration progress"
        )
    
    with col_adv2:
        bulk_commit = st.checkbox(
            "Bulk Commit",
            value=getattr(config, 'bulk_commit', True),
            help="Enable bulk commit for better performance"
        )

st.markdown("---")

# Botões de ação
col1, col2, col3 = st.columns([2, 1, 1])

with col2:
    if st.button("🔄 Reset to Defaults", width="stretch"):
        st.session_state.config = MigrationConfig.default_config()
        st.success("✅ Reset to default configuration")
        st.rerun()

with col3:
    if st.button("💾 Save Configuration", type="primary", width="stretch"):
        # Atualizar configuração
        config.mysql_batch_size = mysql_batch
        config.postgres_bulk_size = postgres_bulk
        config.schema_name = schema_name
        config.bulk_commit = bulk_commit
        
        # Processar listas de tabelas
        if excluded_tables_input.strip():
            config.excluded_tables = [t.strip() for t in excluded_tables_input.split('\n') if t.strip()]
        else:
            config.excluded_tables = []
        
        config.json_name = metadata_json
        config.progress_json_name = progress_json
        
        # Salvar
        config.save_to_file("config.json")
        st.session_state.config = config
        
        st.success("✅ Configuration saved successfully!")
        st.balloons()

# Visualização da configuração atual
st.markdown("---")
st.subheader("📋 Current Configuration Summary")

col_sum1, col_sum2, col_sum3 = st.columns(3)

with col_sum1:
    st.metric("MySQL Batch", f"{config.mysql_batch_size:,}")
    st.metric("Bulk Commit", "✅ Enabled" if getattr(config, 'bulk_commit', True) else "❌ Disabled")

with col_sum2:
    st.metric("PostgreSQL Bulk", f"{config.postgres_bulk_size:,}")
    st.metric("Excluded Tables", len(config.excluded_tables))

with col_sum3:
    st.metric("Schema", config.schema_name)
    st.metric("Config File", "config.json")

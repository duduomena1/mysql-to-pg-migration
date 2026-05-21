"""
MySQL → PostgreSQL Migration Tool - Streamlit Version
100% Python - Zero JavaScript

Run with: streamlit run app_streamlit.py
"""

import streamlit as st
import os
from dbmigrator.configuration_management.configuration import MigrationConfig

# Configuração da página
st.set_page_config(
    page_title="IPQ Migration Tool",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "MySQL to PostgreSQL Migration Tool v2.0 - Powered by Streamlit"
    }
)

# Carregar .env SEMPRE no início
from dotenv import load_dotenv
from dbmigrator.configuration_management.db_credentials import DBCredentials

load_dotenv()

# Inicializar session state e SEMPRE recarregar config do arquivo
config_path = "config.json"
if os.path.exists(config_path):
    # Sempre recarregar do arquivo para pegar mudanças
    st.session_state.config = MigrationConfig.from_json_file(config_path)
else:
    if 'config' not in st.session_state:
        st.session_state.config = MigrationConfig.default_config()

# Carregar credenciais MySQL (sempre do .env se existir)
mysql_host = os.getenv('MYSQL_HOST')
if mysql_host:
    st.session_state.mysql_conn = DBCredentials(
        database=os.getenv('MYSQL_DATABASE', ''),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', ''),
        host=mysql_host,
        port=os.getenv('MYSQL_PORT', '3306')
    )
    st.session_state.mysql_config = {
        'host': mysql_host,
        'port': os.getenv('MYSQL_PORT', '3306'),
        'database': os.getenv('MYSQL_DATABASE', ''),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', '')
    }
elif 'mysql_conn' not in st.session_state:
    st.session_state.mysql_conn = None
    st.session_state.mysql_config = {
        'host': 'localhost',
        'port': '3306',
        'database': '',
        'user': 'root',
        'password': ''
    }

# Carregar credenciais PostgreSQL (sempre do .env se existir)
postgres_host = os.getenv('POSTGRES_HOST')
if postgres_host:
    st.session_state.postgres_conn = DBCredentials(
        database=os.getenv('POSTGRES_DBNAME', ''),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        host=postgres_host,
        port=os.getenv('POSTGRES_PORT', '5432')
    )
    st.session_state.postgres_config = {
        'host': postgres_host,
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DBNAME', ''),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }
elif 'postgres_conn' not in st.session_state:
    st.session_state.postgres_conn = None
    st.session_state.postgres_config = {
        'host': 'localhost',
        'port': '5432',
        'database': '',
        'user': 'postgres',
        'password': ''
    }

# Inicializar schema_name
if 'schema_name' not in st.session_state:
    st.session_state.schema_name = st.session_state.config.schema_name

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.25rem;
        color: #721c24;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.25rem;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<h1 class="main-header">🔄 MySQL → PostgreSQL Migration Tool</h1>', unsafe_allow_html=True)

# Status da configuração
st.markdown("### 📊 Configuration Status")

col_status1, col_status2, col_status3 = st.columns(3)

with col_status1:
    if st.session_state.mysql_conn:
        st.success(f"✅ MySQL Connected\n\n`{st.session_state.mysql_config['database']}@{st.session_state.mysql_config['host']}`")
    else:
        st.warning("⚠️ MySQL Not Configured\n\nGo to Connection page")

with col_status2:
    if st.session_state.postgres_conn:
        st.success(f"✅ PostgreSQL Connected\n\n`{st.session_state.postgres_config['database']}@{st.session_state.postgres_config['host']}`")
    else:
        st.warning("⚠️ PostgreSQL Not Configured\n\nGo to Connection page")

with col_status3:
    if os.path.exists("metadata.json"):
        st.success(f"✅ Metadata Loaded\n\nGo to migration pages")
    else:
        st.info("ℹ️ Metadata Not Loaded\n\nGo to Conversion page")

st.markdown("---")

# Informação inicial
st.info("""
👈 **Use o menu lateral** para navegar entre as funcionalidades:
- 🔌 **Connection**: Configurar conexões com bancos de dados
- ⚙️ **Configure**: Ajustar batch sizes e filtros
- 📊 **Conversion**: Carregar estrutura das tabelas
- 🗂️ **Tables**: Migrar estruturas (CREATE TABLE)
- 📦 **Tuples**: Migrar dados completos
- ⚡ **Partial Migration**: Migração parcial por período (RECOMENDADO para grandes volumes)
- 🔑 **Primary Keys**: Migrar chaves primárias
- 🔗 **Constraints**: Migrar chaves estrangeiras
- 📑 **Indexes**: Migrar índices
- 🔢 **Sequences**: Sincronizar sequências
""")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("🎯 Version", "2.0")
with col2:
    st.metric("🐍 Stack", "100% Python")
with col3:
    st.metric("⚡ Performance", "10-20x faster (CSV)")

st.caption("© 2025 IPQ-Tecnologia - Made with Streamlit 🎈")

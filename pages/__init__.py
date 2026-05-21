"""
Utility functions for Streamlit pages
"""
import streamlit as st
import os
from dbmigrator.configuration_management.configuration import MigrationConfig


def ensure_config_loaded():
    """
    Garante que a configuração está sempre carregada do arquivo config.json
    Deve ser chamada no início de cada página
    """
    config_path = "config.json"
    if os.path.exists(config_path):
        # Sempre recarregar do arquivo para pegar mudanças
        st.session_state.config = MigrationConfig.from_json_file(config_path)
        return True
    else:
        # Criar config padrão se não existir
        if 'config' not in st.session_state:
            st.session_state.config = MigrationConfig.default_config()
        return False


def check_prerequisites(require_metadata=True, require_mysql=True, require_postgres=True):
    """
    Verifica se os pré-requisitos estão atendidos
    
    Args:
        require_metadata: Se True, verifica se metadata foi carregado
        require_mysql: Se True, verifica conexão MySQL
        require_postgres: Se True, verifica conexão PostgreSQL
    
    Returns:
        True se todos os requisitos estão OK, False caso contrário
    """
    from dotenv import load_dotenv
    from dbmigrator.configuration_management.db_credentials import DBCredentials
    
    # Sempre recarregar config primeiro
    ensure_config_loaded()
    
    # Carregar variáveis de ambiente do .env
    load_dotenv()
    
    # Carregar credenciais MySQL do .env automaticamente se não existir no session_state
    if require_mysql and ('mysql_conn' not in st.session_state or st.session_state.mysql_conn is None):
        mysql_host = os.getenv('MYSQL_HOST')
        if mysql_host:
            st.session_state.mysql_conn = DBCredentials(
                database=os.getenv('MYSQL_DATABASE', ''),
                user=os.getenv('MYSQL_USER', 'root'),
                password=os.getenv('MYSQL_PASSWORD', ''),
                host=mysql_host,
                port=os.getenv('MYSQL_PORT', '3306')
            )
    
    # Carregar credenciais PostgreSQL do .env automaticamente se não existir no session_state
    if require_postgres and ('postgres_conn' not in st.session_state or st.session_state.postgres_conn is None):
        postgres_host = os.getenv('POSTGRES_HOST')
        if postgres_host:
            st.session_state.postgres_conn = DBCredentials(
                database=os.getenv('POSTGRES_DBNAME', ''),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', ''),
                host=postgres_host,
                port=os.getenv('POSTGRES_PORT', '5432')
            )
    
    errors = []
    
    # Verificar metadata
    if require_metadata:
        if 'tables_metadata' not in st.session_state:
            # Tentar carregar do arquivo metadata.json
            metadata_path = st.session_state.config.json_name if 'config' in st.session_state else "metadata.json"
            if os.path.exists(metadata_path):
                from dbmigrator.structure_conversion.table_to_json import load_json_file
                st.session_state.tables_metadata = load_json_file(metadata_path)
                # Também carregar selected_tables
                if 'selected_tables' not in st.session_state:
                    st.session_state.selected_tables = [t.name for t in st.session_state.tables_metadata]
            else:
                errors.append("❌ Metadata not loaded. Please go to **📊 Conversion** page to load tables.")
    
    # Verificar MySQL (após tentar carregar do .env)
    if require_mysql and ('mysql_conn' not in st.session_state or st.session_state.mysql_conn is None):
        errors.append("❌ MySQL not configured. Please go to **🔌 Connection** page.")
    
    # Verificar PostgreSQL (após tentar carregar do .env)
    if require_postgres and ('postgres_conn' not in st.session_state or st.session_state.postgres_conn is None):
        errors.append("❌ PostgreSQL not configured. Please go to **🔌 Connection** page.")
    
    if errors:
        for error in errors:
            st.error(error)
        st.stop()
        return False
    
    return True

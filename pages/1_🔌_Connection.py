"""
🔌 Connection Configuration Page
Configure MySQL and PostgreSQL connections
"""

import streamlit as st
import json
import os
from dotenv import load_dotenv
from dbmigrator.data_migration.database_connections.mysql_connection import MySQLConnection
from dbmigrator.data_migration.database_connections.postgresql_connection import PostgreSQLConnection
from dbmigrator.configuration_management.db_credentials import DBCredentials

# Carregar variáveis de ambiente do .env
load_dotenv()

st.title("🔌 Database Connection")

# Inicializar conexões no session_state se não existirem
if 'mysql_config' not in st.session_state:
    st.session_state.mysql_config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': os.getenv('MYSQL_PORT', '3306'),
        'database': os.getenv('MYSQL_DATABASE', ''),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', '')
    }

if 'postgres_config' not in st.session_state:
    st.session_state.postgres_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DBNAME', ''),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', '')
    }

# Tabs para MySQL e PostgreSQL
tab1, tab2 = st.tabs(["🐬 MySQL", "🐘 PostgreSQL"])

with tab1:
    st.subheader("MySQL Configuration")
    
    # Mostrar se carregou do .env
    if os.getenv("MYSQL_HOST"):
        st.info("🔐 Credentials loaded from .env file")
    
    col1, col2 = st.columns(2)
    
    with col1:
        mysql_host = st.text_input("Host", value=st.session_state.mysql_config['host'], key="mysql_host")
        mysql_port = st.number_input("Port", value=int(st.session_state.mysql_config['port']), min_value=1, max_value=65535, key="mysql_port")
        mysql_database = st.text_input("Database", value=st.session_state.mysql_config['database'], key="mysql_db")
    
    with col2:
        mysql_user = st.text_input("User", value=st.session_state.mysql_config['user'], key="mysql_user")
        mysql_password = st.text_input("Password", value=st.session_state.mysql_config['password'], type="password", key="mysql_pass")
    
    if st.button("🔍 Test MySQL Connection", key="test_mysql"):
        try:
            # Criar conexão temporária
            mysql_conn = DBCredentials(
                database=mysql_database,
                user=mysql_user,
                password=mysql_password,
                host=mysql_host,
                port=str(mysql_port)
            )
            
            # Testar conexão
            mysql = MySQLConnection(mysql_conn)
            mysql.create()
            st.success(f"✅ Successfully connected to MySQL database '{mysql_database}'!")
            mysql.close()
            
            # Salvar no session_state
            st.session_state.mysql_config = {
                'host': mysql_host,
                'port': str(mysql_port),
                'database': mysql_database,
                'user': mysql_user,
                'password': mysql_password
            }
            st.session_state.mysql_conn = mysql_conn
        except Exception as e:
            st.error(f"❌ MySQL connection failed: {str(e)}")

with tab2:
    st.subheader("PostgreSQL Configuration")
    
    # Mostrar se carregou do .env
    if os.getenv("POSTGRES_HOST"):
        st.info("🔐 Credentials loaded from .env file")
    
    col1, col2 = st.columns(2)
    
    with col1:
        pg_host = st.text_input("Host", value=st.session_state.postgres_config['host'], key="pg_host")
        pg_port = st.number_input("Port", value=int(st.session_state.postgres_config['port']), min_value=1, max_value=65535, key="pg_port")
        pg_database = st.text_input("Database", value=st.session_state.postgres_config['database'], key="pg_db")
    
    with col2:
        pg_user = st.text_input("User", value=st.session_state.postgres_config['user'], key="pg_user")
        pg_password = st.text_input("Password", value=st.session_state.postgres_config['password'], type="password", key="pg_pass")
    
    pg_schema = st.text_input("Schema", value=os.getenv('POSTGRES_SCHEMA', 'public'), key="pg_schema")
    
    if st.button("🔍 Test PostgreSQL Connection", key="test_pg"):
        try:
            # Criar conexão temporária
            pg_conn = DBCredentials(
                database=pg_database,
                user=pg_user,
                password=pg_password,
                host=pg_host,
                port=str(pg_port)
            )
            
            # Testar conexão
            postgres = PostgreSQLConnection(pg_conn)
            postgres.create()
            st.success(f"✅ Successfully connected to PostgreSQL database '{pg_database}'!")
            postgres.close()
            
            # Salvar no session_state
            st.session_state.postgres_config = {
                'host': pg_host,
                'port': str(pg_port),
                'database': pg_database,
                'user': pg_user,
                'password': pg_password
            }
            st.session_state.postgres_conn = pg_conn
            st.session_state.schema_name = pg_schema
        except Exception as e:
            st.error(f"❌ PostgreSQL connection failed: {str(e)}")

st.markdown("---")

# Botão para salvar configuração
col1, col2 = st.columns([3, 1])

with col2:
    if st.button("💾 Save to Session", type="primary", width="stretch"):
        # Salvar todas as configurações no session_state
        st.session_state.mysql_config = {
            'host': mysql_host,
            'port': str(mysql_port),
            'database': mysql_database,
            'user': mysql_user,
            'password': mysql_password
        }
        
        st.session_state.postgres_config = {
            'host': pg_host,
            'port': str(pg_port),
            'database': pg_database,
            'user': pg_user,
            'password': pg_password
        }
        
        st.session_state.schema_name = pg_schema
        
        # Criar objetos de conexão
        st.session_state.mysql_conn = DBCredentials(
            database=mysql_database,
            user=mysql_user,
            password=mysql_password,
            host=mysql_host,
            port=str(mysql_port)
        )
        
        st.session_state.postgres_conn = DBCredentials(
            database=pg_database,
            user=pg_user,
            password=pg_password,
            host=pg_host,
            port=str(pg_port)
        )
        
        st.success("✅ Configuration saved to session!")
        st.balloons()

"""
💾 Backup Page
Backup and restore operations
"""

import streamlit as st
import os
import shutil
from dbmigrator.structure_conversion.csv_utils import folder_name

st.title("💾 Backup & Restore")

st.info("💾 Manage CSV backups and file operations")

# Tabs para diferentes operações
tab1, tab2, tab3 = st.tabs(["📂 Files", "🗑️ Clear", "📊 Status"])

with tab1:
    st.subheader("📂 Backup Files")
    
    if os.path.exists(folder_name):
        files = os.listdir(folder_name)
        csv_files = [f for f in files if f.endswith('.csv')]
        
        if csv_files:
            st.metric("CSV Files", len(csv_files))
            
            # Calcular tamanho total
            total_size = sum(os.path.getsize(os.path.join(folder_name, f)) for f in csv_files)
            st.metric("Total Size", f"{total_size / (1024*1024):.2f} MB")
            
            # Listar arquivos
            with st.expander("📋 View Files"):
                for file in sorted(csv_files):
                    file_path = os.path.join(folder_name, file)
                    file_size = os.path.getsize(file_path)
                    st.text(f"• {file} ({file_size / (1024*1024):.2f} MB)")
        else:
            st.info("No CSV files found")
    else:
        st.info(f"Backup folder '{folder_name}' does not exist")

with tab2:
    st.subheader("🗑️ Clear Operations")
    
    st.warning("⚠️ These operations cannot be undone!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🗑️ Clear CSV Files**")
        if st.button("🗑️ Delete All CSV Files", type="secondary", width="stretch"):
            try:
                if os.path.exists(folder_name):
                    files = os.listdir(folder_name)
                    csv_files = [f for f in files if f.endswith('.csv')]
                    for file in csv_files:
                        os.remove(os.path.join(folder_name, file))
                    st.success(f"✅ Deleted {len(csv_files)} CSV files!")
                    st.rerun()
                else:
                    st.info("Folder does not exist")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    with col2:
        st.markdown("**🗑️ Clear Metadata & Progress**")
        
        # Mostrar quais arquivos existem antes
        files_to_remove = [
            "metadata.json",
            "progress.json",
            "migration_order.json",
            "partial_progress.json"
        ]
        
        existing_files = [f for f in files_to_remove if os.path.exists(f)]
        if existing_files:
            st.caption(f"📁 Found {len(existing_files)} files to delete")
        else:
            st.caption("📁 No metadata files found")
        
        if st.button("🗑️ Delete All Metadata", type="secondary", width="stretch", key="btn_delete_metadata"):
            with st.spinner("Deleting files..."):
                try:
                    st.write(f"🔍 Debug: Button clicked! folder_name = {folder_name}")
                    
                    removed = 0
                    removed_files = []
                    not_found = []
                    
                    # Remover arquivos de metadados e progress
                    for file in files_to_remove:
                        if os.path.exists(file):
                            st.write(f"🗑️ Deleting: {file}")
                            os.remove(file)
                            removed += 1
                            removed_files.append(file)
                        else:
                            not_found.append(file)
                    
                    # Remover arquivos CSV da pasta data
                    csv_removed = 0
                    if os.path.exists(folder_name):
                        csv_files = [f for f in os.listdir(folder_name) if f.endswith('.csv')]
                        st.write(f"🔍 Found {len(csv_files)} CSV files in {folder_name}")
                        for csv_file in csv_files:
                            csv_path = os.path.join(folder_name, csv_file)
                            st.write(f"🗑️ Deleting CSV: {csv_path}")
                            os.remove(csv_path)
                            csv_removed += 1
                    else:
                        st.write(f"⚠️ Folder {folder_name} does not exist")
                    
                    # Limpar session state também
                    cleared_state = []
                    if 'tables_metadata' in st.session_state:
                        del st.session_state.tables_metadata
                        cleared_state.append('tables_metadata')
                    if 'migration_order' in st.session_state:
                        del st.session_state.migration_order
                        cleared_state.append('migration_order')
                    if 'selected_tables' in st.session_state:
                        del st.session_state.selected_tables
                        cleared_state.append('selected_tables')
                    
                    if removed > 0:
                        st.success(f"✅ Deleted {removed} metadata files: {', '.join(removed_files)}")
                    if csv_removed > 0:
                        st.success(f"✅ Deleted {csv_removed} CSV files from {folder_name}")
                    if cleared_state:
                        st.info(f"🧹 Cleared session state: {', '.join(cleared_state)}")
                    if not_found:
                        st.info(f"ℹ️ Not found: {', '.join(not_found)}")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

with tab3:
    st.subheader("📊 System Status")
    
    # Verificar arquivos de configuração
    config_files = {
        "config.json": "Configuration",
        "metadata.json": "Table Metadata",
        "migration_order.json": "Migration Order",
        "partial_progress.json": "Partial Progress"
    }
    
    for file, desc in config_files.items():
        if os.path.exists(file):
            size = os.path.getsize(file)
            st.success(f"✅ {desc}: {size} bytes")
        else:
            st.warning(f"⚠️ {desc}: Not found")
    
    st.markdown("---")
    
    # Estatísticas de CSV
    if os.path.exists(folder_name):
        csv_count = len([f for f in os.listdir(folder_name) if f.endswith('.csv')])
        st.metric("CSV Backups", csv_count)

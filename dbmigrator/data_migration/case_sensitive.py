import mysql.connector
from typing import Dict, List

def get_tables_with_uppercase(mysql_connection) -> List[str]:
    """
    Get all table names that contain uppercase letters
    """
    cursor = mysql_connection.cursor()
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    
    # Filter tables with uppercase letters
    uppercase_tables = [table for table in tables if table != table.lower()]
    cursor.close()
    
    return uppercase_tables

def normalize_table_names_for_postgres(mysql_connection, table_list: List[str]) -> Dict[str, str]:
    """
    Normalize table names to lowercase for PostgreSQL compatibility
    and store original names mapping for restoration
    """
    original_names = {}
    cursor = mysql_connection.cursor()
    
    for table in table_list:
        if table != table.lower():
            # Store original name mapping
            original_names[table.lower()] = table
            
            # Rename table to lowercase
            cursor.execute(f"ALTER TABLE `{table}` RENAME TO `{table.lower()}`")
    
    mysql_connection.commit()
    cursor.close()
    
    return original_names

def restore_table_names(mysql_connection, original_names: Dict[str, str]):
    """
    Restore tables to their original case-sensitive names
    """
    cursor = mysql_connection.cursor()
    
    for lowercase_name, original_name in original_names.items():
        if lowercase_name != original_name:
            cursor.execute(f"ALTER TABLE `{lowercase_name}` RENAME TO `{original_name}`")
    
    mysql_connection.commit()
    cursor.close()
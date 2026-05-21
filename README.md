# MYSQLPG-MIGRATION
---

## Overview

This project is a Python-based Database Migration System with a modern Streamlit web interface. It facilitates complete MySQL to PostgreSQL database migrations including schema, data, constraints, indexes, and sequences. The system utilizes Poetry for dependency management and provides an intuitive UI for managing the entire migration process.

## Installation and Setup

### Dependencies
This project employs Poetry for dependency management. Ensure you have Poetry installed in your environment. If not, you can install it by following the instructions on the [Poetry documentation](https://python-poetry.org/docs/).
 - python
 - poetry
 - libpq-dev 
 - gcc 
 - python3-dev



### Installation Steps

1. **Clone the Repository:**

```bash
git clone git@github.com:IPQ-Tecnologia/mysqlpg-migration.git
```

2. **Navigate to the Project Directory:**

```bash
cd mysqlpg-migration
```

3. **Install System Dependencies (Ubuntu/Debian):**

```bash
sudo apt-get install libpq-dev gcc python3-dev
```

4. **Install Python Dependencies:**

```bash
poetry install
```

### Configuration

Before running the application, set up your environment:

1. **Create `.env` file** in the project root with database credentials:

```plaintext
# PostgreSQL Credentials
POSTGRES_DBNAME="your_database"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="your_password"
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"

# MySQL Credentials
MYSQL_DATABASE="your_database"
MYSQL_USER="root"
MYSQL_PASSWORD="your_password"
MYSQL_HOST="localhost"
MYSQL_PORT="3306"
```

2. **Review `config.json`** (created automatically on first run):

```json
{
  "schema_name": "public",
  "json_name": "metadata.json",
  "progress_name": "progress.json",
  "postgres_bulk_size": 10000,
  "mysql_batch_size": 5000,
  "bulk_commit": true,
  "excluded_tables": []
}
```

Key configuration parameters:
- `postgres_bulk_size`: Number of rows per batch insert (default: 10000)
- `mysql_batch_size`: Number of rows to fetch from MySQL at once (default: 5000)
- `excluded_tables`: List of table names to skip during migration

## Database Migration Flow

> [!IMPORTANT]
> The application automatically loads database credentials from the `.env` file on startup. Tables with uppercase letters are automatically handled during migration.

> [!WARNING]
> Always backup your databases before starting migration. The process modifies the target PostgreSQL database.

### Complete Migration Steps

Follow this order in the Streamlit UI:

1. **🔌 Connection** (Optional)
   - Credentials are auto-loaded from `.env`
   - Test connections to verify setup

2. **📊 Conversion**
   - Load metadata from MySQL
   - Select/deselect tables to migrate
   - Review table structures and row counts

3. **🗂️ Tables**
   - Migrate table schemas (CREATE TABLE statements)
   - Creates tables with proper column types

4. **📦 Tuples** 
   - Migrate table data (bulk insert with CSV)
   - Shows progress bar and detailed error reporting
   - Failed tables are logged with specific errors
   - Uses PostgreSQL COPY for ultra-fast loading (10-20x faster)

5. **🔑 Primary Keys**
   - Migrate primary key constraints
   - Creates sequences for auto-increment fields

6. **🔗 Constraints**
   - Migrate foreign key constraints
   - Ensures referential integrity

7. **📑 Indexes**
   - Migrate all indexes including GIST indexes
   - Improves query performance

8. **🔢 Sequences**
   - Update sequence values to match current data
   - Prevents duplicate key errors on new inserts

9. **✅ Validate**
   - Compare row counts between MySQL and PostgreSQL
   - Identify any mismatched tables
   - View detailed comparison report

10. **💾 Backup**
    - Export/import CSV backups
    - Clear metadata and progress files

### Migration Features

- **Automatic Error Recovery**: Each table migrates independently with transaction rollback on error
- **Progress Tracking**: Resume interrupted migrations from last successful point
- **Detailed Logging**: View specific errors for each failed table
- **NULL Handling**: Correctly converts NULL values between formats
- **Data Type Conversion**: Handles datetime, boolean, binary, geometry, and decimal types
- **Case Sensitivity**: Automatically handles table name case differences
- **Bulk Operations**: Uses configurable batch sizes for optimal performance

## Running the Application

### Streamlit Web Interface (Recommended)

To run the application with the modern Streamlit UI:

```bash
poetry run streamlit run app_streamlit.py
```

The application will automatically open in your browser at `http://localhost:8501`

### Alternative: Flask API (Legacy)

For the legacy Flask-based API:

```bash
poetry run python app.py
```

Accessible at `http://localhost:5000`

### Using the Shell Script

Quick start with the provided script:

```bash
chmod +x run.sh
./run.sh
```

## Troubleshooting

### Common Issues

**Problem**: `ERROR: current transaction is aborted, commands ignored until end of transaction block`
- **Solution**: Fixed automatically - each table now has independent transaction handling

**Problem**: Tables show NULL values as `\N` strings
- **Solution**: Updated - CSV format now correctly handles PostgreSQL NULL format

**Problem**: Configuration not persisting between pages
- **Solution**: Implemented automatic config reloading on page navigation

**Problem**: Checkboxes not updating when selecting/deselecting all
- **Solution**: Added refresh counter mechanism to force checkbox updates

**Problem**: Migration errors with datetime/timestamp fields
- **Solution**: Fixed CSV serialization to use PostgreSQL-compatible ISO format

### Performance Tips

1. **Adjust Batch Sizes**: Edit `config.json` to tune performance
   - Increase `postgres_bulk_size` for faster loading (up to 50000)
   - Decrease if running out of memory

2. **Use CSV Mode**: Always enabled by default for optimal speed

3. **Network Latency**: If databases are remote, consider increasing batch sizes

4. **Large Tables**: Migration progress is saved - you can safely stop and resume

## Project Structure

```
mysqlpg-migration/
├── app_streamlit.py          # Streamlit web interface entry point
├── app.py                     # Legacy Flask API
├── config.json                # Migration configuration
├── .env                       # Database credentials (create this)
├── pages/                     # Streamlit UI pages
│   ├── __init__.py           # Shared utilities (check_prerequisites, etc)
│   ├── 1_🔌_Connection.py
│   ├── 3_📊_Conversion.py
│   ├── 4_🗂️_Tables.py
│   ├── 5_📦_Tuples.py
│   ├── 7_🔑_Primary_Keys.py
│   ├── 8_🔗_Constraints.py
│   ├── 9_📑_Indexes.py
│   ├── 10_🔢_Sequences.py
│   ├── 11_💾_Backup.py
│   └── 12_✅_Validate.py
├── dbmigrator/               # Core migration logic
│   ├── data_migration/       # Data transfer modules
│   ├── data_access/          # Database connections
│   └── structure_conversion/ # Schema conversion utilities
├── data/                     # CSV export/import directory
├── metadata.json             # Table metadata cache
└── progress.json             # Migration progress tracking
```

## Contributing

When contributing to this project:

1. Maintain transaction safety in all database operations
2. Add error handling with proper rollback
3. Update UI to show detailed error messages
4. Test with both small and large datasets
5. Document any new configuration options

## License

This project is maintained by IPQ Tecnologia.

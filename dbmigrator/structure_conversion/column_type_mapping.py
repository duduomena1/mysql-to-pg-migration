mysql_to_pgsql_type_mapping = {
    'bigint(20)': 'BIGINT',
    'bigint(20) unsigned': 'BIGINT',  # Consider using a check constraint if necessary
    'date': 'DATE',
    'datetime': 'TIMESTAMP WITHOUT TIME ZONE',
    'double': 'DOUBLE PRECISION',
    'double unsigned': 'DOUBLE PRECISION',  # Consider check constraint for positive values
    'enum': 'TEXT',
    'geometry': 'public.geometry(Polygon,4326)', # Consider using PostGIS --> CREATE EXTENSION postgis;
    'int(10) unsigned': 'INTEGER',
    'int(11)': 'INTEGER',
    'longtext': 'TEXT',
    'mediumtext': 'TEXT',
    'point': 'public.geometry(Point,4326)',
    'text': 'TEXT',
    'timestamp': 'TIMESTAMP WITHOUT TIME ZONE',
    'tinyint(1)': 'boolean',  # Commonly used for boolean values in MySQL
    # For VARCHARs, directly map to VARCHAR with the same length
    'varchar(10)': 'VARCHAR(10)',
    'varchar(100)': 'VARCHAR(100)',
    'varchar(11)': 'VARCHAR(11)',
    'varchar(15)': 'VARCHAR(15)',
    'varchar(20)': 'VARCHAR(20)',
    'varchar(200)': 'VARCHAR(200)',
    'varchar(255)': 'VARCHAR(255)',
    'varchar(500)': 'VARCHAR(500)',
    'varchar(7)': 'VARCHAR(7)',
    'varchar(8)': 'VARCHAR(8)',

    # For ENUMs, map to TEXT
    "enum('A+','A-','B+','B-','AB+','AB-','O+','O-')": 'enum_blood_type',
    "enum('public','private','secret')": 'enum_level',
    "enum('lpr','ptz','context','bullet','dome')": 'enum_type',
    "enum('drug','object','organization','people','vehicle','weapon','animal')": 'enum_item_type',
    "enum('create','update','delete')": 'enum_operation',

    ######################################################3
    'datetime(3)':  'TIMESTAMP(3) WITHOUT TIME ZONE',
    'datetime(4)':  'TIMESTAMP(4) WITHOUT TIME ZONE',
    'timestamp(6)': 'TIMESTAMP(6) WITHOUT TIME ZONE',

    'decimal(4,2)': 'DECIMAL(4,2)',
    'decimal(5,3)': 'DECIMAL(5,3)',
    'decimal(10,0)': 'DECIMAL(10,0)',
    'decimal(10,8)': 'DECIMAL(10,8)',
    'decimal(11,8)': 'DECIMAL(11,8)',

    'float': 'FLOAT',

    'varchar(2)': 'VARCHAR(2)',
    'varchar(12)': 'VARCHAR(12)',
    'varchar(14)': 'VARCHAR(14)',
    'varchar(16)': 'VARCHAR(16)',
    'varchar(32)': 'VARCHAR(32)',
    'varchar(36)': 'VARCHAR(36)',
    'varchar(64)': 'VARCHAR(64)',
    'varchar(128)': 'VARCHAR(128)',
    'varchar(150)': 'VARCHAR(150)',
    'varchar(250)': 'VARCHAR(250)',
    'varchar(254)': 'VARCHAR(254)',
    'varchar(300)': 'VARCHAR(300)',
    'varchar(500)': 'VARCHAR(500)',
    'varchar(512)': 'VARCHAR(512)',
    'varchar(600)': 'VARCHAR(600)',

    'char(7)': 'CHARACTER(7)',
    'char(36)': 'CHARACTER(36)',

    'int(2)': 'INTEGER',
    'int(4)': 'INTEGER',
    'int(10)': 'INTEGER',
    'int(12)': 'INTEGER',

    'bigint(9)': 'BIGINT',


    'time': 'TIME',

    'polygon': 'public.geometry(Polygon,4326)',

    'smallint(6)': 'smallint'

}

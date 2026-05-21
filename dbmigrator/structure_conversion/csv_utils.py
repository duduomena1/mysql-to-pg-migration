import builtins
from datetime import datetime, date
from decimal import Decimal

csv_field_limit: int = 20*262144

folder_name = 'data'

type_conversion_map = {
    'NoneType': lambda x: None,
    'bytearray': lambda x: bytearray.fromhex(x.replace('\\x', '', 1)),  # Remove \x prefix
    'datetime': lambda x: datetime.fromisoformat(x),
    'date': lambda x: datetime.fromisoformat(x),
    'bool': lambda x: x == 'True' or x == 't',  # Support both formats
    'Decimal': lambda x: Decimal(x),
    'timedelta': lambda x: datetime.strptime(x, '%H:%M:%S').strftime("%H:%M:%S")
}


def _normalize_temporal_string(value: str, data_type: str) -> str:
    """
    Normaliza valores temporais em string para formato ISO aceito pelo PostgreSQL.
    """
    stripped = value.strip()
    data_type_lower = (data_type or '').lower()

    # Formatos de entrada comuns vindos de MySQL/CSV legado
    date_formats = [
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d-%m-%y',
        '%m-%d-%Y',
        '%m-%d-%y',
        '%d/%m/%Y',
        '%d/%m/%y',
    ]
    datetime_formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%d-%m-%Y %H:%M:%S',
        '%d-%m-%y %H:%M:%S',
        '%m-%d-%Y %H:%M:%S',
        '%m-%d-%y %H:%M:%S',
    ]

    def try_parse(formats):
        for fmt in formats:
            try:
                return datetime.strptime(stripped, fmt)
            except ValueError:
                continue
        return None

    if data_type_lower in ('date',):
        parsed = try_parse(date_formats)
        if parsed is not None:
            return parsed.strftime('%Y-%m-%d')

    if data_type_lower in ('datetime', 'timestamp'):
        parsed = try_parse(datetime_formats)
        if parsed is not None:
            return parsed.strftime('%Y-%m-%d %H:%M:%S')

        # Algumas colunas datetime podem vir sem horário
        parsed = try_parse(date_formats)
        if parsed is not None:
            return parsed.strftime('%Y-%m-%d 00:00:00')

    return value


def convert_to_type(value, type_name):
    # Try to get the type object from globals() dictionary
    return getattr(builtins, type_name)(value)


def deserialize_value(s):
    """
    Deserializes a value from a string with type information back to its original type.
    """
    # Handle PostgreSQL COPY NULL format
    if s == '\\N':
        return None
    
    # Check if the value has type information (contains ':')
    if ':' not in s:
        # No type prefix - return as is (for simple types like int, float, str)
        return s
    
    # Split only on the first ':'
    parts = s.split(':', 1)
    if len(parts) != 2:
        return s
    
    type_str, value_str = parts
    
    # Verificar se é realmente um tipo conhecido, senão retornar como string
    # (para evitar interpretar "2025-10-23 14:30:00" como tipo "2025-10-23 14")
    known_types = ['NoneType', 'bytearray', 'datetime', 'date', 'bool', 'Decimal', 'timedelta', 'int', 'float', 'str']
    if type_str not in known_types and not hasattr(builtins, type_str):
        # Não é um tipo válido, retornar o valor original
        return s
    
    # Handle NoneType
    if type_str == 'NoneType':
        return None
    
    if type_str == 'bytearray':
        # Convert hex string back to bytearray
        return bytearray.fromhex(value_str.replace('\\x', '', 1))
    
    if type_str in type_conversion_map:
        return type_conversion_map[type_str](value_str)

    # Tentar converter usando builtins
    try:
        return convert_to_type(value_str, type_str)
    except (AttributeError, ValueError, TypeError):
        # Se falhar, retornar o valor original
        return s


def _coerce_temporal_for_postgres(value, col):
    """
    Converte strings temporais em objetos Python (date/datetime) com base no tipo da coluna.
    Isso evita dependência de DateStyle no PostgreSQL.
    """
    if value is None or not isinstance(value, str):
        return value

    data_type_lower = (getattr(col, 'data_type', '') or '').lower()
    if data_type_lower not in ('date', 'datetime', 'timestamp'):
        return value

    normalized = _normalize_temporal_string(value, data_type_lower)

    if data_type_lower == 'date':
        try:
            return datetime.strptime(normalized, '%Y-%m-%d').date()
        except ValueError:
            return value

    # datetime/timestamp
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d'):
        try:
            parsed = datetime.strptime(normalized, fmt)
            if fmt == '%Y-%m-%d':
                return parsed.replace(hour=0, minute=0, second=0, microsecond=0)
            return parsed
        except ValueError:
            continue

    return value


def deserialize_row_with_columns(row, columns):
    """
    Deserializa uma linha do CSV e aplica coerção por tipo de coluna.
    """
    values = [deserialize_value(s) for s in row]
    return tuple(_coerce_temporal_for_postgres(value, col) for value, col in zip(values, columns))


def serialize_value(value, col):
    """
    Serializes a value to a string with type information.
    """
    if (col.nullable is False):
        if (value is None):
            if col.data_type == 'datetime':
                value = datetime.now().isoformat()

    # Handle None/NULL values - PostgreSQL COPY expects \N for NULL
    if value is None:
        return '\\N'

    # Handle tinyint(1) as boolean - PostgreSQL expects 't' or 'f'
    if col.data_type == 'tinyint(1)':
        return 't' if value == 1 else 'f'

    # Handle Python boolean type
    if isinstance(value, bool):
        return 't' if value else 'f'

    # Handle binary data - PostgreSQL COPY expects hex format: \xHEXSTRING
    if isinstance(value, bytes):
        return '\\x' + value.hex()

    if isinstance(value, bytearray):
        return '\\x' + value.hex()
    
    # Handle datetime and date - PostgreSQL can parse ISO format directly
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    
    if isinstance(value, date):
        return value.strftime('%Y-%m-%d')
    
    # Handle Decimal - PostgreSQL can parse numeric strings directly
    if isinstance(value, Decimal):
        return str(value)
    
    # For simple types (int, float, str), return the value directly
    # PostgreSQL COPY can handle these natively
    if isinstance(value, str):
        return _normalize_temporal_string(value, col.data_type)

    if isinstance(value, (int, float)):
        return str(value)
    
    # For any other type, use the type prefix format
    return f"{type(value).__name__}:{value}"

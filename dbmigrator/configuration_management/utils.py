import re


def numeric_or_string_value(s):
    try:
        float(s)
        return s
    except ValueError:
        return f"'{s}'"

def is_camel_case(word: str) -> bool:
    if not word or not isinstance(word, str):
        return False

    # Primeira letra precisa ser minúscula
    if not word[0].islower():
        return False

    # Só letras e números
    if not re.fullmatch(r"[A-Za-z0-9]+", word):
        return False

    # Não pode ter duas maiúsculas seguidas
    if re.search(r"[A-Z]{2,}", word):
        return False

    # Deve ter pelo menos uma letra maiúscula (indica mais de uma palavra)
    if not re.search(r"[A-Z]", word):
        return False

    return True

def format_reserved_word(word: str) -> str:
    # reserved_words = {'NAME', 'DEFAULT', 'ORDER', 'TYPE', 'KEY', 'GROUP'}
    reserved_words = {
        'NAME', 'DEFAULT', 'ORDER', 'TYPE', 'KEY', 'GROUP',
    'ABORT', 'ACCESS', 'ACTION', 'ADD', 'ADMIN', 'AFTER', 'AGGREGATE', 'ALL', 'ALSO', 'ALTER',
    'ANALYSE', 'ANALYZE', 'AND', 'ANY', 'ARRAY', 'AS', 'ASC', 'ASSERTION', 'ASSIGNMENT', 'ASYMMETRIC',
    'AT', 'AUTHORIZATION', 'BACKWARD', 'BINARY', 'BOTH', 'CASE', 'CAST', 'CHECK', 'COLLATE', 'COLLATION',
    'COLUMN', 'CONCURRENTLY', 'CONSTRAINT', 'CREATE', 'CROSS', 'CURRENT_CATALOG', 'CURRENT_DATE', 'CURRENT_ROLE',
    'CURRENT_SCHEMA', 'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'CURRENT_USER', 'DEFAULT', 'DEFERRABLE', 'DEFERRED',
    'DESC', 'DISTINCT', 'DO', 'ELSE', 'END', 'EXCEPT', 'FALSE', 'FETCH', 'FOR', 'FOREIGN', 'FREEZE', 'FROM',
    'FULL', 'GRANT', 'GROUP', 'HAVING', 'ILIKE', 'IN', 'INITIALLY', 'INNER', 'INTERSECT', 'INTO', 'IS', 'ISNULL',
    'JOIN', 'LATERAL', 'LEADING', 'LEFT', 'LIKE', 'LIMIT', 'LOCALTIME', 'LOCALTIMESTAMP', 'NATURAL', 'NOT', 'NOTNULL',
    'NULL', 'OFFSET', 'ON', 'ONLY', 'OR', 'ORDER', 'OUTER', 'OVERLAPS', 'PLACING', 'PRIMARY', 'REFERENCES', 'RETURNING',
    'RIGHT', 'SELECT', 'SESSION_USER', 'SIMILAR', 'SOME', 'SYMMETRIC', 'TABLE', 'TABLESAMPLE', 'THEN', 'TO', 'TRAILING',
    'TRUE', 'UNION', 'UNIQUE', 'USER', 'USING', 'VARIADIC', 'VERBOSE', 'WHEN', 'WHERE', 'WINDOW', 'WITH'
    }

    if word.upper() in reserved_words:
        return f'"{word}"'
    elif is_camel_case(word):
        return f'"{word}"'
    else:
        return word


def postgresql_GIST_indexes():
    return []

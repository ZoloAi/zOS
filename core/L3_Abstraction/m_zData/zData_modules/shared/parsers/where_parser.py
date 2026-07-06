# zOS/core/L3_Abstraction/m_zData/zData_modules/shared/parsers/where_parser.py
"""
WHERE clause parsing for zData query operations.

This module converts human-readable WHERE clause strings into adapter-compatible
dictionary formats. It supports multiple SQL-like operators and produces output
compatible with all backend adapters (SQLite, PostgreSQL, CSV).

Architecture Position
--------------------
- **Layer**: Tier 0 - Foundation
- **Dependencies**: value_parser.py (same package)
- **Used By**: CRUD read/update/delete operations, validator
- **Purpose**: Parse WHERE strings into structured filter dictionaries

Supported Operators
------------------
The parser supports a rich set of SQL-like comparison and logical operators:

**Logical Operators:**
- OR: Combines conditions with logical OR ("age > 18 OR status = admin")

**Comparison Operators:**
- =  : Equality ("name = John")
- != : Not equal ("status != inactive")
- >  : Greater than ("age > 18")
- <  : Less than ("age < 65")
- >= : Greater or equal ("score >= 90")
- <= : Less or equal ("score <= 100")

**Special Operators:**
- IS NULL     : Check for null ("email IS NULL")
- IS NOT NULL : Check for not null ("phone IS NOT NULL")
- LIKE        : Pattern matching ("name LIKE %John%")
- IN          : List membership ("status IN active,pending")

Output Format
------------
The parser produces dictionaries with special operator keys for non-equality:

Equality (no operator key):
    "name = John" → {"name": "John"}

Comparison operators (with $ prefix):
    "age > 18" → {"age": {"$gt": 18}}
    "score >= 90" → {"score": {"$gte": 90}}

Special operators:
    "email IS NULL" → {"email": None}
    "phone IS NOT NULL" → {"phone": {"$notnull": True}}
    "name LIKE %John%" → {"name": {"$like": "%John%"}}

Logical OR (with $or key):
    "age > 18 OR status = admin" → {"$or": [{"age": {"$gt": 18}}, {"status": "admin"}]}

Usage Examples
-------------
Basic equality:
    >>> parse_where_clause("name = John")
    {"name": "John"}

Comparison operators:
    >>> parse_where_clause("age >= 18")
    {"age": {"$gte": 18}}
    
    >>> parse_where_clause("score < 100")
    {"score": {"$lt": 100}}

NULL checks:
    >>> parse_where_clause("email IS NULL")
    {"email": None}
    
    >>> parse_where_clause("phone IS NOT NULL")
    {"phone": {"$notnull": True}}

LIKE pattern:
    >>> parse_where_clause("name LIKE %Smith%")
    {"name": {"$like": "%Smith%"}}

IN operator:
    >>> parse_where_clause("status IN active,pending")
    {"status": ["active", "pending"]}

OR conditions:
    >>> parse_where_clause("age > 18 OR status = admin")
    {"$or": [{"age": {"$gt": 18}}, {"status": "admin"}]}

Value Type Detection
-------------------
All values are automatically parsed to appropriate Python types via value_parser:
    "age = 42"     → {"age": 42}        (int)
    "price = 9.99" → {"price": 9.99}    (float)
    "active = true"→ {"active": True}   (bool)
    "name = John"  → {"name": "John"}   (str)

Security Notes
-------------
- Field names are passed through without sanitization (adapter responsibility)
- Values are type-converted but not SQL-escaped (adapter uses parameterized queries)
- No support for arbitrary SQL injection (limited operator set)

Limitations
----------
- No support for AND operator (all non-OR conditions are implicit AND)
- No support for parentheses or complex precedence
- No support for nested conditions beyond simple OR
- BETWEEN operator not implemented (use >= and <=)

Integration Points
-----------------
This parser is used by:
- crud_read.py: SELECT WHERE filtering
- crud_update.py: UPDATE WHERE conditions
- crud_delete.py: DELETE WHERE conditions
- DataValidator: Validation rule checking

See Also
--------
- value_parser.parse_value(): Type conversion for parsed values
- BaseDataAdapter: Backend adapter interface (uses parsed dictionaries)
"""

from zOS import Dict, Optional, Any, re

# Import from same directory
try:
    from .value_parser import parse_value
except ImportError:
    from value_parser import parse_value

# Operator-token SSOT (shared by all WHERE/filter evaluators)
try:
    from ..operators import (
        OP_AND, OP_OR, OP_LIKE, OP_NOTLIKE, OP_NIN, OP_NOTBETWEEN,
        OP_NOTNULL, OP_GTE, OP_LTE, OP_NE, OP_GT, OP_LT,
    )
except ImportError:  # pragma: no cover - flat import fallback
    from operators import (
        OP_AND, OP_OR, OP_LIKE, OP_NOTLIKE, OP_NIN, OP_NOTBETWEEN,
        OP_NOTNULL, OP_GTE, OP_LTE, OP_NE, OP_GT, OP_LT,
    )

# ============================================================
# Module Constants - SQL Keywords
# ============================================================

# Logical operator keywords (z-prefixed, case-sensitive — framework native)
_KEYWORD_ZAND = ' zAND '
_KEYWORD_ZOR = ' zOR '

# Legacy SQL keywords (backward compat only)
_KEYWORD_OR = " OR "
_KEYWORD_OR_UPPER = "OR"

# NULL check keywords
_KEYWORD_IS_NOT_NULL = " IS NOT NULL"
_KEYWORD_IS_NULL = " IS NULL"

# Special operator keywords (z-prefixed, case-sensitive — framework native)
_KEYWORD_ZLIKE = " zLIKE "
_KEYWORD_ZIN = " zIN "
_KEYWORD_ZBETWEEN = " zBETWEEN "
_KEYWORD_ZABOVE = " zABOVE "   # field zABOVE value → field > value
_KEYWORD_ZBELOW = " zBELOW "   # field zBELOW value → field < value
_KEYWORD_ZNULL = " zNULL"    # field zNULL  → IS NULL  (value is unknown)
_KEYWORD_ZKNOWN = " zKNOWN"  # field zKNOWN → IS NOT NULL (value is known)
# zBETWEEN uses zAND as its range separator: age zBETWEEN 25 zAND 35
# parse_zand_where re-merges BETWEEN parts so parse_single_where receives the full expression

# Negation keywords (zNOT prefix — checked before positive forms)
_KEYWORD_ZNOT_ZBETWEEN = " zNOT zBETWEEN "  # field zNOT zBETWEEN min zAND max
_KEYWORD_ZNOT_ZIN = " zNOT zIN "            # field zNOT zIN (val1, val2)
_KEYWORD_ZNOT_ZLIKE = " zNOT zLIKE "

# Legacy SQL operator keywords (backward compat only)
_KEYWORD_IN = " IN "
_KEYWORD_LIKE = " LIKE "

# ============================================================
# Module Constants - Comparison Operators
# ============================================================

# Comparison operator symbols (order matters - check longer first!)
_OPERATOR_GTE = ">="
_OPERATOR_LTE = "<="
_OPERATOR_NE = "!="
_OPERATOR_GT = ">"
_OPERATOR_LT = "<"
_OPERATOR_EQ = "="

# All comparison operators in order (longest first to avoid partial matches)
_COMPARISON_OPERATORS = [
    _OPERATOR_GTE,
    _OPERATOR_LTE,
    _OPERATOR_NE,
    _OPERATOR_GT,
    _OPERATOR_LT,
    _OPERATOR_EQ,
]

# ============================================================
# Module Constants - Operator Keys (Output Format)
# ============================================================

# Operator keys for dictionary output (MongoDB-style $ prefix).
# SSOT: shared/operators.py — all evaluators read these same tokens.
_KEY_AND = OP_AND
_KEY_OR = OP_OR
_KEY_LIKE = OP_LIKE
_KEY_NOTLIKE = OP_NOTLIKE
_KEY_NIN = OP_NIN
_KEY_NOTBETWEEN = OP_NOTBETWEEN
_KEY_NOTNULL = OP_NOTNULL
_KEY_GTE = OP_GTE
_KEY_LTE = OP_LTE
_KEY_NE = OP_NE
_KEY_GT = OP_GT
_KEY_LT = OP_LT

# Mapping from SQL operators to output keys
_OPERATOR_KEY_MAP = {
    _OPERATOR_GTE: _KEY_GTE,
    _OPERATOR_LTE: _KEY_LTE,
    _OPERATOR_NE: _KEY_NE,
    _OPERATOR_GT: _KEY_GT,
    _OPERATOR_LT: _KEY_LT,
    _OPERATOR_EQ: None,  # Equality has no key (direct value)
}

# ============================================================
# Module Constants - Regex Patterns
# ============================================================

# Pattern for splitting zOR/zAND conditions (case-sensitive, exact match)
_PATTERN_ZAND_SPLIT = r'\s+zAND\s+'
_PATTERN_ZOR_SPLIT = r'\s+zOR\s+'

# Pattern for splitting legacy OR conditions (case-insensitive)
_PATTERN_OR_SPLIT = r'\s+OR\s+'

# ============================================================
# Module Constants - Delimiters
# ============================================================

# Delimiter for IN operator value lists
_DELIMITER_IN_VALUES = ","

# ============================================================
# Public API
# ============================================================

__all__ = [
    "parse_where_clause",
    "parse_grouped_where",
    "parse_or_where",
    "parse_single_where",
]

def parse_where_clause(where_str: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse a WHERE clause string into an adapter-compatible dictionary.
    
    This is the main entry point for WHERE clause parsing. It automatically detects
    OR conditions and delegates to the appropriate parser.
    
    Args:
        where_str: The WHERE clause string to parse (without "WHERE" keyword).
                  Can be None or empty string (returns None).
    
    Returns:
        Dictionary representation of the WHERE clause, or None if input is empty.
        
        Format depends on operators used:
        - Simple equality: {"field": value}
        - Comparison: {"field": {"$op": value}}
        - OR conditions: {"$or": [condition1, condition2, ...]}
    
    Supported Operators:
        - Logical: OR
        - Comparison: =, !=, >, <, >=, <=
        - Special: IS NULL, IS NOT NULL, LIKE, IN
    
    Examples:
        Empty input:
            >>> parse_where_clause(None)
            None
            >>> parse_where_clause("")
            None
        
        Simple equality:
            >>> parse_where_clause("name = John")
            {"name": "John"}
        
        Comparison:
            >>> parse_where_clause("age >= 18")
            {"age": {"$gte": 18}}
        
        OR condition:
            >>> parse_where_clause("age > 18 OR status = admin")
            {"$or": [{"age": {"$gt": 18}}, {"status": "admin"}]}
        
        NULL check:
            >>> parse_where_clause("email IS NULL")
            {"email": None}
        
        LIKE pattern:
            >>> parse_where_clause("name LIKE %Smith%")
            {"name": {"$like": "%Smith%"}}
        
        IN list:
            >>> parse_where_clause("status IN active,pending")
            {"status": ["active", "pending"]}
    
    Notes:
        - Input is automatically stripped of leading/trailing whitespace
        - OR detection is case-insensitive (or, OR, Or all work)
        - Field names are case-preserved as provided
        - Values are automatically type-converted via parse_value()
        - Returns None for unparseable clauses (no exceptions)
    
    See Also:
        - parse_or_where(): Handles OR conditions
        - parse_single_where(): Handles single conditions
        - parse_value(): Type conversion for values
    """
    if not where_str:
        return None

    condition = where_str.strip()

    # Grouped precedence: (A zOR B) zAND C — parentheses override flat evaluation.
    # Guard: zIN (val1, val2) and zNOT zIN (val1, val2) use parens for value lists, not
    # grouping.  Strip those patterns first; only route to grouped parser if a bare ( remains.
    if '(' in condition:
        _stripped = re.sub(r'z(?:NOT\s+z)?IN\s*\([^)]*\)', '', condition)
        if '(' in _stripped:
            return parse_grouped_where(condition)

    # zOR: framework-native OR (case-sensitive, takes precedence)
    if _KEYWORD_ZOR in condition:
        return parse_zor_where(condition)

    # zAND: framework-native AND (case-sensitive) — merges multiple conditions
    if _KEYWORD_ZAND in condition:
        return parse_zand_where(condition)

    # Legacy OR support (case-insensitive, backward compat)
    if _KEYWORD_OR in condition.upper():
        return parse_or_where(condition)

    # Parse single condition
    return parse_single_where(condition)

def parse_grouped_where(where_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a WHERE clause that contains parenthesised groups for mixed AND/OR precedence.

    Parenthesised sub-expressions are extracted into placeholder tokens, the
    remaining flat string is split by the outer zAND/zOR operators, and then each
    placeholder is resolved recursively.  This avoids a full recursive-descent
    parser while still handling arbitrarily nested groups.

    Examples:
        >>> parse_grouped_where("(country = USA zOR country = Ireland) zAND score > 85")
        {"$and": [
            {"$or": [{"country": "USA"}, {"country": "Ireland"}]},
            {"score": {"$gt": 85}}
        ]}

        >>> parse_grouped_where("score > 90 zAND (city = Tokyo zOR city = Seoul)")
        {"$and": [
            {"score": {"$gt": 90}},
            {"$or": [{"city": "Tokyo"}, {"city": "Seoul"}]}
        ]}
    """
    # ── 1. Extract parenthesised groups into placeholders ──────────────────
    groups: Dict[str, str] = {}
    counter = [0]

    def _extract(s: str) -> str:
        result = []
        i = 0
        while i < len(s):
            if s[i] == '(':
                # Find matching closing paren (handles nesting)
                depth = 1
                j = i + 1
                while j < len(s) and depth:
                    if s[j] == '(':
                        depth += 1
                    elif s[j] == ')':
                        depth -= 1
                    j += 1
                inner = s[i + 1: j - 1]
                key = f'__zGROUP_{counter[0]}__'
                counter[0] += 1
                groups[key] = inner
                result.append(key)
                i = j
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    flat = _extract(where_str.strip())

    # ── 2. Resolve a token: placeholder → recursive parse, string → normal parse ──
    def _resolve(token: str) -> Optional[Dict[str, Any]]:
        token = token.strip()
        if token in groups:
            return parse_where_clause(groups[token])
        return parse_where_clause(token) if token else None

    # ── 3. Split the flattened string on the outermost zAND / zOR ─────────
    if _KEYWORD_ZAND in flat:
        raw_parts = re.split(_PATTERN_ZAND_SPLIT, flat)

        # Re-merge zBETWEEN range parts (same logic as parse_zand_where)
        coalesced = []
        i = 0
        while i < len(raw_parts):
            part = raw_parts[i].strip()
            if (_KEYWORD_ZBETWEEN in part or _KEYWORD_ZNOT_ZBETWEEN in part) and i + 1 < len(raw_parts):
                coalesced.append(part + _KEYWORD_ZAND + raw_parts[i + 1].strip())
                i += 2
            else:
                coalesced.append(part)
                i += 1

        resolved = [_resolve(p) for p in coalesced if p.strip()]
        resolved = [r for r in resolved if r]
        if not resolved:
            return None
        if len(resolved) == 1:
            return resolved[0]
        return {_KEY_AND: resolved}

    if _KEYWORD_ZOR in flat:
        raw_parts = re.split(_PATTERN_ZOR_SPLIT, flat)
        resolved = [_resolve(p) for p in raw_parts if p.strip()]
        resolved = [r for r in resolved if r]
        if not resolved:
            return None
        if len(resolved) == 1:
            return resolved[0]
        return {_KEY_OR: resolved}

    # No outer logical operator — resolve the single (possibly grouped) token
    return _resolve(flat)


def parse_zand_where(where_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a WHERE clause containing zAND conditions (framework-native, case-sensitive).

    Splits on ' zAND ' and merges all conditions into a single dict (AND semantics).

    Examples:
        >>> parse_zand_where("score > 88 zAND age >= 35")
        {"score": {"$gt": 88}, "age": {"$gte": 35}}
    """
    parts = re.split(_PATTERN_ZAND_SPLIT, where_str)

    # Re-merge parts where zBETWEEN (or zNOT zBETWEEN) consumed the first zAND as its range
    # separator.  e.g. "age zBETWEEN 25 zAND 35 zAND score > 90" splits into
    # ["age zBETWEEN 25", "35", "score > 90"] → re-merge first two back.
    # Same applies to "age zNOT zBETWEEN 25 zAND 35 zAND score > 90".
    coalesced = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if (_KEYWORD_ZBETWEEN in part or _KEYWORD_ZNOT_ZBETWEEN in part) and i + 1 < len(parts):
            coalesced.append(part + _KEYWORD_ZAND + parts[i + 1].strip())
            i += 2
        else:
            coalesced.append(part)
            i += 1

    merged: Dict[str, Any] = {}
    for part in coalesced:
        part = part.strip()
        if part:
            parsed = parse_single_where(part)
            if parsed:
                merged.update(parsed)
    return merged if merged else None


def parse_zor_where(where_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a WHERE clause containing zOR conditions (framework-native, case-sensitive).

    Splits on ' zOR ' and wraps results in {"$or": [...]}.

    Examples:
        >>> parse_zor_where("score < 80 zOR age > 40")
        {"$or": [{"score": {"$lt": 80}}, {"age": {"$gt": 40}}]}
    """
    parts = re.split(_PATTERN_ZOR_SPLIT, where_str)
    conditions = []
    for part in parts:
        part = part.strip()
        if part:
            parsed = parse_single_where(part)
            if parsed:
                conditions.append(parsed)

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {_KEY_OR: conditions}


def parse_or_where(where_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a WHERE clause containing OR conditions.
    
    This function splits a WHERE clause by the OR keyword and parses each part
    independently. It produces an output dictionary with a "$or" key containing
    an array of condition dictionaries.
    
    Args:
        where_str: The WHERE clause string containing OR operators.
                  Must be non-empty (caller should check).
    
    Returns:
        Dictionary with "$or" key containing list of parsed conditions.
        Returns None if no valid conditions could be parsed.
        
        If only one condition is valid, returns that condition directly
        (no $or wrapper needed).
    
    OR Logic:
        - Splits by " OR " (case-insensitive, with surrounding spaces)
        - Each part is parsed as a single condition
        - Empty parts are skipped
        - Invalid parts are skipped (no error thrown)
        - Recursion is avoided (only single conditions parsed)
    
    Examples:
        Two conditions:
            >>> parse_or_where("age > 18 OR status = admin")
            {"$or": [{"age": {"$gt": 18}}, {"status": "admin"}]}
        
        Multiple conditions:
            >>> parse_or_where("age < 13 OR age > 65 OR disabled = true")
            {"$or": [
                {"age": {"$lt": 13}},
                {"age": {"$gt": 65}},
                {"disabled": True}
            ]}
        
        Single valid condition (no $or wrapper):
            >>> parse_or_where("name = John OR ")
            {"name": "John"}
    
    Notes:
        - OR detection is case-insensitive (or, OR, Or all work)
        - Leading/trailing whitespace in each part is stripped
        - Nested OR conditions are not supported (flat list only)
        - Avoids infinite recursion by only calling parse_single_where()
    
    See Also:
        - parse_where_clause(): Main entry point
        - parse_single_where(): Parses individual conditions
    """
    # Split by OR (case-insensitive)
    or_parts = re.split(_PATTERN_OR_SPLIT, where_str, flags=re.IGNORECASE)

    or_conditions = []
    for part in or_parts:
        part = part.strip()
        # Only parse non-empty parts that don't contain nested OR
        if part and _KEYWORD_OR not in part.upper():
            # Parse each part (avoiding infinite recursion)
            parsed = parse_single_where(part)
            if parsed:
                or_conditions.append(parsed)

    if not or_conditions:
        return None

    # If only one condition, return it directly (no $or wrapper)
    if len(or_conditions) == 1:
        return or_conditions[0]

    # Multiple conditions - wrap in $or
    return {_KEY_OR: or_conditions}

def parse_single_where(condition: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single WHERE condition without OR operators.
    
    This function handles all non-OR operators: comparison (=, !=, >, <, >=, <=),
    NULL checks (IS NULL, IS NOT NULL), pattern matching (LIKE), and list
    membership (IN).
    
    Args:
        condition: A single WHERE condition string (no OR operators).
                  Must be non-empty (caller should check).
    
    Returns:
        Dictionary representation of the condition, or None if unparseable.
        
        Format varies by operator:
        - Equality: {"field": value}
        - Comparison: {"field": {"$op": value}}
        - IS NULL: {"field": None}
        - IS NOT NULL: {"field": {"$notnull": True}}
        - LIKE: {"field": {"$like": pattern}}
        - IN: {"field": [value1, value2, ...]}
    
    Operator Precedence:
        Operators are checked in this order:
        1. IS NOT NULL (before IS NULL to avoid partial match)
        2. IS NULL
        3. IN
        4. LIKE
        5. Comparison operators (>=, <=, !=, >, <, =)
    
    Examples:
        Equality:
            >>> parse_single_where("name = John")
            {"name": "John"}
        
        Comparison:
            >>> parse_single_where("age >= 18")
            {"age": {"$gte": 18}}
            
            >>> parse_single_where("score < 100")
            {"score": {"$lt": 100}}
        
        NULL checks:
            >>> parse_single_where("email IS NULL")
            {"email": None}
            
            >>> parse_single_where("phone IS NOT NULL")
            {"phone": {"$notnull": True}}
        
        LIKE pattern:
            >>> parse_single_where("name LIKE %Smith%")
            {"name": {"$like": "%Smith%"}}
        
        IN list:
            >>> parse_single_where("status IN active,pending,closed")
            {"status": ["active", "pending", "closed"]}
        
        Type conversion:
            >>> parse_single_where("age = 42")
            {"age": 42}  # int, not string
            
            >>> parse_single_where("active = true")
            {"active": True}  # bool, not string
    
    Notes:
        - All operators are case-insensitive (in, IN, In all work)
        - Field names preserve original casing (except IS NULL/IS NOT NULL)
        - IS NULL/IS NOT NULL lowercase the field name (legacy behavior)
        - Values are type-converted via parse_value()
        - IN operator splits values by comma (no escaping supported)
        - Returns None for unparseable conditions (no exceptions thrown)
    
    See Also:
        - _parse_comparison(): Handles comparison operators
        - parse_value(): Type conversion for values
    """
    condition = condition.strip()
    upper = condition.upper()

    # Handle zKNOWN (framework-native, case-sensitive) — field zKNOWN → IS NOT NULL
    if condition.endswith(_KEYWORD_ZKNOWN):
        field = condition[:-len(_KEYWORD_ZKNOWN)].strip()
        return {field: {_KEY_NOTNULL: True}}

    # Handle zNULL (framework-native, case-sensitive) — field zNULL → IS NULL
    if condition.endswith(_KEYWORD_ZNULL):
        field = condition[:-len(_KEYWORD_ZNULL)].strip()
        return {field: None}

    # Handle legacy IS NOT NULL (check before IS NULL to avoid partial match)
    if _KEYWORD_IS_NOT_NULL in upper:
        field = upper.replace(_KEYWORD_IS_NOT_NULL, "").strip()
        return {field.lower(): {_KEY_NOTNULL: True}}

    # Handle legacy IS NULL
    if _KEYWORD_IS_NULL in upper:
        field = upper.replace(_KEYWORD_IS_NULL, "").strip()
        return {field.lower(): None}

    # Handle zNOT zBETWEEN — checked before positive zBETWEEN
    # field zNOT zBETWEEN min zAND max → {"field": {"$notbetween": [min, max]}}
    if _KEYWORD_ZNOT_ZBETWEEN in condition:
        parts = condition.split(_KEYWORD_ZNOT_ZBETWEEN, 1)
        if len(parts) == 2:
            field = parts[0].strip()
            range_parts = parts[1].split(_KEYWORD_ZAND, 1)
            if len(range_parts) == 2:
                min_val = parse_value(range_parts[0].strip())
                max_val = parse_value(range_parts[1].strip())
                return {field: {_KEY_NOTBETWEEN: [min_val, max_val]}}

    # Handle zBETWEEN (framework-native, case-sensitive) — field zBETWEEN min zAND max
    # parse_zand_where re-merges the split so the full expression arrives here intact
    if _KEYWORD_ZBETWEEN in condition:
        parts = condition.split(_KEYWORD_ZBETWEEN, 1)
        if len(parts) == 2:
            field = parts[0].strip()
            range_parts = parts[1].split(_KEYWORD_ZAND, 1)
            if len(range_parts) == 2:
                min_val = parse_value(range_parts[0].strip())
                max_val = parse_value(range_parts[1].strip())
                return {field: {_KEY_GTE: min_val, _KEY_LTE: max_val}}

    # Handle zNOT zIN — checked before positive zIN
    # field zNOT zIN (val1, val2) → {"field": {"$nin": [val1, val2]}}
    if _KEYWORD_ZNOT_ZIN in condition:
        parts = condition.split(_KEYWORD_ZNOT_ZIN, 1)
        if len(parts) == 2:
            field = parts[0].strip()
            raw_list = parts[1].strip().strip('()')
            values = [parse_value(v.strip()) for v in raw_list.split(_DELIMITER_IN_VALUES)]
            return {field: {_KEY_NIN: values}}

    # Handle zIN (framework-native, case-sensitive) — zIN (val1, val2, val3)
    if _KEYWORD_ZIN in condition:
        parts = condition.split(_KEYWORD_ZIN, 1)
        if len(parts) == 2:
            field = parts[0].strip()
            raw_list = parts[1].strip().strip('()')
            values = [parse_value(v.strip()) for v in raw_list.split(_DELIMITER_IN_VALUES)]
            return {field: values}

    # Handle legacy IN operator (case-insensitive, backward compat)
    if _KEYWORD_IN in upper:
        parts = condition.split(_KEYWORD_IN, 1)
        if len(parts) == 2:
            field = parts[0].strip()
            # Split by comma and parse each value
            values = [
                parse_value(v.strip())
                for v in parts[1].strip().split(_DELIMITER_IN_VALUES)
            ]
            return {field: values}

    # Handle zNOT zLIKE — checked before positive zLIKE
    # field zNOT zLIKE pattern → {"field": {"$notlike": pattern}}
    if _KEYWORD_ZNOT_ZLIKE in condition:
        parts = condition.split(_KEYWORD_ZNOT_ZLIKE, 1)
        if len(parts) == 2:
            return {parts[0].strip(): {_KEY_NOTLIKE: parts[1].strip()}}

    # Handle zLIKE (framework-native, case-sensitive, takes precedence)
    if _KEYWORD_ZLIKE in condition:
        parts = condition.split(_KEYWORD_ZLIKE, 1)
        if len(parts) == 2:
            return {parts[0].strip(): {_KEY_LIKE: parts[1].strip()}}

    # Handle legacy LIKE operator (case-insensitive, backward compat)
    if _KEYWORD_LIKE in upper:
        parts = condition.split(_KEYWORD_LIKE, 1)
        if len(parts) == 2:
            return {parts[0].strip(): {_KEY_LIKE: parts[1].strip()}}

    # Handle zABOVE / zBELOW (string-form aliases for > / <, used in check: expressions)
    if _KEYWORD_ZABOVE in condition:
        parts = condition.split(_KEYWORD_ZABOVE, 1)
        if len(parts) == 2:
            return {parts[0].strip(): {_KEY_GT: parse_value(parts[1].strip())}}

    if _KEYWORD_ZBELOW in condition:
        parts = condition.split(_KEYWORD_ZBELOW, 1)
        if len(parts) == 2:
            return {parts[0].strip(): {_KEY_LT: parse_value(parts[1].strip())}}

    # Parse comparison operators (=, !=, >, <, >=, <=)
    result = _parse_comparison(condition)
    if result:
        return result

    # Could not parse WHERE clause - return None (silent failure)
    return None

def _parse_comparison(condition: str) -> Optional[Dict[str, Any]]:
    """
    Parse comparison operators in a WHERE condition.
    
    This helper function handles all comparison operators: >=, <=, !=, >, <, =.
    Operators are checked in order from longest to shortest to avoid partial matches
    (e.g., checking ">=" before ">" prevents "age >= 18" matching ">").
    
    Args:
        condition: A single condition string containing a comparison operator.
    
    Returns:
        Dictionary with field and comparison, or None if no operator found.
        
        Format:
        - Equality (=): {"field": value}
        - Comparison: {"field": {"$op": value}}
    
    Operator Order:
        Operators are checked in this order (longest first):
        1. >= (greater or equal) → {"$gte": value}
        2. <= (less or equal) → {"$lte": value}
        3. != (not equal) → {"$ne": value}
        4. > (greater than) → {"$gt": value}
        5. < (less than) → {"$lt": value}
        6. = (equality) → value (no operator key)
    
    Examples:
        Greater or equal:
            >>> _parse_comparison("age >= 18")
            {"age": {"$gte": 18}}
        
        Less than:
            >>> _parse_comparison("score < 100")
            {"score": {"$lt": 100}}
        
        Not equal:
            >>> _parse_comparison("status != inactive")
            {"status": {"$ne": "inactive"}}
        
        Equality (no operator key):
            >>> _parse_comparison("name = John")
            {"name": "John"}
    
    Notes:
        - Only the first matching operator is used
        - Values are type-converted via parse_value()
        - Field names and values are stripped of whitespace
        - Returns None if no operator found (not an error)
    
    See Also:
        - parse_single_where(): Calls this for comparison parsing
        - parse_value(): Type conversion for values
        - _COMPARISON_OPERATORS: List of operators checked
        - _OPERATOR_KEY_MAP: Mapping from operators to output keys
    """
    # Check operators in order (longest first to avoid partial matches)
    for operator in _COMPARISON_OPERATORS:
        if operator in condition:
            # Split on first occurrence only
            field, value = condition.split(operator, 1)
            parsed_value = parse_value(value.strip())

            # Get operator key from map (None for equality)
            op_key = _OPERATOR_KEY_MAP[operator]

            # Format: {"field": {"$op": value}} or {"field": value}
            if op_key:
                return {field.strip(): {op_key: parsed_value}}
            else:
                return {field.strip(): parsed_value}

    return None

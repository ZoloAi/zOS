# zOS/core/L2_Core/c_zDisplay/zDisplay_modules/utils/list_helpers.py

"""
List Formatting Utilities
==========================

Helper functions for list prefix generation and number conversion.
Extracted from display_event_data.py to reduce file size and promote reusability.

Functions:
- generate_prefix(): Generate list prefix based on style and number
- number_to_letter(): Convert number to lowercase letter (1→a, 2→b, 27→aa)
- number_to_roman(): Convert number to lowercase roman numeral (1→i, 2→ii, 4→iv)
"""


def generate_prefix(style: str, number: int) -> str:
    """Generate list prefix based on style and number.
    
    Args:
        style: List style (bullet, number, letter, roman, circle, square, dash, none)
        number: Item number (1-indexed)
        
    Returns:
        Formatted prefix (e.g., "1. ", "a. ", "i. ", "• ", "○ ", "▪ ", "- ", or "")
    
    Examples:
        generate_prefix('number', 1)  # Returns "1. "
        generate_prefix('letter', 1)  # Returns "a. "
        generate_prefix('roman', 4)   # Returns "iv. "
        generate_prefix('bullet', 1)  # Returns "- "
        generate_prefix('circle', 1)  # Returns "○ "
        generate_prefix('none', 1)    # Returns ""
    """
    if style == 'number':
        return f"{number}. "
    elif style == 'letter':
        return number_to_letter(number) + ". "
    elif style == 'upper-letter':
        return number_to_letter(number).upper() + ". "
    elif style == 'roman':
        return number_to_roman(number) + ". "
    elif style == 'upper-roman':
        return number_to_roman(number).upper() + ". "
    elif style == 'disc':
        return "● "
    elif style == 'circle':
        return "○ "
    elif style == 'square':
        return "▪ "
    elif style == 'bullet':
        return "- "
    elif style == 'dash':
        return "- "
    else:  # "none" style or unknown
        return ""


def number_to_letter(num: int) -> str:
    """Convert number to lowercase letter (1→a, 2→b, 27→aa).
    
    Args:
        num: Number to convert (1-indexed)
        
    Returns:
        Lowercase letter(s)
    
    Examples:
        number_to_letter(1)   # "a"
        number_to_letter(26)  # "z"
        number_to_letter(27)  # "aa"
        number_to_letter(52)  # "az"
    """
    result = ""
    while num > 0:
        num -= 1
        result = chr(97 + (num % 26)) + result
        num //= 26
    return result


def number_to_roman(num: int) -> str:
    """Convert number to lowercase roman numeral (1→i, 2→ii, 4→iv).
    
    Args:
        num: Number to convert (1-50 supported)
        
    Returns:
        Lowercase roman numeral
    
    Examples:
        number_to_roman(1)   # "i"
        number_to_roman(4)   # "iv"
        number_to_roman(9)   # "ix"
        number_to_roman(27)  # "xxvii"
    """
    values = [50, 40, 10, 9, 5, 4, 1]
    symbols = ['l', 'xl', 'x', 'ix', 'v', 'iv', 'i']
    result = ""
    for i, value in enumerate(values):
        count = num // value
        if count:
            result += symbols[i] * count
            num -= value * count
    return result

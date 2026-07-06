# zOS/core/L2_Handling/c_zDisplay/zDisplay_modules/b_primitives/inputs/__init__.py

"""
Primitive Input Operations
===========================

Terminal syscall wrappers for input operations (input, getpass).
"""

from .input_string import StringInput
from .input_password import PasswordInput

__all__ = [
    'StringInput',
    'PasswordInput',
]

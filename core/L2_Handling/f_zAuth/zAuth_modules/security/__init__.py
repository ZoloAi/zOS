"""
Security Module - Layer 1: Security Primitives

Provides foundational security utilities for password hashing and verification.
No dependencies on other auth modules.
"""

from .password_security import PasswordSecurity

__all__ = ['PasswordSecurity']

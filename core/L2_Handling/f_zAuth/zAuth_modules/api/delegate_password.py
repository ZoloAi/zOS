# zOS/core/L2_Handling/d_zAuth/zAuth_modules/api/delegate_password.py

"""
Password Security Delegate for zAuth Facade.

This module provides password hashing and verification delegate methods,
following zDisplay's delegate pattern for clean facade composition.

Methods:
    - hash_password: Delegate to password_security.hash_password()
    - verify_password: Delegate to password_security.verify_password()

Pattern:
    All methods delegate to self.password_security module instance.
"""

class DelegatePassword:  # pylint: disable=no-member
    """Mixin providing password security delegate methods.
    
    These methods provide thin wrappers around the PasswordSecurity module,
    delegating all password hashing and verification operations.
    
    Note:
        This is a mixin class. The password_security attribute is provided by
        the subclass (zAuth). Pylint warnings about missing member are expected
        and suppressed.
    """

    # Password Security Delegates

    def hash_password(self, plain_password: str) -> str:
        """
        Hash a plaintext password using bcrypt.
        
        Delegates to: password_security.hash_password()
        
        Uses bcrypt with 12 rounds (2^12 = 4096 iterations) and random salting.
        Passwords longer than 72 bytes are truncated with a warning logged.
        
        Args:
            plain_password: Plaintext password string
        
        Returns:
            str: bcrypt hashed password (UTF-8 decoded), e.g., "$2b$12$..."
        
        Raises:
            ValueError: If password is empty or None
        
        Integration:
            - Used by login() to hash passwords before save_session()
            - Used by session_persistence.save_session() for storage
        
        Example:
            hashed = zos.auth.hash_password("my_secure_password")
            # Returns: "$2b$12$abc123..."
        """
        return self.password_security.hash_password(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plaintext password against a bcrypt hash.
        
        Delegates to: password_security.verify_password()
        
        Uses timing-safe comparison to prevent timing attacks.
        
        Args:
            plain_password: Plaintext password to verify
            hashed_password: bcrypt hashed password (from database/storage)
        
        Returns:
            bool: True if password matches, False otherwise
        
        Integration:
            - Used by authentication.login() for password verification
            - Used by session_persistence.load_session() for persistent sessions
        
        Example:
            is_valid = zos.auth.verify_password("password123", "$2b$12$...")
            if is_valid:
                print("Password correct!")
        """
        return self.password_security.verify_password(plain_password, hashed_password)

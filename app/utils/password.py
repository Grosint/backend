"""Password utilities with security best practices."""

import secrets

from passlib.context import CryptContext

# Password hashing context with secure settings
pwd_context = CryptContext(
    schemes=["bcrypt"],  # Use bcrypt (industry standard)
    deprecated="auto",  # Auto-upgrade deprecated schemes
    bcrypt__rounds=12,  # High number of rounds for security (default is 12)
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password string

    Raises:
        ValueError: If password is empty or too weak
    """
    if not password:
        raise ValueError("Password cannot be empty")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored hashed password

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def generate_secure_password(length: int = 16) -> str:
    """
    Generate a secure random password.

    Args:
        length: Password length (minimum 8)

    Returns:
        Secure random password

    Raises:
        ValueError: If length is too short
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters")

    # Generate password with mixed case, numbers, and symbols
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")

    if len(password) > 128:
        issues.append("Password must be less than 128 characters long")

    if not any(c.islower() for c in password):
        issues.append("Password must contain at least one lowercase letter")

    if not any(c.isupper() for c in password):
        issues.append("Password must contain at least one uppercase letter")

    if not any(c.isdigit() for c in password):
        issues.append("Password must contain at least one number")

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        issues.append("Password must contain at least one special character")

    # Check for common patterns
    common_patterns = [
        "123456",
        "password",
        "qwerty",
        "abc123",
        "password123",
        "admin",
        "user",
        "test",
        "welcome",
        "login",
    ]

    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            issues.append(f"Password contains common pattern: {pattern}")
            break

    # Check for repeated characters
    if len(set(password)) < len(password) * 0.6:
        issues.append("Password has too many repeated characters")

    return len(issues) == 0, issues


def is_password_breached(password: str) -> bool:
    """
    Check if password appears in common breach databases.

    Note: This is a simplified implementation. In production, you would
    integrate with services like HaveIBeenPwned API.

    Args:
        password: Password to check

    Returns:
        True if password appears to be breached
    """
    # Common breached passwords (simplified list)
    breached_passwords = {
        "123456",
        "password",
        "123456789",
        "12345678",
        "12345",
        "1234567",
        "1234567890",
        "qwerty",
        "abc123",
        "password123",
        "admin",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
        "master",
        "hello",
        "freedom",
        "whatever",
    }

    return password.lower() in breached_passwords

"""Test user validation scenarios."""

import pytest
from pydantic import ValidationError

from app.models.user import UserBase, UserCreate, UserUpdate
from app.schemas.user import UserCreateRequest, UserUpdateRequest
from app.utils.validators import validate_phone_number, validate_required_phone_number


class TestPhoneValidation:
    """Test phone number validation."""

    def test_validate_required_phone_number_valid_cases(self):
        """Test valid phone numbers for required fields."""
        # Valid phone numbers
        assert validate_required_phone_number("+1234567890") == "+1234567890"
        assert validate_required_phone_number("1234567890") == "+1234567890"
        assert validate_required_phone_number("+91 98765 43210") == "+919876543210"
        assert validate_required_phone_number("+1 (555) 123-4567") == "+15551234567"
        assert validate_required_phone_number("+44 20 7946 0958") == "+442079460958"

    def test_validate_required_phone_number_invalid_cases(self):
        """Test invalid phone numbers for required fields."""
        # None value
        with pytest.raises(ValueError, match="Phone number is required"):
            validate_required_phone_number(None)

        # Empty string
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_required_phone_number("")

        # Too short
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("123")

        # Too long
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("12345678901234567890")

        # Only special characters
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("+()- ")

    def test_validate_phone_number_optional_fields(self):
        """Test phone validation for optional fields."""
        # Valid cases
        assert validate_phone_number("+1234567890") == "+1234567890"
        assert validate_phone_number("1234567890") == "+1234567890"
        assert validate_phone_number(None) is None

        # Invalid cases
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_phone_number("")

    def test_phone_normalization(self):
        """Test phone number normalization."""
        # Test various formats
        test_cases = [
            ("+1234567890", "+1234567890"),  # Already normalized
            ("1234567890", "+1234567890"),  # Add + prefix
            ("+1 234 567 890", "+1234567890"),  # Remove spaces
            ("+1-234-567-890", "+1234567890"),  # Remove dashes
            ("+1 (234) 567-890", "+1234567890"),  # Remove parentheses and dashes
            ("+91 98765 43210", "+919876543210"),  # Indian number
        ]

        for input_phone, expected in test_cases:
            assert validate_required_phone_number(input_phone) == expected


class TestUserCreateRequestValidation:
    """Test UserCreateRequest validation."""

    def test_valid_user_create_request(self):
        """Test valid user creation request."""
        request = UserCreateRequest(
            email="test@example.com",
            phone="+1234567890",
            password="password123",
            verifyByGovId=True,
        )

        assert request.email == "test@example.com"
        assert request.phone == "+1234567890"
        assert request.password == "password123"
        assert request.verifyByGovId is True

    def test_invalid_email_format(self):
        """Test invalid email format."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="invalid-email",
                phone="+1234567890",
                password="password123",
                verifyByGovId=True,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)

    def test_empty_phone_validation(self):
        """Test empty phone validation."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com",
                phone="",
                password="password123",
                verifyByGovId=True,
            )

        errors = exc_info.value.errors()
        assert any(
            "Phone number cannot be empty" in str(error["msg"]) for error in errors
        )

    def test_missing_required_fields(self):
        """Test missing required fields."""
        # Missing phone
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com", password="password123", verifyByGovId=True
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("phone",) for error in errors)

        # Missing email
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                phone="+1234567890", password="password123", verifyByGovId=True
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)

        # Missing password
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com", phone="+1234567890", verifyByGovId=True
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)

        # Missing verifyByGovId
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com", phone="+1234567890", password="password123"
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("verifyByGovId",) for error in errors)

    def test_invalid_verify_by_gov_id_type(self):
        """Test invalid verifyByGovId type."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="password123",
                verifyByGovId="invalid",  # Cannot be coerced to boolean
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("verifyByGovId",) for error in errors)

    def test_password_length_validation(self):
        """Test password length validation."""
        # Short password
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="short",
                verifyByGovId=True,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)

        # Long password
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="test@example.com",
                phone="+1234567890",
                password="a" * 101,  # Too long
                verifyByGovId=True,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("password",) for error in errors)


class TestUserUpdateRequestValidation:
    """Test UserUpdateRequest validation."""

    def test_valid_user_update_request(self):
        """Test valid user update request."""
        request = UserUpdateRequest(
            email="new@example.com",
            phone="+9876543210",
            verifyByGovId=False,
            firstName="John",
            lastName="Doe",
        )

        assert request.email == "new@example.com"
        assert request.phone == "+9876543210"
        assert request.verifyByGovId is False
        assert request.firstName == "John"
        assert request.lastName == "Doe"

    def test_partial_user_update_request(self):
        """Test partial user update request."""
        request = UserUpdateRequest(firstName="Jane")

        assert request.firstName == "Jane"
        assert request.email is None
        assert request.phone is None
        assert request.verifyByGovId is None

    def test_empty_phone_in_update(self):
        """Test empty phone in update request."""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(phone="")

        errors = exc_info.value.errors()
        assert any(
            "Phone number cannot be empty" in str(error["msg"]) for error in errors
        )

    def test_invalid_email_in_update(self):
        """Test invalid email in update request."""
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(email="invalid-email")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("email",) for error in errors)

    def test_field_length_validation(self):
        """Test field length validation in update request."""
        # Long firstName
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(firstName="a" * 101)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("firstName",) for error in errors)

        # Long lastName
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(lastName="a" * 101)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("lastName",) for error in errors)

        # Long pinCode
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(pinCode="a" * 11)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("pinCode",) for error in errors)

        # Long state
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(state="a" * 101)

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("state",) for error in errors)


class TestUserModelValidation:
    """Test User model validation."""

    def test_user_base_validation(self):
        """Test UserBase model validation."""
        user_base = UserBase(
            email="test@example.com", phone="+1234567890", password="hashed_password"
        )

        assert user_base.email == "test@example.com"
        assert user_base.phone == "+1234567890"
        assert user_base.password == "hashed_password"
        assert user_base.isActive is True  # Default value
        assert user_base.isVerified is False  # Default value

    def test_user_create_validation(self):
        """Test UserCreate model validation."""
        user_create = UserCreate(
            email="test@example.com",
            phone="+1234567890",
            verifyByGovId=True,
            password="password123",
        )

        assert user_create.email == "test@example.com"
        assert user_create.phone == "+1234567890"
        assert user_create.verifyByGovId is True
        assert user_create.password == "password123"

    def test_user_update_validation(self):
        """Test UserUpdate model validation."""
        user_update = UserUpdate(firstName="John", lastName="Doe", phone="+9876543210")

        assert user_update.firstName == "John"
        assert user_update.lastName == "Doe"
        assert user_update.phone == "+9876543210"
        assert user_update.email is None

    def test_user_model_phone_validation(self):
        """Test phone validation in User models."""
        # Valid phone
        user = UserBase(
            email="test@example.com", phone="+1234567890", password="hashed_password"
        )
        assert user.phone == "+1234567890"

        # Invalid phone
        with pytest.raises(ValidationError) as exc_info:
            UserBase(email="test@example.com", phone="", password="hashed_password")

        errors = exc_info.value.errors()
        assert any(
            "Phone number cannot be empty" in str(error["msg"]) for error in errors
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_phone_number_boundary_lengths(self):
        """Test phone number boundary lengths."""
        # Minimum valid length (7 digits)
        assert validate_required_phone_number("1234567") == "+1234567"

        # Maximum valid length (15 digits)
        assert validate_required_phone_number("123456789012345") == "+123456789012345"

        # Just below minimum (6 digits)
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("123456")

        # Just above maximum (16 digits)
        with pytest.raises(
            ValueError, match="Phone number must be between 7 and 15 digits"
        ):
            validate_required_phone_number("1234567890123456")

    def test_phone_number_with_plus_prefix(self):
        """Test phone numbers with plus prefix."""
        # With plus prefix
        assert validate_required_phone_number("+1234567890") == "+1234567890"

        # Without plus prefix
        assert validate_required_phone_number("1234567890") == "+1234567890"

        # Multiple plus signs (should be handled gracefully)
        with pytest.raises(
            ValueError, match="Phone number cannot contain multiple plus signs"
        ):
            validate_required_phone_number("++1234567890")

    def test_phone_number_with_whitespace(self):
        """Test phone numbers with various whitespace characters."""
        test_cases = [
            ("+1 234 567 890", "+1234567890"),
            ("+1\t234\t567\t890", "+1234567890"),
            ("+1\n234\n567\n890", "+1234567890"),
            ("+1\r234\r567\r890", "+1234567890"),
        ]

        for input_phone, expected in test_cases:
            assert validate_required_phone_number(input_phone) == expected

    def test_phone_number_with_special_characters(self):
        """Test phone numbers with special characters."""
        test_cases = [
            ("+1-234-567-890", "+1234567890"),
            ("+1(234)567-890", "+1234567890"),
            ("+1 (234) 567-890", "+1234567890"),
            ("+1.234.567.890", "+1234567890"),
        ]

        for input_phone, expected in test_cases:
            assert validate_required_phone_number(input_phone) == expected

    def test_empty_string_vs_none(self):
        """Test distinction between empty string and None."""
        # None should be allowed for optional fields
        assert validate_phone_number(None) is None

        # Empty string should not be allowed for optional fields
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_phone_number("")

        # None should not be allowed for required fields
        with pytest.raises(ValueError, match="Phone number is required"):
            validate_required_phone_number(None)

        # Empty string should not be allowed for required fields
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            validate_required_phone_number("")

# Email Service Usage Guide

This guide explains how to use the email service in the GROSINT backend application.

## Overview

The email service is a template-based, configurable email sending system built on Azure Communication Services. It supports multiple email types and is designed to be independent and reusable.

## Quick Start

### Basic Usage

```python
from app.services.email_service import email_service

# Send OTP email
await email_service.send_otp_email(
    email="user@example.com",
    otp="123456",
    expires_in_minutes=10
)

# Send registration success email
await email_service.send_registration_success_email(
    email="user@example.com",
    first_name="John",
    last_name="Doe"
)

# Send welcome email
await email_service.send_welcome_email(
    email="user@example.com",
    first_name="John",
    last_name="Doe"
)

# Send account verified email
await email_service.send_account_verified_email(
    email="user@example.com",
    first_name="John"
)

# Send password reset email
await email_service.send_password_reset_email(
    email="user@example.com",
    reset_token="abc123xyz",
    reset_url="https://app.com/reset?token=abc123xyz",
    expires_in_minutes=30
)
```

## Available Email Templates

### 1. OTP Email (`otp.html`)
**Purpose**: Send one-time password for email verification

**Usage**:
```python
await email_service.send_otp_email(
    email="user@example.com",
    otp="123456",
    expires_in_minutes=10
)
```

**Template Variables**:
- `{{otp}}` - The OTP code
- `{{expires_in_minutes}}` - Expiration time in minutes
- `{{app_name}}` - Application name (from settings)

### 2. Registration Success (`registration_success.html`)
**Purpose**: Confirm successful user registration

**Usage**:
```python
await email_service.send_registration_success_email(
    email="user@example.com",
    first_name="John",
    last_name="Doe"
)
```

**Template Variables**:
- `{{first_name}}` - User's first name
- `{{full_name}}` - User's full name
- `{{app_name}}` - Application name

### 3. Welcome Email (`welcome.html`)
**Purpose**: Welcome new users to the platform

**Usage**:
```python
await email_service.send_welcome_email(
    email="user@example.com",
    first_name="John",
    last_name="Doe"
)
```

**Template Variables**:
- `{{first_name}}` - User's first name
- `{{full_name}}` - User's full name
- `{{app_name}}` - Application name

### 4. Account Verified (`account_verified.html`)
**Purpose**: Confirm successful account verification

**Usage**:
```python
await email_service.send_account_verified_email(
    email="user@example.com",
    first_name="John"
)
```

**Template Variables**:
- `{{first_name}}` - User's first name
- `{{app_name}}` - Application name

### 5. Password Reset (`password_reset.html`)
**Purpose**: Send password reset link

**Usage**:
```python
await email_service.send_password_reset_email(
    email="user@example.com",
    reset_token="abc123xyz",
    reset_url="https://app.com/reset?token=abc123xyz",
    expires_in_minutes=30
)
```

**Template Variables**:
- `{{reset_url}}` - Password reset URL
- `{{expires_in_minutes}}` - Token expiration time
- `{{app_name}}` - Application name

## Advanced Usage

### Custom Template Email

You can send emails using any template with custom variables:

```python
from app.services.email_service import EmailTemplate, email_service

await email_service.send_template_email(
    template=EmailTemplate.OTP,
    to="user@example.com",
    subject="Your Custom Subject",
    otp="123456",
    expires_in_minutes=10,
    custom_var="custom_value"
)
```

### Direct Email Sending

For complete control, send emails directly with HTML content:

```python
await email_service.send_email(
    to="user@example.com",
    subject="Custom Email",
    html_content="<h1>Hello</h1><p>This is a custom email.</p>",
    plain_text_content="Hello\n\nThis is a custom email."
)
```

### Multiple Recipients

Send to multiple recipients:

```python
await email_service.send_otp_email(
    email=["user1@example.com", "user2@example.com"],
    otp="123456"
)
```

## Integration Points

### Current Integrations

1. **User Registration** (`app/api/endpoints/user.py`)
   - Sends OTP email after user creation

2. **OTP Sending** (`app/api/endpoints/auth.py`)
   - `/api/auth/send-otp` endpoint
   - `/api/auth/resend-otp` endpoint

3. **OTP Verification** (`app/api/endpoints/auth.py`)
   - Sends account verified email after successful verification

### Adding New Email Types

1. **Create Template**:
   - Add new HTML template in `app/templates/emails/`
   - Use `{{variable_name}}` for dynamic content

2. **Add to EmailTemplate Enum**:
   ```python
   class EmailTemplate(str, Enum):
       # ... existing templates
       NEW_TYPE = "new_type"
   ```

3. **Add Method to EmailService**:
   ```python
   async def send_new_type_email(self, email: str, **kwargs) -> bool:
       return await self.send_template_email(
           template=EmailTemplate.NEW_TYPE,
           to=email,
           **kwargs
       )
   ```

## Error Handling

The email service handles errors gracefully:

```python
# Returns False on failure, True on success
result = await email_service.send_otp_email(email="user@example.com", otp="123456")

if not result:
    # Handle failure (log, retry, etc.)
    logger.error("Failed to send email")
```

## Configuration

Required environment variables (see `AZURE_EMAIL_SETUP.md`):

```bash
AZURE_EMAIL_ENDPOINT=https://your-resource.communication.azure.com
AZURE_EMAIL_ACCESS_KEY=your-access-key-here
AZURE_EMAIL_SENDER_ADDRESS=donotreply@your-domain.com
FRONTEND_URL=https://your-app.com
```

**Note**: Both `AZURE_EMAIL_ENDPOINT` and `AZURE_EMAIL_ACCESS_KEY` are required. This approach provides better security and flexibility in configuration management.

## Testing

### Test Email Sending

```python
import asyncio
from app.services.email_service import email_service

async def test():
    result = await email_service.send_otp_email(
        email="test@example.com",
        otp="123456"
    )
    print(f"Sent: {result}")

asyncio.run(test())
```

### Mock for Testing

```python
from unittest.mock import AsyncMock, patch

@patch('app.services.email_service.email_service.send_otp_email')
async def test_user_registration(mock_send):
    mock_send.return_value = True
    # Your test code
```

## Best Practices

1. **Always handle failures**: Check return value and log errors
2. **Use appropriate templates**: Don't send OTP emails for welcome messages
3. **Don't block on email**: Email sending is async, but failures shouldn't break user flow
4. **Log email events**: Track sent emails for debugging
5. **Respect rate limits**: Azure has rate limits (1000 emails/minute by default)
6. **Test templates**: Preview templates before deploying

## Template Customization

Templates are located in `app/templates/emails/`. They use:
- Modern HTML/CSS with inline styles (for email client compatibility)
- Responsive design
- Gradient backgrounds
- Professional styling

To customize:
1. Edit the HTML file
2. Use `{{variable_name}}` for dynamic content
3. Test with real email clients
4. Ensure mobile responsiveness

## Troubleshooting

### Email Not Sending
1. Check Azure connection string in `.env`
2. Verify sender address is configured
3. Check application logs for errors
4. Verify Azure service status

### Template Not Found
1. Ensure template file exists in `app/templates/emails/`
2. Check template name matches enum value
3. Verify file has `.html` extension

### Variables Not Replacing
1. Ensure variable names match template placeholders
2. Use `{{variable_name}}` format (double curly braces)
3. Check variable values are not None

## Support

For Azure setup, see `AZURE_EMAIL_SETUP.md`.
For issues, check application logs and Azure Portal email logs.

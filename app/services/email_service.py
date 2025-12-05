"""Email service for sending transactional emails using Azure Communication Services."""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from azure.communication.email import EmailClient
from azure.core.exceptions import AzureError

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailTemplate(str, Enum):
    """Available email templates."""

    OTP = "otp"
    REGISTRATION_SUCCESS = "registration_success"
    PASSWORD_RESET = (
        "password_reset"  # nosec B105 - Template identifier, not a password
    )
    WELCOME = "welcome"
    ACCOUNT_VERIFIED = "account_verified"


class EmailService:
    """Service for sending emails via Azure Communication Services."""

    def __init__(self):
        """Initialize email service with Azure Communication Services."""
        self.sender_address = settings.AZURE_EMAIL_SENDER_ADDRESS
        self.template_dir = Path(__file__).parent.parent / "templates" / "emails"

        # Build connection string from separate endpoint and access key
        self.connection_string = self._build_connection_string()

        if not self.connection_string:
            logger.warning(
                "Azure email configuration incomplete. Email sending will be disabled. "
                "Please set both AZURE_EMAIL_ENDPOINT and AZURE_EMAIL_ACCESS_KEY."
            )
            self.client = None
        elif not self.sender_address:
            logger.warning(
                "Azure email sender address not configured. Email sending will be disabled. "
                "Please set AZURE_EMAIL_SENDER_ADDRESS."
            )
            self.client = None
        else:
            try:
                self.client = EmailClient.from_connection_string(self.connection_string)
                logger.info(
                    f"Azure Email client initialized successfully. "
                    f"Sender address: {self.sender_address}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Azure Email client: {e}")
                self.client = None

    def _build_connection_string(self) -> str:
        """
        Build connection string from separate endpoint and access key.

        Returns:
            Connection string or empty string if not configured
        """
        endpoint = (
            settings.AZURE_EMAIL_ENDPOINT.strip()
            if settings.AZURE_EMAIL_ENDPOINT
            else ""
        )
        access_key = (
            settings.AZURE_EMAIL_ACCESS_KEY.strip()
            if settings.AZURE_EMAIL_ACCESS_KEY
            else ""
        )

        if endpoint and access_key:
            # Ensure endpoint doesn't have trailing slash
            endpoint = endpoint.rstrip("/")
            return f"endpoint={endpoint};accesskey={access_key}"

        # If only one is provided, log warning
        if endpoint or access_key:
            logger.warning(
                "Azure email configuration incomplete: both AZURE_EMAIL_ENDPOINT and "
                "AZURE_EMAIL_ACCESS_KEY must be provided."
            )

        return ""

    def _load_template(self, template_name: str) -> str:
        """
        Load email template from file.

        Args:
            template_name: Name of the template file (without .html extension)

        Returns:
            Template content as string

        Raises:
            FileNotFoundError: If template file doesn't exist
        """
        template_path = self.template_dir / f"{template_name}.html"

        if not template_path.exists():
            raise FileNotFoundError(
                f"Email template not found: {template_path}. "
                f"Available templates: {[f.stem for f in self.template_dir.glob('*.html')]}"
            )

        with open(template_path, encoding="utf-8") as f:
            return f.read()

    def _render_template(self, template_content: str, **kwargs: Any) -> str:
        """
        Render email template with provided variables.

        Args:
            template_content: Template content as string
            **kwargs: Variables to substitute in template

        Returns:
            Rendered template content
        """
        rendered = template_content
        for key, value in kwargs.items():
            placeholder = f"{{{{{key}}}}}"
            rendered = rendered.replace(placeholder, str(value))
        return rendered

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        html_content: str,
        plain_text_content: str | None = None,
    ) -> bool:
        """
        Send email using Azure Communication Services.

        Args:
            to: Recipient email address(es)
            subject: Email subject
            html_content: HTML email content
            plain_text_content: Plain text email content (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.client:
            logger.warning(
                "Email client not initialized. Email not sent. "
                "Check Azure email configuration."
            )
            return False

        try:
            # Convert single email to list
            recipients = [to] if isinstance(to, str) else to

            # Create message
            message = {
                "senderAddress": self.sender_address,
                "recipients": {
                    "to": [{"address": email} for email in recipients],
                },
                "content": {
                    "subject": subject,
                    "html": html_content,
                },
            }

            # Add plain text content if provided
            if plain_text_content:
                message["content"]["plainText"] = plain_text_content

            # Send email
            poller = self.client.begin_send(message)
            result = poller.result()

            logger.info(
                f"Email sent successfully to {', '.join(recipients)}. "
                f"Message ID: {result.get('id', 'N/A')}"
            )
            return True

        except AzureError as e:
            error_code = getattr(e, "error_code", None) or getattr(e, "code", None)

            # Provide helpful error messages for common issues
            if error_code == "DomainNotLinked":
                logger.error(
                    f"Azure email service error: Domain not linked. "
                    f"The sender address '{self.sender_address}' domain has not been linked/verified in Azure. "
                    f"Please link the domain in Azure Portal: Communication Services → Email → Domains. "
                    f"See AZURE_EMAIL_SETUP.md for detailed instructions."
                )
            else:
                logger.error(f"Azure email service error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_template_email(
        self,
        template: EmailTemplate,
        to: str | list[str],
        subject: str | None = None,
        **template_vars: Any,
    ) -> bool:
        """
        Send email using a template.

        Args:
            template: Email template to use
            to: Recipient email address(es)
            subject: Email subject (if None, uses template default)
            **template_vars: Variables to pass to template

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Load template
            template_content = self._load_template(template.value)

            # Render template with variables
            html_content = self._render_template(template_content, **template_vars)

            # Generate plain text version (simple HTML strip)
            plain_text_content = self._generate_plain_text(html_content)

            # Use provided subject or default
            email_subject = subject or self._get_default_subject(template)

            # Send email
            return await self.send_email(
                to=to,
                subject=email_subject,
                html_content=html_content,
                plain_text_content=plain_text_content,
            )

        except FileNotFoundError as e:
            logger.error(f"Template not found: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send template email: {e}")
            return False

    async def send_otp_email(
        self, email: str, otp: str, expires_in_minutes: int = 10
    ) -> bool:
        """
        Send OTP email to user.

        Args:
            email: Recipient email address
            otp: OTP code
            expires_in_minutes: OTP expiration time in minutes

        Returns:
            True if email sent successfully, False otherwise
        """
        return await self.send_template_email(
            template=EmailTemplate.OTP,
            to=email,
            otp=otp,
            expires_in_minutes=expires_in_minutes,
            app_name=settings.PROJECT_NAME,
        )

    async def send_registration_success_email(
        self,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> bool:
        """
        Send registration success email.

        Args:
            email: Recipient email address
            first_name: User's first name (optional)
            last_name: User's last name (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        # Build full_name by joining only non-empty name parts
        name_parts = []
        if first_name and first_name.strip():
            name_parts.append(first_name.strip())
        if last_name and last_name.strip():
            name_parts.append(last_name.strip())
        full_name = " ".join(name_parts) if name_parts else "User"

        return await self.send_template_email(
            template=EmailTemplate.REGISTRATION_SUCCESS,
            to=email,
            first_name=(
                first_name.strip() if first_name and first_name.strip() else "User"
            ),
            full_name=full_name,
            app_name=settings.PROJECT_NAME,
        )

    async def send_welcome_email(
        self,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> bool:
        """
        Send welcome email to new user.

        Args:
            email: Recipient email address
            first_name: User's first name (optional)
            last_name: User's last name (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        # Build full_name by joining only non-empty name parts
        name_parts = []
        if first_name and first_name.strip():
            name_parts.append(first_name.strip())
        if last_name and last_name.strip():
            name_parts.append(last_name.strip())
        full_name = " ".join(name_parts) if name_parts else "User"

        return await self.send_template_email(
            template=EmailTemplate.WELCOME,
            to=email,
            first_name=(
                first_name.strip() if first_name and first_name.strip() else "User"
            ),
            full_name=full_name,
            app_name=settings.PROJECT_NAME,
        )

    async def send_account_verified_email(
        self,
        email: str,
        first_name: str | None = None,
    ) -> bool:
        """
        Send account verification success email.

        Args:
            email: Recipient email address
            first_name: User's first name (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        return await self.send_template_email(
            template=EmailTemplate.ACCOUNT_VERIFIED,
            to=email,
            first_name=first_name or "User",
            app_name=settings.PROJECT_NAME,
        )

    async def send_password_reset_email(
        self,
        email: str,
        reset_token: str,
        reset_url: str | None = None,
        expires_in_minutes: int = 30,
    ) -> bool:
        """
        Send password reset email.

        Args:
            email: Recipient email address
            reset_token: Password reset token
            reset_url: Full reset URL (optional, will be constructed if not provided)
            expires_in_minutes: Token expiration time in minutes

        Returns:
            True if email sent successfully, False otherwise
        """
        if not reset_url:
            # Construct reset URL (adjust based on your frontend URL)
            # URL-encode the token to handle special characters safely
            frontend_url = getattr(settings, "FRONTEND_URL", "https://your-app.com")
            encoded_token = quote_plus(reset_token)
            reset_url = f"{frontend_url}/reset-password?token={encoded_token}"

        return await self.send_template_email(
            template=EmailTemplate.PASSWORD_RESET,
            to=email,
            reset_url=reset_url,
            expires_in_minutes=expires_in_minutes,
            app_name=settings.PROJECT_NAME,
        )

    def _generate_plain_text(self, html_content: str) -> str:
        """
        Generate plain text version from HTML content.

        Args:
            html_content: HTML email content

        Returns:
            Plain text version
        """
        # Simple HTML to text conversion
        import re

        # Remove script and style elements
        text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)

        # Replace common HTML elements
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"</p>", "\n\n", text)
        text = re.sub(r"</div>", "\n", text)
        text = re.sub(r"</h[1-6]>", "\n\n", text)

        # Remove all HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        import html

        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = text.strip()

        return text

    def _get_default_subject(self, template: EmailTemplate) -> str:
        """
        Get default subject for template.

        Args:
            template: Email template

        Returns:
            Default subject line
        """
        subjects = {
            EmailTemplate.OTP: f"Your {settings.PROJECT_NAME} Verification Code",
            EmailTemplate.REGISTRATION_SUCCESS: f"Welcome to {settings.PROJECT_NAME}!",
            EmailTemplate.WELCOME: f"Welcome to {settings.PROJECT_NAME}!",
            EmailTemplate.ACCOUNT_VERIFIED: f"Account Verified - {settings.PROJECT_NAME}",
            EmailTemplate.PASSWORD_RESET: f"Reset Your {settings.PROJECT_NAME} Password",
        }
        return subjects.get(template, f"Message from {settings.PROJECT_NAME}")


# Create singleton instance
email_service = EmailService()

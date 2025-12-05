# Azure Communication Services Email Setup Guide

This guide will walk you through setting up Azure Communication Services Email for sending transactional emails (OTP, registration confirmations, etc.) in the GROSINT backend.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Azure Setup Steps](#azure-setup-steps)
3. [Configuration](#configuration)
4. [Testing](#testing)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:

- An active Azure account with a subscription
- Azure CLI installed (optional, but recommended)
- Access to Azure Portal (<https://portal.azure.com>)

---

## Azure Setup Steps

### Step 1: Create Azure Communication Services Resource

1. **Log in to Azure Portal**
   - Navigate to <https://portal.azure.com>
   - Sign in with your Azure account

2. **Create a new Communication Services resource**
   - Click "Create a resource" or search for "Communication Services"
   - Select "Communication Services" from the results
   - Click "Create"

3. **Configure the resource**
   - **Subscription**: Select your Azure subscription
   - **Resource Group**: Create a new one or select existing
   - **Resource Name**: Choose a unique name (e.g., `grosint-email-service`)
   - **Region**: Select a region close to your users (e.g., `East US`, `West Europe`)
   - **Data Location**: Select the same or nearest region
   - Click "Review + create", then "Create"

4. **Wait for deployment**
   - Wait 2-3 minutes for the resource to be created
   - Click "Go to resource" when deployment completes

### Step 2: Get Connection String

1. **Navigate to Keys**
   - In your Communication Services resource, go to "Settings" → "Keys"
   - You'll see two connection strings: `Primary Connection String` and `Secondary Connection String`

2. **Copy the Primary Connection String**
   - Click the copy icon next to "Primary Connection String"
   - Format: `endpoint=https://<resource-name>.communication.azure.com/;accesskey=<access-key>`
   - **Save this securely** - you'll need it for configuration

### Step 3: Create Email Communication Service and Link Domain

**⚠️ IMPORTANT: This step is critical. The domain MUST be linked before you can send emails.**

1. **Navigate to Email Communication Services**
   - In your Communication Services resource, look for "Email" in the left menu
   - Click on "Email Communication Services" or "Domains"

2. **Add and Link a Domain**
   - Click "Add domain" or "Provision domain"
   - You have two options:
     - **Option A: Use Azure Managed Domain (Recommended for testing/quick start)**
       - Click "Add domain" → Select "Azure Managed Domain"
       - Azure will automatically provision a managed domain
       - The domain will be: `<your-resource-name>.azurecomm.net`
       - **Status must show "Linked" or "Verified"** before you can send emails
       - The sender address will be: `donotreply@<your-resource-name>.azurecomm.net`
       - This is usually ready within a few minutes
     - **Option B: Use Your Own Domain (Recommended for production)**
       - Click "Add domain" → Select "Custom Domain"
       - Enter your domain (e.g., `yourdomain.com`)
       - Follow DNS verification steps

3. **For Azure Managed Domain (Quick Start)**
   - Azure will automatically create and link a managed domain
   - **Wait for the domain status to show "Linked"** (usually 2-5 minutes)
   - Check the status in: Communication Services → Email → Domains
   - The sender address will be: `donotreply@<your-resource-name>.azurecomm.net`
   - **You can only send emails once the domain shows "Linked" status**

4. **For Custom Domain (Production)**
   - After adding your domain, Azure will provide DNS records to add
   - Add these records to your domain's DNS settings:
     - **MX Record**: For email routing
     - **TXT Record**: For domain verification
     - **CNAME Records**: For email authentication (SPF, DKIM, DMARC)
   - Wait for verification (can take up to 48 hours)
   - **Status must show "Linked" or "Verified"** before you can send emails
   - Once verified, you can use emails like `noreply@yourdomain.com`

5. **Verify Domain is Linked**
   - Go to: Communication Services → Email → Domains
   - Check that your domain shows status as **"Linked"** or **"Verified"**
   - If status is "Pending" or "Not Linked", wait a few minutes and refresh
   - **You cannot send emails until the domain is linked**

### Step 4: Verify Domain (For Custom Domains)

1. **Check Domain Status**
   - In the "Domains" section, check your domain status
   - Status should be "Verified" before you can send emails

2. **DNS Records to Add** (Example for custom domain)

   ```
   Type: MX
   Name: @
   Value: <provided-by-azure>
   Priority: 10

   Type: TXT
   Name: @
   Value: <verification-string>

   Type: CNAME
   Name: <provided-name>
   Value: <provided-value>
   ```

### Step 5: Get Sender Email Address

**⚠️ IMPORTANT: The domain must be "Linked" before you can use the sender address.**

1. **For Azure Managed Domain**
   - First, ensure the domain shows "Linked" status in Azure Portal
   - Format: `donotreply@<your-resource-name>.azurecomm.net`
   - Example: `donotreply@grosint-email-service.azurecomm.net`
   - **Note**: The domain part (`<your-resource-name>.azurecomm.net`) must match your resource name

2. **For Custom Domain**
   - First, ensure the domain shows "Verified" status in Azure Portal
   - Use any email address from your verified domain
   - Example: `noreply@yourdomain.com` or `support@yourdomain.com`
   - The domain part must exactly match your verified domain

3. **Verify Domain Status Before Using**
   - Go to: Communication Services → Email → Domains
   - Confirm status is "Linked" (Azure Managed) or "Verified" (Custom Domain)
   - Only then configure `AZURE_EMAIL_SENDER_ADDRESS` in your `.env` file

---

## Configuration

### Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Azure Communication Services Email Configuration
AZURE_EMAIL_ENDPOINT=https://<your-resource>.communication.azure.com
AZURE_EMAIL_ACCESS_KEY=<your-access-key>
AZURE_EMAIL_SENDER_ADDRESS=donotreply@<your-resource>.azurecomm.net

# Frontend URL (for password reset links, etc.)
FRONTEND_URL=https://your-app.com
```

### Example .env Configuration

```bash
# Azure Email Service
AZURE_EMAIL_ENDPOINT=https://grosint-email-service.communication.azure.com
AZURE_EMAIL_ACCESS_KEY=abc123xyz789...
AZURE_EMAIL_SENDER_ADDRESS=donotreply@grosint-email-service.azurecomm.net
FRONTEND_URL=https://app.grosint.com
```

### Important Notes

1. **Never commit `.env` file** - Keep connection strings secure
2. **Use different sender addresses** for different environments (dev, staging, prod)
3. **Connection string format** must be exact: `endpoint=...;accesskey=...`

---

## Testing

### Test Email Sending

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables** (as shown above)

3. **Test via API**
   - Use the `/api/auth/send-otp` endpoint
   - Or create a test script:

   ```python
   import asyncio
   from app.services.email_service import email_service

   async def test_email():
       result = await email_service.send_otp_email(
           email="your-email@example.com",
           otp="123456",
           expires_in_minutes=10
       )
       print(f"Email sent: {result}")

   asyncio.run(test_email())
   ```

### Verify Email Delivery

1. Check your inbox (and spam folder)
2. Check Azure Portal → Communication Services → Email → "Email logs" for delivery status
3. Check application logs for any errors

---

## Pricing

Azure Communication Services Email pricing (as of 2025):

- **Free Tier**: 5,000 emails/month (first 30 days)
- **Pay-as-you-go**:
  - First 50,000 emails/month: $0.0001 per email ($0.10 per 1,000)
  - Next 950,000 emails/month: $0.00008 per email ($0.08 per 1,000)
  - Over 1,000,000 emails/month: Custom pricing

**Example Monthly Cost:**

- 10,000 emails: ~$1.00
- 100,000 emails: ~$10.00
- 1,000,000 emails: ~$90.00

---

## Troubleshooting

### Common Issues

#### 1. "Configuration incomplete"

- **Solution**:
  - Ensure both `AZURE_EMAIL_ENDPOINT` and `AZURE_EMAIL_ACCESS_KEY` are set in your `.env` file
  - Verify endpoint format: `https://<your-resource>.communication.azure.com` (without trailing slash)
  - Check for extra spaces in environment variables
  - Ensure access key is copied correctly from Azure Portal

#### 2. "DomainNotLinked" or "Sender address not verified"

- **Error Message**: `DomainNotLinked: The specified sender domain has not been linked.`
- **Solution**:
  1. Go to Azure Portal → Your Communication Services resource → Email → Domains
  2. Check the status of your domain:
     - **If status is "Pending"**: Wait 2-5 minutes and refresh the page
     - **If status is "Not Linked"**: Click on the domain and ensure it's properly provisioned
     - **Status must be "Linked" or "Verified"** to send emails
  3. For Azure Managed Domain:
     - Wait a few minutes after creation for automatic linking
     - Refresh the domains page to see updated status
  4. For Custom Domain:
     - Ensure all DNS records are added correctly
     - Wait for DNS propagation (can take up to 48 hours)
     - Verify domain shows "Verified" status
  5. **Verify sender address matches linked domain**:
     - If using Azure Managed Domain: Use `donotreply@<your-resource>.azurecomm.net`
     - If using Custom Domain: Use an email from your verified domain
  6. After linking, restart your application to ensure it picks up the changes

#### 3. "Email not received"

- **Check spam folder**
- Verify sender address is correct
- Check Azure Portal → Email logs for delivery status
- Ensure recipient email is valid

#### 4. "Authentication failed"

- **Solution**: Regenerate access keys in Azure Portal
- Update connection string in `.env` file
- Restart your application

#### 5. "Rate limit exceeded"

- **Solution**: Azure has rate limits per resource
- Default: 1,000 emails per minute per resource
- For higher limits, contact Azure support

### Debugging

1. **Enable detailed logging**

   ```python
   import logging
   logging.getLogger('azure').setLevel(logging.DEBUG)
   ```

2. **Check Azure Portal logs**
   - Communication Services → Monitoring → Logs
   - Email → Email logs

3. **Test connection**

   ```python
   from azure.communication.email import EmailClient
   client = EmailClient.from_connection_string("your-connection-string")
   # If no error, connection is valid
   ```

---

## Security Best Practices

1. **Never expose connection strings** in code or version control
2. **Use Azure Key Vault** for production (recommended)
3. **Rotate access keys** regularly
4. **Use different resources** for dev/staging/production
5. **Monitor email usage** in Azure Portal
6. **Set up alerts** for unusual activity

---

## Additional Resources

- [Azure Communication Services Documentation](https://learn.microsoft.com/azure/communication-services/)
- [Email Service Quickstart](https://learn.microsoft.com/azure/communication-services/quickstarts/email/send-email)
- [Pricing Details](https://azure.microsoft.com/pricing/details/communication-services/)
- [Azure Portal](https://portal.azure.com)

---

## Quick Reference

### Required Azure Resources

1. ✅ Communication Services resource
2. ✅ Email Communication Service (domain)
3. ✅ Connection string (from Keys section)
4. ✅ Verified sender email address

### Required Environment Variables

```bash
AZURE_EMAIL_ENDPOINT=https://<your-resource>.communication.azure.com
AZURE_EMAIL_ACCESS_KEY=<your-access-key>
AZURE_EMAIL_SENDER_ADDRESS=<sender-email>
FRONTEND_URL=<your-frontend-url>
```

### Email Templates Available

- `otp.html` - OTP verification code
- `registration_success.html` - Registration confirmation
- `welcome.html` - Welcome email
- `account_verified.html` - Account verification success
- `password_reset.html` - Password reset link

---

## Support

If you encounter issues:

1. Check Azure Portal for service status
2. Review application logs
3. Verify configuration in `.env` file
4. Test with Azure Managed Domain first
5. Contact Azure support if needed

---

**Last Updated**: December 2025

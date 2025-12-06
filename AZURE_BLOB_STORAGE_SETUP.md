# Azure Blob Storage Setup Guide

This guide explains how to set up Azure Blob Storage for the file upload system.

## Overview

The upload system supports two methods:

1. **Direct Upload**: Files are uploaded through the backend server
2. **Pre-signed URL Upload**: Clients upload directly to Azure Blob Storage using pre-signed URLs

## Azure Setup Steps

### 1. Create Azure Storage Account

1. Log in to the [Azure Portal](https://portal.azure.com)
2. Navigate to **Storage accounts** → **Create**
3. Fill in the required fields:
   - **Subscription**: Select your subscription
   - **Resource group**: Create new or use existing
   - **Storage account name**: Choose a unique name (e.g., `grosintstorage`)
   - **Region**: Select your preferred region
   - **Performance**: Standard (recommended) or Premium
   - **Redundancy**: Choose based on your needs (LRS, GRS, ZRS, etc.)
4. Click **Review + create**, then **Create**

### 2. Create Container

1. Once the storage account is created, navigate to it
2. Go to **Containers** in the left menu
3. Click **+ Container**
4. Configure:
   - **Name**: `uploads` (or your preferred name)
   - **Public access level**:
     - **Private (no anonymous access)**: Recommended for security
     - **Blob (anonymous read access for blobs only)**: If you need public access
     - **Container (anonymous read access for container and blobs)**: Not recommended
5. Click **Create**

### 3. Get Access Credentials

You have two options for authentication:

#### Option A: Connection String (Recommended for simplicity)

1. In your storage account, go to **Access keys** in the left menu
2. Click **Show** next to **key1** or **key2**
3. Copy the **Connection string** (starts with `DefaultEndpointsProtocol=https;...`)

#### Option B: Account Name and Key (More granular control)

1. In your storage account, go to **Access keys** in the left menu
2. Copy the **Storage account name**
3. Click **Show** next to **key1** or **key2**
4. Copy the **Key** value

### 4. Configure Environment Variables

Add the following environment variables to your `.env` file:

#### Using Connection String (Option A)

```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=your_account_name;AccountKey=your_account_key;EndpointSuffix=core.windows.net"
AZURE_STORAGE_CONTAINER_NAME="uploads"
```

#### Using Account Name and Key (Option B)

```bash
AZURE_STORAGE_ACCOUNT_NAME="your_account_name"
AZURE_STORAGE_ACCOUNT_KEY="your_account_key"
AZURE_STORAGE_CONTAINER_NAME="uploads"
```

### 5. Additional Configuration (Optional)

You can customize the upload behavior with these optional environment variables:

```bash
# Pre-signed URL expiration time in minutes (default: 60)
AZURE_SAS_TOKEN_EXPIRY_MINUTES=60

# Maximum file size in MB (default: 100)
MAX_UPLOAD_SIZE_MB=100

# Allowed file extensions (comma-separated, default: jpg,jpeg,png,gif,pdf,doc,docx,xls,xlsx,txt,csv,zip,rar)
ALLOWED_FILE_EXTENSIONS="jpg,jpeg,png,gif,pdf,doc,docx,xls,xlsx,txt,csv,zip,rar"
```

## Security Best Practices

### 1. Access Control

- **Use Private containers** for sensitive files
- **Implement authentication** on your API endpoints (already implemented)
- **Use SAS tokens** with appropriate permissions and expiration times

### 2. Network Security

- Consider using **Azure Private Endpoints** for production
- Enable **Storage account firewall** to restrict access by IP address
- Use **Virtual Network Service Endpoints** if applicable

### 3. Data Protection

- Enable **Soft delete** for blob storage to recover accidentally deleted files
- Enable **Versioning** for important files
- Configure **Lifecycle management** to automatically move or delete old files

### 4. Monitoring

- Enable **Storage Analytics** for logging and metrics
- Set up **Alerts** for unusual activity
- Monitor **Access patterns** and costs

## Folder Structure

The system automatically organizes files using the following structure:

```
{container_name}/
  {folder}/          # Optional folder (e.g., "images", "documents")
    {prefix}/        # Optional prefix (e.g., user ID, category)
      YYYY/MM/DD/    # Date-based organization
        filename_uuid.ext
```

### Examples

- `uploads/images/user123/2025/01/15/photo_abc12345.jpg`
- `uploads/documents/2025/01/15/report_xyz67890.pdf`
- `uploads/profiles/2025/01/15/avatar_def45678.png`

## API Usage Examples

### 1. Get Upload Configuration

```bash
GET /api/upload/config
```

### 2. Generate Pre-signed URL

```bash
POST /api/upload/presigned-url
Content-Type: application/json
Authorization: Bearer {access_token}

{
  "filename": "document.pdf",
  "folder": "documents",
  "prefix": "user123",
  "expiry_minutes": 60,
  "metadata": {
    "uploaded_by": "user123",
    "category": "invoice"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Pre-signed URL generated successfully",
  "data": {
    "blob_name": "documents/user123/2025/12/05/document_abc12345.pdf",
    "presigned_url": "https://...",
    "content_type": "application/pdf",
    "expires_at": "2025-12-05T19:33:47.4843364Z",
    "expiry_minutes": 60,
    "upload_instructions": {
      "method": "PUT",
      "required_headers": {
        "x-ms-blob-type": "BlockBlob",
        "Content-Type": "application/pdf"
      }
    }
  }
}
```

### 3. Upload Using Pre-signed URL

**IMPORTANT**: The `x-ms-blob-type: BlockBlob` header is **REQUIRED** for all uploads to Azure Blob Storage. Without this header, the upload will fail with a `MissingRequiredHeader` error.

Upload directly to the returned `presigned_url` using a PUT request:

```bash
PUT {presigned_url}
Content-Type: application/pdf
x-ms-blob-type: BlockBlob

[file content as binary]
```

**Example using cURL:**
```bash
curl -X PUT "{presigned_url}" \
  -H "x-ms-blob-type: BlockBlob" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

**Example using JavaScript (fetch):**
```javascript
const response = await fetch(presignedUrl, {
  method: 'PUT',
  headers: {
    'x-ms-blob-type': 'BlockBlob',
    'Content-Type': 'application/pdf'
  },
  body: fileBlob
});
```

**Example using Python (requests):**
```python
import requests

with open('document.pdf', 'rb') as f:
    response = requests.put(
        presigned_url,
        headers={
            'x-ms-blob-type': 'BlockBlob',
            'Content-Type': 'application/pdf'
        },
        data=f
    )
```

The response from the pre-signed URL endpoint includes `upload_instructions` with all required headers.

### 4. Direct Upload

```bash
POST /api/upload/direct
Content-Type: multipart/form-data

file: [binary file]
folder: "images"
prefix: "user123"
```

### 5. Get File Information

```bash
GET /api/upload/file/info?blob_name=images/user123/2025/01/15/photo_abc12345.jpg&generate_sas=true
```

### 6. Delete File

```bash
DELETE /api/upload/file
Content-Type: application/json

{
  "blob_name": "images/user123/2025/01/15/photo_abc12345.jpg"
}
```

## Troubleshooting

### Common Issues

1. **"Azure Blob Storage credentials not configured"**
   - Ensure you've set either `AZURE_STORAGE_CONNECTION_STRING` or both `AZURE_STORAGE_ACCOUNT_NAME` and `AZURE_STORAGE_ACCOUNT_KEY`

2. **"Container not found"**
   - The system will automatically create the container if it doesn't exist
   - Ensure the storage account name and credentials are correct

3. **"File size exceeds maximum"**
   - Check the `MAX_UPLOAD_SIZE_MB` setting
   - Increase it if needed (consider Azure limits)

4. **"File extension not allowed"**
   - Check the `ALLOWED_FILE_EXTENSIONS` setting
   - Add the extension if needed

5. **Pre-signed URL expires too quickly**
   - Increase `AZURE_SAS_TOKEN_EXPIRY_MINUTES` (max 1440 minutes = 24 hours)

### Azure Storage Limits

- **Maximum blob size**: 4.75 TB (for block blobs)
- **Maximum container size**: Unlimited
- **Maximum number of containers**: Unlimited
- **SAS token maximum expiry**: 24 hours (for account-level SAS)

## Cost Optimization

1. **Use appropriate storage tier**:
   - Hot: Frequently accessed files
   - Cool: Infrequently accessed files (lower cost)
   - Archive: Rarely accessed files (lowest cost)

2. **Enable lifecycle management** to automatically move files to cooler tiers

3. **Monitor usage** through Azure Cost Management

4. **Use compression** for large files when possible

## Testing

After setup, test the configuration:

1. **Test direct upload**:
2.

   ```bash
   curl -X POST http://localhost:8000/api/upload/direct \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -F "file=@test.jpg" \
     -F "folder=test"
   ```

3. **Test pre-signed URL**:
4.

   ```bash
   curl -X POST http://localhost:8000/api/upload/presigned-url \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"filename": "test.jpg", "folder": "test"}'
   ```

## Support

For Azure-specific issues, refer to:

- [Azure Blob Storage Documentation](https://docs.microsoft.com/azure/storage/blobs/)
- [Azure Storage SDK for Python](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/storage/azure-storage-blob)

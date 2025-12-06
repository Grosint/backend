# Quick Guide: Uploading Files Using Pre-signed URLs in Postman

## The Problem
When uploading to Azure Blob Storage using a pre-signed URL, you **MUST** include the `x-ms-blob-type: BlockBlob` header. Without it, you'll get:
```
400 Bad Request
MissingRequiredHeader: x-ms-blob-type
```

## Solution: Step-by-Step Instructions

### Option 1: Use the Pre-configured Request (Recommended)

1. **Generate Pre-signed URL:**
   - Use the "Generate Pre-signed URL" request in the Postman collection
   - This automatically saves `presigned_url` and `content_type` to environment variables

2. **Upload File:**
   - Use the "Upload Using Pre-signed URL" request
   - The headers are already configured correctly
   - Just select your file in the Body tab

### Option 2: Manual Setup

If you're creating your own request or the auto-save didn't work:

1. **Create a new PUT request** in Postman

2. **Set the URL:**
   - Paste the full `presigned_url` from the "Generate Pre-signed URL" response
   - Example: `https://grosintstorage.blob.core.windows.net/uploads/documents/user123/2025/12/05/document_abc12345.pdf?se=...`

3. **Add REQUIRED Headers:**
   - Click on the "Headers" tab
   - Add these headers (both are required):

   | Key | Value | Required |
   |-----|-------|----------|
   | `x-ms-blob-type` | `BlockBlob` | ✅ YES - Without this, upload will fail! |
   | `Content-Type` | `application/pdf` (or your file type) | ✅ YES |

   **Important:** The `x-ms-blob-type` header is case-sensitive and must be exactly `BlockBlob`.

4. **Set the Body:**
   - Go to the "Body" tab
   - Select "binary" or "file"
   - Choose your file

5. **Send the request**

## Common Mistakes

❌ **Wrong:** Only setting `Content-Type` header
✅ **Correct:** Setting both `x-ms-blob-type: BlockBlob` AND `Content-Type`

❌ **Wrong:** Using `x-ms-blob-type: blockblob` (lowercase)
✅ **Correct:** Using `x-ms-blob-type: BlockBlob` (exact case)

❌ **Wrong:** Using POST method
✅ **Correct:** Using PUT method

## Example Headers in Postman

When you add the headers, they should look like this:

```
Headers (2)
┌─────────────────────┬─────────────────────────────┐
│ Key                  │ Value                       │
├─────────────────────┼─────────────────────────────┤
│ x-ms-blob-type      │ BlockBlob                    │
│ Content-Type        │ application/pdf              │
└─────────────────────┴─────────────────────────────┘
```

## Testing

After sending the request, you should get:
- **Status:** `201 Created` (successful upload)
- **Response:** Empty body or minimal response

If you get `400 Bad Request` with `MissingRequiredHeader`, check that:
1. The `x-ms-blob-type` header is present
2. The value is exactly `BlockBlob` (not `blockblob` or `BlockBlob ` with spaces)
3. The header name is exactly `x-ms-blob-type` (case-sensitive)

## Using cURL (for reference)

```bash
curl -X PUT "{presigned_url}" \
  -H "x-ms-blob-type: BlockBlob" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

## Using JavaScript (for reference)

```javascript
const response = await fetch(presignedUrl, {
  method: 'PUT',
  headers: {
    'x-ms-blob-type': 'BlockBlob',  // REQUIRED!
    'Content-Type': 'application/pdf'
  },
  body: fileBlob
});
```

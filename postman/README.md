# GROSINT V2 API - Postman Collection

This folder contains the complete Postman collection, environments, and globals for the GROSINT V2 Backend API.

## 📁 Folder Structure

```
postman/
├── collections/
│   └── GROSINT_V2_API.postman_collection.json  # Main API collection
├── environments/
│   ├── Local.postman_environment.json          # Local development environment
│   └── Production.postman_environment.json      # Production environment
├── globals/
│   └── workspace.postman_globals.json          # Global variables
└── README.md                                    # This file
```

## 🚀 Quick Start

### Import into Postman

1. **Import Collection:**
   - Open Postman
   - Click **Import** button
   - Select `collections/GROSINT_V2_API.postman_collection.json`
   - Click **Import**

2. **Import Environments:**
   - Click **Import** button
   - Select both environment files:
     - `environments/Local.postman_environment.json`
     - `environments/Production.postman_environment.json`
   - Click **Import**

3. **Import Globals (Optional):**
   - Click **Import** button
   - Select `globals/workspace.postman_globals.json`
   - Click **Import**

4. **Select Environment:**
   - In the top-right corner of Postman, select the environment you want to use:
     - **Local** - for local development (http://localhost:8000/api)
     - **Production** - for production (https://40.81.229.12/api)

## 📋 Collection Structure

### Authentication
- **Login** - Authenticate and get JWT tokens (auto-saves tokens)
- **Refresh Token** - Refresh access token
- **Logout** - Invalidate tokens
- **Change Password** - Update user password
- **Get Auth Status** - Get current authentication status
- **Get Token Info** - Get detailed token information
- **Validate Token** - Validate token and get user info
- **Send OTP** - Send OTP to user email
- **Verify OTP** - Verify OTP and activate account
- **Resend OTP** - Resend OTP to user email

### User Management
- **Create User** - Create new user account (OTP sent automatically)
- **Get Current User Info** - Get authenticated user information
- **Update Current User** - Update user profile
- **List Users** - List users with pagination (admin only)
- **Delete User** - Delete user by ID (admin only)

### Search
- **Phone Lookup** - Create and execute phone lookup search
- **Email Lookup** - Create and execute email lookup search
- **Get Search Results** - Get search results by search ID
- **List Searches** - Get searches with pagination
- **Get Search Statistics** - Get search statistics

### Admin
- **Authentication** - Admin login endpoints
- **Test Phone Lookup Service** - Test individual phone lookup services
- **Test Email Lookup Service** - Test individual email lookup services
- **Service Health Checks** - Health checks for all services
- **List Available Services** - List all available services

### Health Check
- **Health Check** - System health endpoint

## 🔑 Environment Variables

### Local Environment
- `base_url`: `http://localhost:8000/api`
- `access_token`: Auto-populated from login
- `refresh_token`: Auto-populated from login
- `admin_token`: Auto-populated from admin login
- `user_id`: Auto-populated from login
- `search_id`: Manually set after creating a search
- `user_email`: Default test email
- `user_password`: Default test password

### Production Environment
- `base_url`: `https://40.81.229.12/api`
- Same variables as Local environment

## 🔄 Auto-Populated Variables

The collection automatically saves tokens and user information:

- **Login** → Saves `access_token`, `refresh_token`, `user_id`
- **Admin Login** → Saves `admin_token` and `access_token`
- **Refresh Token** → Updates `access_token`

## 📝 Usage Tips

1. **First Time Setup:**
   - Use **Create User** endpoint to create a test account
   - Use **Login** endpoint to authenticate
   - Tokens are automatically saved to environment variables

2. **Testing Admin Endpoints:**
   - Use **Admin > 🔐 Authentication > Login (Get Admin Token)** to get admin token
   - Admin token is saved to `admin_token` variable

3. **Testing Search:**
   - Use **Phone Lookup** or **Email Lookup** to create a search
   - Copy the `search_id` from response
   - Use **Get Search Results** with the `search_id` to retrieve results

4. **Environment Switching:**
   - Switch between Local and Production environments using the dropdown in Postman
   - All requests will use the correct base URL automatically

## 🧪 Test Scripts

The collection includes automatic test scripts that:
- Extract and save tokens from login responses
- Validate response structure
- Check status codes

## 📚 API Documentation

For detailed API documentation, visit:
- **Swagger UI**: http://localhost:8000/api/docs (Local)
- **ReDoc**: http://localhost:8000/api/redoc (Local)

## 🔒 Security Notes

- Tokens are stored as environment variables (not in collection)
- Use **secret** type for sensitive variables in environments
- Never commit actual tokens or passwords to version control
- Update `user_email` and `user_password` in environments with your test credentials

## 🛠️ Maintenance

When adding new endpoints:
1. Add them to the appropriate folder in the collection
2. Use environment variables for base URLs and tokens
3. Add descriptions for each endpoint
4. Include example request bodies
5. Update this README if needed

## 📞 Support

For issues or questions about the API:
- Check the API documentation at `/api/docs`
- Review the codebase in `app/api/endpoints/`
- Check server logs for detailed error messages

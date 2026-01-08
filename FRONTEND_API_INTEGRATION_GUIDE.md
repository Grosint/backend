# Frontend API Integration Guide

Complete API documentation with request/response formats, error handling, and integration prompts for frontend LLM.

## Table of Contents
1. [Base Configuration](#base-configuration)
2. [Authentication Flow](#authentication-flow)
3. [Plan Management APIs](#plan-management-apis)
4. [Prepaid Payment APIs](#prepaid-payment-apis)
5. [Subscription APIs](#subscription-apis)
6. [Credit Management APIs](#credit-management-apis)
7. [Error Handling](#error-handling)
8. [Complete Integration Prompts](#complete-integration-prompts)

---

## Base Configuration

### API Base URL
```
Production: https://your-api-domain.com/api/v1
Development: http://localhost:8000/api/v1
```

### Headers
All authenticated requests require:
```javascript
{
  "Content-Type": "application/json",
  "Authorization": "Bearer <access_token>"
}
```

### Response Format
All API responses follow this structure:
```typescript
interface SuccessResponse<T> {
  success: true;
  message: string;
  timestamp: string; // ISO 8601 format
  data: T;
}

interface ErrorResponse {
  success: false;
  message: string;
  timestamp: string;
  error_code: string;
  details?: Record<string, any>;
  validation_errors?: Array<{
    field: string;
    message: string;
    value?: any;
  }>;
}
```

---

## Authentication Flow

### 1. User Registration
**Endpoint:** `POST /api/v1/auth/register` (if exists) or `POST /api/v1/user`

**Request:**
```typescript
{
  email: string;
  password: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
}
```

**Success Response (201):**
```typescript
{
  success: true;
  message: "User created successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    id: string;
    email: string;
    firstName?: string;
    lastName?: string;
    isActive: boolean;
    isVerified: boolean;
    createdAt: string;
  };
}
```

**Error Responses:**
- `400` - Validation error
- `409` - User already exists
- `500` - Server error

### 2. Send OTP
**Endpoint:** `POST /api/v1/auth/send-otp`

**Request:**
```typescript
{
  email: string;
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "OTP sent successfully to your email";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    message: "OTP sent successfully";
    expires_in: 600; // seconds (10 minutes)
  };
}
```

**Error Responses:**
- `404` - User not found
- `500` - Failed to send OTP

### 3. Verify OTP
**Endpoint:** `POST /api/v1/auth/verify-otp`

**Request:**
```typescript
{
  email: string;
  otp: string;
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "OTP verified successfully...";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    message: "OTP verified successfully";
    verified_at: string; // ISO 8601
    is_verified: boolean; // true for gov emails, false for others
  };
}
```

**Error Responses:**
- `400` - Invalid or expired OTP
- `404` - User not found
- `500` - Server error

### 4. Login
**Endpoint:** `POST /api/v1/auth/login`

**Request:**
```typescript
{
  email: string;
  password: string;
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Login successful";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    access_token: string;
    refresh_token: string;
    token_type: "bearer";
    expires_in: number; // seconds
  };
}
```

**Error Responses:**
- `401` - Invalid credentials
- `422` - Validation error
- `500` - Server error

### 5. Refresh Token
**Endpoint:** `POST /api/v1/auth/refresh`

**Request:**
```typescript
{
  refresh_token: string;
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Token refreshed successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    access_token: string;
    token_type: "bearer";
    expires_in: number;
  };
}
```

**Error Responses:**
- `401` - Invalid or expired refresh token
- `500` - Server error

### 6. Logout
**Endpoint:** `POST /api/v1/auth/logout`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```typescript
{
  refresh_token?: string; // Optional
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Logout successful";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    message: "Logged out successfully";
  };
}
```

### 7. Get Auth Status
**Endpoint:** `GET /api/v1/auth/me`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Authentication status retrieved";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    is_authenticated: true;
    user_id: string;
    email: string;
    token_type: "bearer";
    expires_at: string; // ISO 8601
  };
}
```

---

## Plan Management APIs

### 1. List Plans
**Endpoint:** `GET /api/v1/plans?active_only=true`

**Query Parameters:**
- `active_only` (boolean, default: true) - Show only active plans

**Success Response (200):**
```typescript
{
  success: true;
  message: "Plans retrieved successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: [
    {
      id: string;
      name: string;
      cashfreePlanId: string | null;
      price: number; // in paise
      credits: number;
      durationInDays: number;
      isPrepaid: boolean; // true = Prepaid, false = Subscription
      isActive: boolean;
      discount: number; // in paise
      createdAt: string;
      updatedAt: string;
    }
  ];
}
```

**Error Responses:**
- `500` - Server error

### 2. Get Plan by ID
**Endpoint:** `GET /api/v1/plans/{plan_id}`

**Success Response (200):**
```typescript
{
  success: true;
  message: "Plan retrieved successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    id: string;
    name: string;
    cashfreePlanId: string | null;
    price: number;
    credits: number;
    durationInDays: number;
    isPrepaid: boolean;
    isActive: boolean;
    discount: number;
    createdAt: string;
    updatedAt: string;
  };
}
```

**Error Responses:**
- `404` - Plan not found
- `500` - Server error

---

## Prepaid Payment APIs

### 1. Create Payment Order
**Endpoint:** `POST /api/v1/payments/create`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request:**
```typescript
{
  planId: string;
  origin: string; // Frontend URL for redirect (e.g., "https://yourapp.com")
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Payment order created successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    paymentSessionId: string; // Use this to redirect to Cashfree
    orderId: string;
    redirectUrl: string | null;
  };
}
```

**Error Responses:**
- `400` - Invalid plan or plan not active
- `404` - Plan or user not found
- `401` - Unauthorized
- `500` - Server error

**Frontend Flow:**
1. User selects prepaid plan
2. Call this API with `planId` and `origin`
3. Redirect user to Cashfree using `paymentSessionId`
4. User completes payment on Cashfree
5. Cashfree redirects back to `{origin}/api/v1/payments/redirect/{orderId}`
6. Poll or verify payment status using `/payments/verify/{orderId}`

### 2. Verify Payment
**Endpoint:** `POST /api/v1/payments/verify/{order_id}`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Payment verified successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    orderId: string;
    status: "pending" | "completed" | "failed" | "cancelled" | "expired";
    amount: number; // in rupees
    paymentMethod: string | null;
    transactionTime: string | null; // ISO 8601
  };
}
```

**Error Responses:**
- `404` - Payment not found
- `401` - Unauthorized
- `500` - Server error

**Frontend Flow:**
- Call this endpoint after user returns from Cashfree
- Poll every 2-3 seconds if status is "pending"
- Show success message when status is "completed"
- Show error message for other statuses

### 3. Payment Redirect Page
**Endpoint:** `GET /api/v1/payments/redirect/{order_id}`

**Note:** This is a server-side HTML page. Frontend should handle redirects differently.

**Frontend Implementation:**
```javascript
// After user returns from Cashfree
const orderId = new URLSearchParams(window.location.search).get('order_id');
if (orderId) {
  // Poll payment status
  pollPaymentStatus(orderId);
}

async function pollPaymentStatus(orderId) {
  const maxAttempts = 10;
  let attempts = 0;

  const interval = setInterval(async () => {
    attempts++;
    const response = await fetch(`/api/v1/payments/verify/${orderId}`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });

    const result = await response.json();

    if (result.data.status === 'completed') {
      clearInterval(interval);
      // Show success, refresh credit balance
      showSuccessMessage();
      refreshCreditBalance();
    } else if (result.data.status !== 'pending' || attempts >= maxAttempts) {
      clearInterval(interval);
      // Show error
      showErrorMessage(result.data.status);
    }
  }, 2000);
}
```

---

## Subscription APIs

### 1. Create Subscription
**Endpoint:** `POST /api/v1/subscriptions/create`

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request:**
```typescript
{
  planId: string;
  origin: string; // Frontend URL for redirect
}
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Subscription created successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    cashfreeSubscriptionId: string;
    subscriptionSessionId: string; // Use this to redirect to Cashfree
    redirectUrl: string | null;
  };
}
```

**Error Responses:**
- `400` - Invalid plan, plan is prepaid, or missing Cashfree plan ID
- `404` - Plan or user not found
- `401` - Unauthorized
- `500` - Server error

**Frontend Flow:**
1. User selects subscription plan
2. Call this API with `planId` and `origin`
3. Redirect user to Cashfree using `subscriptionSessionId`
4. User authorizes subscription on Cashfree
5. Cashfree redirects back to `{origin}/api/v1/subscriptions/redirect/{subscription_id}`
6. Subscription is activated via webhook (no polling needed)

### 2. Get User Subscriptions
**Endpoint:** `GET /api/v1/subscriptions/me`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Subscriptions retrieved successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: [
    {
      id: string;
      userId: string;
      planId: string;
      cfSubscriptionId: string | null;
      status: "initialized" | "pending" | "active" | "cancelled" | "expired";
      startDate: string | null; // ISO 8601
      nextBillingDate: string | null; // ISO 8601
      createdAt: string;
      updatedAt: string;
    }
  ];
}
```

**Error Responses:**
- `401` - Unauthorized
- `500` - Server error

### 3. Cancel Subscription
**Endpoint:** `POST /api/v1/subscriptions/{subscription_id}/cancel`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Subscription cancelled successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    success: true;
    message: "Subscription cancelled successfully";
  };
}
```

**Error Responses:**
- `403` - Not authorized to cancel this subscription
- `404` - Subscription not found
- `401` - Unauthorized
- `500` - Server error

---

## Credit Management APIs

### 1. Get Credit Balance
**Endpoint:** `GET /api/v1/credits/balance`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Success Response (200):**
```typescript
{
  success: true;
  message: "Credit balance retrieved successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: {
    totalAvailableCredits: number;
    creditsByType: {
      ON_DEMAND?: {
        totalCredits: number;
        credits: Array<{
          creditsId: string;
          credits: number;
          expiresAt: string | null; // ISO 8601
          createdAt: string; // ISO 8601
        }>;
      };
      PERIODIC?: {
        totalCredits: number;
        credits: Array<{
          creditsId: string;
          credits: number;
          expiresAt: string | null;
          createdAt: string;
        }>;
      };
    };
  };
}
```

**Error Responses:**
- `401` - Unauthorized
- `500` - Server error

### 2. Get Credit Transactions
**Endpoint:** `GET /api/v1/credits/transactions?skip=0&limit=100&txn_type=CREDIT`

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `skip` (number, default: 0) - Number of records to skip
- `limit` (number, default: 100, max: 1000) - Number of records to return
- `txn_type` (string, optional) - Filter by "CREDIT" or "DEBIT"

**Success Response (200):**
```typescript
{
  success: true;
  message: "Credit transactions retrieved successfully";
  timestamp: "2024-01-01T00:00:00Z";
  data: [
    {
      id: string;
      userId: string;
      creditsId: string;
      txnType: "CREDIT" | "DEBIT";
      creditsUsed: number;
      service: string | null; // e.g., "SERVICE_DEDUCTION", "CREDIT_CREATED"
      createdAt: string; // ISO 8601
    }
  ];
}
```

**Error Responses:**
- `401` - Unauthorized
- `422` - Validation error (invalid query params)
- `500` - Server error

---

## Error Handling

### Error Response Structure
```typescript
interface ErrorResponse {
  success: false;
  message: string;
  timestamp: string;
  error_code: string;
  details?: Record<string, any>;
  validation_errors?: Array<{
    field: string;
    message: string;
    value?: any;
  }>;
}
```

### Common Error Codes

| Error Code | Status | Description |
|------------|--------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `AUTHENTICATION_ERROR` | 401 | Authentication failed |
| `AUTHORIZATION_ERROR` | 403 | Access denied |
| `CONFLICT` | 409 | Resource already exists |
| `BUSINESS_LOGIC_ERROR` | 400 | Business rule violation |
| `EXTERNAL_SERVICE_ERROR` | 502 | External service failure |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected server error |

### Error Handling Example
```typescript
async function handleApiCall<T>(
  apiCall: () => Promise<Response>
): Promise<SuccessResponse<T>> {
  try {
    const response = await apiCall();
    const data = await response.json();

    if (!response.ok) {
      // Handle error response
      const error: ErrorResponse = data;

      switch (error.error_code) {
        case 'VALIDATION_ERROR':
          // Show validation errors
          error.validation_errors?.forEach(err => {
            showFieldError(err.field, err.message);
          });
          break;
        case 'AUTHENTICATION_ERROR':
          // Redirect to login
          redirectToLogin();
          break;
        case 'NOT_FOUND':
          showError(error.message);
          break;
        default:
          showError(error.message || 'An error occurred');
      }

      throw new Error(error.message);
    }

    return data as SuccessResponse<T>;
  } catch (error) {
    if (error instanceof TypeError) {
      // Network error
      showError('Network error. Please check your connection.');
    }
    throw error;
  }
}
```

### Token Refresh on 401
```typescript
let refreshTokenPromise: Promise<string> | null = null;

async function apiRequest<T>(
  url: string,
  options: RequestInit = {}
): Promise<SuccessResponse<T>> {
  let accessToken = getAccessToken();

  const makeRequest = async (token: string) => {
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
  };

  let response = await makeRequest(accessToken);

  // If 401, try to refresh token
  if (response.status === 401 && getRefreshToken()) {
    if (!refreshTokenPromise) {
      refreshTokenPromise = refreshAccessToken();
    }

    const newAccessToken = await refreshTokenPromise;
    refreshTokenPromise = null;

    // Retry with new token
    response = await makeRequest(newAccessToken);
  }

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message);
  }

  return response.json();
}

async function refreshAccessToken(): Promise<string> {
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: getRefreshToken() }),
  });

  if (!response.ok) {
    // Refresh failed, redirect to login
    redirectToLogin();
    throw new Error('Token refresh failed');
  }

  const data = await response.json();
  setAccessToken(data.data.access_token);
  return data.data.access_token;
}
```

---

## Complete Integration Prompts

### Prompt 1: Payment Flow Integration

```
I need to integrate a payment system with the following backend API:

BASE_URL: https://api.example.com/api/v1

AUTHENTICATION:
- All authenticated endpoints require: Authorization: Bearer <access_token>
- Token obtained from: POST /auth/login with {email, password}
- Returns: {access_token, refresh_token, expires_in}
- Refresh token via: POST /auth/refresh with {refresh_token}

PLAN MANAGEMENT:
- List plans: GET /plans?active_only=true
- Returns array of plans with: {id, name, price (paise), credits, durationInDays, isPrepaid (boolean), isActive}
- Filter prepaid: plans.filter(p => p.isPrepaid === true)
- Filter subscriptions: plans.filter(p => p.isPrepaid === false)

PREPAID PAYMENT FLOW:
1. User selects prepaid plan
2. POST /payments/create with {planId, origin: window.location.origin}
3. Response: {paymentSessionId, orderId, redirectUrl}
4. Redirect user to Cashfree using paymentSessionId
5. After payment, user returns to {origin}/api/v1/payments/redirect/{orderId}
6. Poll payment status: POST /payments/verify/{orderId} every 2 seconds
7. When status === "completed", show success and refresh credit balance
8. If status !== "pending" && status !== "completed", show error

SUBSCRIPTION FLOW:
1. User selects subscription plan
2. POST /subscriptions/create with {planId, origin: window.location.origin}
3. Response: {subscriptionSessionId, cashfreeSubscriptionId}
4. Redirect user to Cashfree using subscriptionSessionId
5. After authorization, user returns to {origin}/api/v1/subscriptions/redirect/{subscription_id}
6. Subscription activated via webhook (no polling needed)
7. Show success message

CREDIT MANAGEMENT:
- Get balance: GET /credits/balance
- Returns: {totalAvailableCredits, creditsByType: {ON_DEMAND, PERIODIC}}
- Get transactions: GET /credits/transactions?skip=0&limit=100

ERROR HANDLING:
- All responses: {success: boolean, message: string, data: T, error_code?: string}
- 401: Refresh token or redirect to login
- 422: Show validation_errors array
- 404: Show "Resource not found"
- 500: Show "Server error, please try again"

Create a complete React/TypeScript implementation with:
- API service layer with error handling
- Token refresh logic
- Payment flow components
- Subscription flow components
- Credit balance display
- Error toast notifications
```

### Prompt 2: Complete API Client

```
Create a TypeScript API client for this backend with the following requirements:

API BASE: https://api.example.com/api/v1

RESPONSE FORMAT:
All responses: {success: boolean, message: string, timestamp: string, data: T}
Errors: {success: false, message: string, error_code: string, details?: object}

AUTHENTICATION:
- Store tokens in localStorage/sessionStorage
- Auto-refresh on 401 errors
- Intercept all requests to add Authorization header

ENDPOINTS TO IMPLEMENT:

1. AUTH:
   - login(email, password): POST /auth/login
   - refreshToken(refreshToken): POST /auth/refresh
   - logout(refreshToken?): POST /auth/logout
   - getAuthStatus(): GET /auth/me

2. PLANS:
   - listPlans(activeOnly?): GET /plans?active_only={activeOnly}
   - getPlan(id): GET /plans/{id}

3. PAYMENTS:
   - createPayment(planId, origin): POST /payments/create
   - verifyPayment(orderId): POST /payments/verify/{orderId}

4. SUBSCRIPTIONS:
   - createSubscription(planId, origin): POST /subscriptions/create
   - getUserSubscriptions(): GET /subscriptions/me
   - cancelSubscription(id): POST /subscriptions/{id}/cancel

5. CREDITS:
   - getCreditBalance(): GET /credits/balance
   - getTransactions(skip?, limit?, txnType?): GET /credits/transactions

REQUIREMENTS:
- Type-safe with TypeScript interfaces
- Error handling with custom error classes
- Request/response interceptors
- Token refresh on 401
- Retry logic for network errors
- Loading states
- Export as ES6 module
```

### Prompt 3: Payment UI Components

```
Create React components for payment integration:

REQUIREMENTS:

1. PLAN SELECTION COMPONENT:
   - Fetch plans from GET /plans
   - Display prepaid and subscription plans separately
   - Show: name, price (convert paise to rupees), credits, duration
   - Button to select plan

2. PREPAID PAYMENT COMPONENT:
   - On plan select, call POST /payments/create
   - Show loading state
   - Redirect to Cashfree using paymentSessionId
   - After redirect back, poll POST /payments/verify/{orderId}
   - Show: "Processing payment..." while polling
   - On success: "Payment successful! Credits added."
   - On failure: "Payment failed: {status}"
   - Refresh credit balance after success

3. SUBSCRIPTION COMPONENT:
   - On plan select, call POST /subscriptions/create
   - Show loading state
   - Redirect to Cashfree using subscriptionSessionId
   - After redirect back, show: "Subscription activated!"
   - Display subscription status from GET /subscriptions/me
   - Show cancel button that calls POST /subscriptions/{id}/cancel

4. CREDIT BALANCE COMPONENT:
   - Fetch from GET /credits/balance
   - Display totalAvailableCredits prominently
   - Show breakdown by type (ON_DEMAND, PERIODIC)
   - Show expiry dates for each credit
   - Auto-refresh after payment/subscription

5. ERROR HANDLING:
   - Toast notifications for errors
   - Handle 401: redirect to login
   - Handle 422: show validation errors
   - Handle network errors: show retry button

TECH STACK:
- React 18+ with TypeScript
- React Query for data fetching
- React Router for navigation
- Toast library for notifications
- Tailwind CSS for styling
```

### Prompt 4: Error Handling Guide

```
Implement comprehensive error handling for this API:

API RESPONSE FORMAT:
Success: {success: true, message: string, data: T, timestamp: string}
Error: {success: false, message: string, error_code: string, details?: object, validation_errors?: array}

ERROR CODES:
- VALIDATION_ERROR (422): Show field-level errors from validation_errors array
- NOT_FOUND (404): "Resource not found"
- AUTHENTICATION_ERROR (401): Redirect to login, refresh token if possible
- AUTHORIZATION_ERROR (403): "You don't have permission"
- CONFLICT (409): "Resource already exists"
- BUSINESS_LOGIC_ERROR (400): Show message from API
- EXTERNAL_SERVICE_ERROR (502): "Payment gateway error, please try again"
- INTERNAL_SERVER_ERROR (500): "Server error, please try again"

IMPLEMENTATION REQUIREMENTS:

1. API CLIENT:
   - Intercept all responses
   - Check response.success
   - Throw typed errors for error responses
   - Handle network errors separately

2. ERROR BOUNDARY:
   - React Error Boundary for component errors
   - Fallback UI with retry button

3. TOAST NOTIFICATIONS:
   - Success: Green toast with message
   - Error: Red toast with error_code and message
   - Validation: Show all validation_errors

4. TOKEN REFRESH:
   - On 401, attempt token refresh
   - If refresh fails, redirect to login
   - Retry original request with new token

5. RETRY LOGIC:
   - Retry network errors 3 times with exponential backoff
   - Don't retry 4xx errors (except 401)
   - Show loading state during retries

6. USER-FRIENDLY MESSAGES:
   - Map error_codes to user-friendly messages
   - Show technical details only in dev mode
   - Provide actionable next steps

Create a complete error handling system with examples.
```

---

## Complete Example: React Payment Integration

```typescript
// api/client.ts
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

interface ApiResponse<T> {
  success: boolean;
  message: string;
  timestamp: string;
  data?: T;
  error_code?: string;
  details?: any;
  validation_errors?: Array<{field: string; message: string}>;
}

class ApiClient {
  private getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  }

  private getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  private setTokens(accessToken: string, refreshToken?: string): void {
    localStorage.setItem('access_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  private async refreshAccessToken(): Promise<string> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const data: ApiResponse<{access_token: string}> = await response.json();

    if (!data.success || !data.data) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      throw new Error('Token refresh failed');
    }

    this.setTokens(data.data.access_token);
    return data.data.access_token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const token = this.getAccessToken();

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    // Handle 401 with token refresh
    if (response.status === 401 && token) {
      try {
        const newToken = await this.refreshAccessToken();
        headers['Authorization'] = `Bearer ${newToken}`;
        response = await fetch(`${API_BASE}${endpoint}`, {
          ...options,
          headers,
        });
      } catch (error) {
        // Refresh failed, will redirect to login
        throw error;
      }
    }

    const data: ApiResponse<T> = await response.json();

    if (!data.success) {
      const error = new Error(data.message);
      (error as any).error_code = data.error_code;
      (error as any).details = data.details;
      (error as any).validation_errors = data.validation_errors;
      throw error;
    }

    return data;
  }

  // Auth methods
  async login(email: string, password: string) {
    const response = await this.request<{
      access_token: string;
      refresh_token: string;
      token_type: string;
      expires_in: number;
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (response.data) {
      this.setTokens(response.data.access_token, response.data.refresh_token);
    }

    return response;
  }

  async logout() {
    const refreshToken = this.getRefreshToken();
    await this.request('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  // Plan methods
  async listPlans(activeOnly: boolean = true) {
    return this.request<Array<{
      id: string;
      name: string;
      price: number;
      credits: number;
      durationInDays: number;
      isPrepaid: boolean;
      isActive: boolean;
    }>>(`/plans?active_only=${activeOnly}`);
  }

  // Payment methods
  async createPayment(planId: string, origin: string) {
    return this.request<{
      paymentSessionId: string;
      orderId: string;
      redirectUrl: string | null;
    }>('/payments/create', {
      method: 'POST',
      body: JSON.stringify({ planId, origin }),
    });
  }

  async verifyPayment(orderId: string) {
    return this.request<{
      orderId: string;
      status: string;
      amount: number;
      paymentMethod: string | null;
      transactionTime: string | null;
    }>(`/payments/verify/${orderId}`, {
      method: 'POST',
    });
  }

  // Subscription methods
  async createSubscription(planId: string, origin: string) {
    return this.request<{
      cashfreeSubscriptionId: string;
      subscriptionSessionId: string;
      redirectUrl: string | null;
    }>('/subscriptions/create', {
      method: 'POST',
      body: JSON.stringify({ planId, origin }),
    });
  }

  async getUserSubscriptions() {
    return this.request<Array<{
      id: string;
      planId: string;
      status: string;
      startDate: string | null;
      nextBillingDate: string | null;
    }>>('/subscriptions/me');
  }

  async cancelSubscription(subscriptionId: string) {
    return this.request<{success: boolean; message: string}>(
      `/subscriptions/${subscriptionId}/cancel`,
      { method: 'POST' }
    );
  }

  // Credit methods
  async getCreditBalance() {
    return this.request<{
      totalAvailableCredits: number;
      creditsByType: Record<string, any>;
    }>('/credits/balance');
  }

  async getCreditTransactions(skip: number = 0, limit: number = 100, txnType?: string) {
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: limit.toString(),
    });
    if (txnType) params.append('txn_type', txnType);

    return this.request<Array<{
      id: string;
      txnType: string;
      creditsUsed: number;
      service: string | null;
      createdAt: string;
    }>>(`/credits/transactions?${params}`);
  }
}

export const apiClient = new ApiClient();
```

---

## Testing Checklist

### Authentication
- [ ] User can register
- [ ] User can send OTP
- [ ] User can verify OTP
- [ ] User can login
- [ ] Token refresh works
- [ ] Logout works
- [ ] 401 errors trigger token refresh

### Plans
- [ ] Can fetch all plans
- [ ] Can filter prepaid plans
- [ ] Can filter subscription plans
- [ ] Can get plan by ID

### Prepaid Payments
- [ ] Can create payment order
- [ ] Redirects to Cashfree correctly
- [ ] Payment verification works
- [ ] Polling stops on completion
- [ ] Credits are added after payment
- [ ] Error handling for failed payments

### Subscriptions
- [ ] Can create subscription
- [ ] Redirects to Cashfree correctly
- [ ] Can view user subscriptions
- [ ] Can cancel subscription
- [ ] Credits are added on activation

### Credits
- [ ] Can fetch credit balance
- [ ] Balance updates after payment
- [ ] Can fetch transactions
- [ ] Transaction filtering works

### Error Handling
- [ ] Validation errors display correctly
- [ ] Network errors show retry option
- [ ] 401 errors trigger login redirect
- [ ] Error toasts display properly

---

*Last Updated: Based on complete codebase analysis*

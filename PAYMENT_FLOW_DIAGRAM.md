# Payment System Flow Diagram

This document provides a complete flowchart of how the payment system works in the codebase, including both prepaid and subscription processes, plan management, and schedulers.

## Table of Contents
1. [Plan Management Flow](#plan-management-flow)
2. [Prepaid Payment Flow](#prepaid-payment-flow)
3. [Subscription Payment Flow](#subscription-payment-flow)
4. [Credit Management Flow](#credit-management-flow)
5. [Scheduler Flow](#scheduler-flow)
6. [Webhook Processing](#webhook-processing)

---

## Plan Management Flow

Plans are stored in the database and can be either **Prepaid** (`isPrepaid: true`) or **Subscription** (`isPrepaid: false`).

```mermaid
flowchart TD
    A[Admin Creates Plan] --> B{Plan Type?}
    B -->|isPrepaid: true| C[Prepaid Plan]
    B -->|isPrepaid: false| D[Subscription Plan]

    C --> E[Store in DB:<br/>- name<br/>- price paise<br/>- credits<br/>- durationInDays<br/>- isPrepaid: true<br/>- isActive: true]

    D --> F[Store in DB:<br/>- name<br/>- price paise<br/>- credits<br/>- durationInDays<br/>- isPrepaid: false<br/>- isActive: true]
    F --> G[Create Cashfree Plan]
    G --> H[Store cashfreePlanId in DB]

    E --> I[Plan Available in Collection]
    H --> I

    I --> J[User Fetches Plans<br/>GET /api/v1/plans/]
    J --> K{Filter by isPrepaid}
    K -->|true| L[Show Prepaid Plans]
    K -->|false| M[Show Subscription Plans]
```

**Key Points:**
- Plans are stored in MongoDB `plans` collection
- Prepaid plans don't need Cashfree plan ID
- Subscription plans require Cashfree plan creation and `cashfreePlanId`
- Plans can be fetched via `GET /api/v1/plans/` endpoint
- Only active plans (`isActive: true`) are shown by default

---

## Prepaid Payment Flow

Prepaid payments are one-time purchases that immediately grant credits.

```mermaid
flowchart TD
    A[User Selects Prepaid Plan] --> B[POST /api/v1/payments/create<br/>planId, origin]
    B --> C[PaymentService.create_payment]

    C --> D[Validate User & Plan]
    D --> E{Plan Valid?}
    E -->|No| F[Return Error]
    E -->|Yes| G[Generate Order ID]

    G --> H[Create Cashfree Payment Order]
    H --> I[Get payment_session_id]

    I --> J[Create Payment Record in DB:<br/>- userId<br/>- planId<br/>- cfOrderId<br/>- cfPaymentId<br/>- amount<br/>- status: PENDING]

    J --> K[Return paymentSessionId to User]
    K --> L[User Redirected to Cashfree]

    L --> M{Payment Status?}
    M -->|Success| N[Cashfree Webhook<br/>POST /api/v1/payments/webhook]
    M -->|User Returns| O[GET /api/v1/payments/verify/{order_id}]

    N --> P[PaymentService.process_webhook]
    O --> Q[PaymentService.verify_payment]

    P --> R{Status = COMPLETED?}
    Q --> R

    R -->|Yes| S[_activate_credits_for_payment]
    R -->|No| T[Update Payment Status Only]

    S --> U[Get Plan Details]
    U --> V[Calculate Expiry Date<br/>now + durationInDays]
    V --> W[CreditService.create_credit]
    W --> X[Create Credit Record:<br/>- userId<br/>- type: ON_DEMAND<br/>- credits: plan.credits<br/>- expiresAt: calculated]
    X --> Y[Create CreditTxn Record:<br/>- txnType: CREDIT<br/>- creditsUsed: plan.credits]

    T --> Z[End]
    Y --> Z
```

**Key Points:**
- Prepaid payments create `ON_DEMAND` type credits
- Credits expire based on `plan.durationInDays`
- Payment status tracked in `payments` collection
- Credits activated immediately upon successful payment
- Transaction records created for audit trail

---

## Subscription Payment Flow

Subscriptions are recurring payments that grant periodic credits.

```mermaid
flowchart TD
    A[User Selects Subscription Plan] --> B[POST /api/v1/subscriptions/create<br/>planId, origin]
    B --> C[SubscriptionService.create_subscription]

    C --> D[Validate User & Plan]
    D --> E{Plan Valid?}
    E -->|No| F[Return Error]
    E -->|Yes| G{Plan isPrepaid?}
    G -->|Yes| H[Error: Cannot create subscription<br/>for prepaid plan]
    G -->|No| I{Has cashfreePlanId?}
    I -->|No| J[Error: Plan missing Cashfree ID]
    I -->|Yes| K[Cancel Existing Subscriptions]

    K --> L[Generate Subscription ID]
    L --> M[Create Cashfree Subscription]
    M --> N[Get cf_subscription_id<br/>& subscription_session_id]

    N --> O[Create Subscription Record in DB:<br/>- userId<br/>- planId<br/>- cfSubscriptionId<br/>- status: INITIALIZED]

    O --> P[Return subscriptionSessionId to User]
    P --> Q[User Redirected to Cashfree]

    Q --> R[User Authorizes Subscription]
    R --> S[Cashfree Webhook:<br/>SUBSCRIPTION_ACTIVATED]

    S --> T[POST /api/v1/subscriptions/webhook]
    T --> U[SubscriptionService.process_webhook]

    U --> V{Event Type?}
    V -->|SUBSCRIPTION_ACTIVATED| W[Update Status: ACTIVE]
    V -->|SUBSCRIPTION_CHARGED| W
    V -->|SUBSCRIPTION_CANCELLED| X[Update Status: CANCELLED]
    V -->|SUBSCRIPTION_EXPIRED| Y[Update Status: EXPIRED]

    W --> Z[_activate_credits_for_subscription]
    X --> AA[End]
    Y --> AA

    Z --> AB[Get Plan Details]
    AB --> AC[Calculate Expiry Date<br/>now + durationInDays]
    AC --> AD[CreditService.create_credit]
    AD --> AE[Create Credit Record:<br/>- userId<br/>- type: PERIODIC<br/>- credits: plan.credits<br/>- expiresAt: calculated]
    AE --> AF[Create CreditTxn Record:<br/>- txnType: CREDIT<br/>- creditsUsed: plan.credits]

    AF --> AG[Set nextBillingDate<br/>now + 30 days]
    AG --> AH[Recurring Billing Cycle]

    AH --> AI[Cashfree Charges User<br/>Every Billing Cycle]
    AI --> AJ[SUBSCRIPTION_CHARGED Webhook]
    AJ --> Z

    AF --> AA
```

**Key Points:**
- Subscriptions create `PERIODIC` type credits
- First charge happens 2 days after subscription creation
- Credits are renewed on each billing cycle (monthly)
- Subscription can be cancelled via `POST /api/v1/subscriptions/{id}/cancel`
- Status transitions: INITIALIZED → ACTIVE → (CANCELLED/EXPIRED)

---

## Credit Management Flow

Credits are deducted when users consume services, following FIFO logic.

```mermaid
flowchart TD
    A[User Consumes Service] --> B[CreditService.deduct_credits]
    B --> C[Calculate Total Available Credits]

    C --> D[Get Active Credits<br/>Not Expired]
    D --> E[Group by Type:<br/>PERIODIC & ON_DEMAND]

    E --> F{Has PERIODIC Credits?}
    F -->|Yes| G[Deduct from PERIODIC First<br/>Sorted by Expiry Date]
    F -->|No| H[Skip to ON_DEMAND]

    G --> I{Remaining to Deduct?}
    I -->|Yes| H
    I -->|No| J[Success]

    H --> K{Has ON_DEMAND Credits?}
    K -->|Yes| L[Deduct from ON_DEMAND<br/>Sorted by Creation Date]
    K -->|No| M[Insufficient Credits]

    L --> N{Remaining to Deduct?}
    N -->|Yes| M
    N -->|No| O[Update Credit Records]

    O --> P[For Each Credit Used:]
    P --> Q[credit.credits -= deduct_amount]
    Q --> R{credit.credits <= 0?}
    R -->|Yes| S[credit.status = EXPIRED]
    R -->|No| T[Keep Active]

    S --> U[Create CreditTxn:<br/>- txnType: DEBIT<br/>- creditsUsed: amount]
    T --> U

    U --> V{More Credits Needed?}
    V -->|Yes| P
    V -->|No| J

    J --> W[Return Success]
    M --> X[Return Error:<br/>Insufficient Credits]
```

**Key Points:**
- **FIFO Logic**: PERIODIC credits are deducted first (by expiry), then ON_DEMAND (by creation)
- Each deduction creates a transaction record
- Credits are marked as EXPIRED when balance reaches 0
- Transaction records track all credit movements

---

## Scheduler Flow

A background scheduler runs daily to expire credits that have passed their expiry date.

```mermaid
flowchart TD
    A[Application Startup] --> B[main.py lifespan]
    B --> C[CreditScheduler.start]

    C --> D{CREDIT_EXPIRY_SCHEDULER_ENABLED?}
    D -->|No| E[Skip Scheduler]
    D -->|Yes| F[Initialize AsyncIOScheduler]

    F --> G[Add Cron Job:<br/>expire_credits_task<br/>Schedule: Daily at configured time<br/>Default: 02:00 UTC]

    G --> H[Scheduler Running]

    H --> I[Daily Trigger at Scheduled Time]
    I --> J[CreditScheduler.expire_credits_task]

    J --> K[CreditService.expire_credits]
    K --> L[Query Credits:<br/>expiresAt < now<br/>status = ACTIVE]

    L --> M{Found Expired Credits?}
    M -->|No| N[Log: No credits to expire]
    M -->|Yes| O[For Each Expired Credit:]

    O --> P[credit.status = EXPIRED]
    P --> Q{credit.credits > 0?}
    Q -->|Yes| R[Create CreditTxn:<br/>- txnType: DEBIT<br/>- creditsUsed: credit.credits<br/>- service: CREDIT_EXPIRED]
    Q -->|No| S[Skip Transaction]

    R --> T[Increment expired_count<br/>& total_expired_amount]
    S --> T

    T --> U{More Credits?}
    U -->|Yes| O
    U -->|No| V[Log Results:<br/>expired_count<br/>total_expired_amount]

    V --> W[Return Success]
    N --> W

    W --> X[Wait for Next Schedule]
    X --> I

    Y[Application Shutdown] --> Z[CreditScheduler.shutdown]
    Z --> AA[Stop Scheduler]
```

**Key Points:**
- Scheduler runs daily at configured time (default: 02:00 UTC)
- Can be disabled via `CREDIT_EXPIRY_SCHEDULER_ENABLED` env var
- Expires credits that have passed their `expiresAt` date
- Creates transaction records for expired credits
- Logs summary of expired credits

---

## Webhook Processing

Both payment and subscription webhooks are processed asynchronously.

### Payment Webhook Flow

```mermaid
flowchart TD
    A[Cashfree Payment Webhook] --> B[POST /api/v1/payments/webhook]
    B --> C[Extract & Verify Signature]
    C --> D{Signature Valid?}
    D -->|No| E[Return 401: Invalid Signature]
    D -->|Yes| F[PaymentService.process_webhook]

    F --> G[Extract order_id from webhook]
    G --> H[Find Payment by cfOrderId]
    H --> I{Payment Found?}
    I -->|No| J[Return Error]
    I -->|Yes| K{Already COMPLETED?}
    K -->|Yes| L[Return: Already Processed]
    K -->|No| M[Update Payment Status]

    M --> N{order_status = paid?}
    N -->|Yes| O[status = COMPLETED<br/>Set transactionTime<br/>Set paymentMethod]
    N -->|No| P[status = failed/expired/cancelled]

    O --> Q[_activate_credits_for_payment]
    P --> R[End]

    Q --> S[Create ON_DEMAND Credits]
    S --> R
```

### Subscription Webhook Flow

```mermaid
flowchart TD
    A[Cashfree Subscription Webhook] --> B[POST /api/v1/subscriptions/webhook]
    B --> C[Extract & Verify Signature]
    C --> D{Signature Valid?}
    D -->|No| E[Return 401: Invalid Signature]
    D -->|Yes| F[SubscriptionService.process_webhook]

    F --> G[Extract cf_subscription_id]
    G --> H[Find Subscription by cfSubscriptionId]
    H --> I{Subscription Found?}
    I -->|No| J[Return Error]
    I -->|Yes| K{Event Type?}

    K -->|SUBSCRIPTION_ACTIVATED| L[status = ACTIVE<br/>Set startDate<br/>Set nextBillingDate]
    K -->|SUBSCRIPTION_CHARGED| L
    K -->|SUBSCRIPTION_CANCELLED| M[status = CANCELLED]
    K -->|SUBSCRIPTION_EXPIRED| N[status = EXPIRED]

    L --> O[_activate_credits_for_subscription]
    M --> P[End]
    N --> P

    O --> Q[Create PERIODIC Credits]
    Q --> P
```

---

## Database Schema Overview

### Plans Collection
```javascript
{
  _id: ObjectId,
  name: String,
  cashfreePlanId: String | null,  // Required for subscriptions
  price: Integer,                  // In paise
  credits: Integer,
  durationInDays: Integer,
  isPrepaid: Boolean,               // true = Prepaid, false = Subscription
  isActive: Boolean,
  discount: Integer,                // In paise
  createdAt: DateTime,
  updatedAt: DateTime
}
```

### Payments Collection
```javascript
{
  _id: ObjectId,
  userId: ObjectId,
  planId: ObjectId | null,
  subscriptionId: ObjectId | null,
  cfPaymentId: String,
  cfOrderId: String,
  amount: Float,                    // In rupees
  status: String,                   // pending, completed, failed, cancelled, expired
  paymentMethod: String | null,
  transactionTime: DateTime | null,
  createdAt: DateTime,
  updatedAt: DateTime
}
```

### Subscriptions Collection
```javascript
{
  _id: ObjectId,
  userId: ObjectId,
  planId: ObjectId,
  cfSubscriptionId: String | null,
  status: String,                  // initialized, pending, active, cancelled, expired
  startDate: DateTime | null,
  nextBillingDate: DateTime | null,
  createdAt: DateTime,
  updatedAt: DateTime
}
```

### Credits Collection
```javascript
{
  _id: ObjectId,
  userId: ObjectId,
  type: String,                     // ON_DEMAND or PERIODIC
  credits: Integer,
  status: String,                  // ACTIVE or EXPIRED
  expiresAt: DateTime | null,
  createdAt: DateTime,
  updatedAt: DateTime
}
```

### Credit Transactions Collection
```javascript
{
  _id: ObjectId,
  userId: ObjectId,
  creditsId: ObjectId,
  txnType: String,                  // CREDIT or DEBIT
  creditsUsed: Integer,
  service: String | null,          // Service that triggered transaction
  createdAt: DateTime,
  updatedAt: DateTime
}
```

---

## Summary

### Prepaid Flow Summary
1. **Plan Selection**: User selects prepaid plan from collection
2. **Payment Creation**: Create Cashfree payment order
3. **Payment Processing**: User completes payment on Cashfree
4. **Webhook/Verification**: Payment status confirmed
5. **Credit Activation**: ON_DEMAND credits created immediately
6. **Expiration**: Credits expire based on `durationInDays` (handled by scheduler)

### Subscription Flow Summary
1. **Plan Selection**: User selects subscription plan from collection
2. **Subscription Creation**: Create Cashfree subscription
3. **Authorization**: User authorizes subscription on Cashfree
4. **Activation**: Subscription activated via webhook
5. **Credit Activation**: PERIODIC credits created on activation
6. **Recurring Billing**: Cashfree charges user monthly
7. **Credit Renewal**: New credits added on each charge (via webhook)
8. **Cancellation**: User can cancel subscription anytime

### Key Differences

| Aspect | Prepaid | Subscription |
|--------|---------|--------------|
| **Credit Type** | ON_DEMAND | PERIODIC |
| **Payment Frequency** | One-time | Recurring (monthly) |
| **Cashfree Plan ID** | Not required | Required |
| **Credit Expiry** | Based on plan duration | Based on plan duration (renewed each cycle) |
| **Deduction Priority** | Second priority (after PERIODIC) | First priority (before ON_DEMAND) |
| **Webhook Events** | Payment status updates | Subscription lifecycle events |

---

## API Endpoints Reference

### Plans
- `GET /api/v1/plans/` - List all plans
- `GET /api/v1/plans/{plan_id}` - Get plan details
- `POST /api/v1/plans/` - Create plan (admin)
- `PUT /api/v1/plans/{plan_id}` - Update plan (admin)

### Payments (Prepaid)
- `POST /api/v1/payments/create` - Create payment order
- `POST /api/v1/payments/verify/{order_id}` - Verify payment status
- `GET /api/payments/redirect/{order_id}` - Payment redirect page
- `POST /api/v1/payments/webhook` - Cashfree payment webhook

### Subscriptions
- `POST /api/v1/subscriptions/create` - Create subscription
- `GET /api/v1/subscriptions/me` - Get user subscriptions
- `POST /api/v1/subscriptions/{id}/cancel` - Cancel subscription
- `GET /api/subscriptions/redirect/{id}` - Subscription redirect page
- `POST /api/v1/subscriptions/webhook` - Cashfree subscription webhook

### Credits
- `GET /api/v1/credits/balance` - Get credit balance
- `GET /api/v1/credits/transactions` - Get transaction history

---

## Configuration

### Environment Variables
- `CREDIT_EXPIRY_SCHEDULER_ENABLED` - Enable/disable credit expiry scheduler (default: true)
- `CREDIT_EXPIRY_SCHEDULE_HOUR` - Hour for daily credit expiry (default: 2)
- `CREDIT_EXPIRY_SCHEDULE_MINUTE` - Minute for daily credit expiry (default: 0)
- `CASHFREE_APP_ID` - Cashfree application ID
- `CASHFREE_SECRET_KEY` - Cashfree secret key
- `CASHFREE_WEBHOOK_SECRET` - Webhook signature verification secret

---

*Last Updated: Based on codebase analysis*

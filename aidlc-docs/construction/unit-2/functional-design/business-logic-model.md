# Business Logic Model - Unit 2: Admin Backend

## Admin Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Admin Login Flow                              │
└─────────────────────────────────────────────────────────────────┘

    POST /admin/auth/login
    {username, password}
            │
            ▼
    ┌────────────────┐
    │ Check Env      │
    │ (dev/prod)     │
    └───────┬────────┘
            │
   ┌────────┴────────┐
   │                 │
  dev              prod
   │                 │
   ▼                 ▼
┌──────────┐  ┌────────────────┐
│ Check    │  │ Get Creds from │
│ admin/   │  │ Secrets Manager│
│ admin    │  └───────┬────────┘
└────┬─────┘          │
     │                ▼
     │         ┌────────────────┐
     │         │ Verify bcrypt  │
     │         │ password hash  │
     │         └───────┬────────┘
     │                 │
     └────────┬────────┘
              │
     ┌────────┴────────┐
     │                 │
   valid            invalid
     │                 │
     ▼                 ▼
┌──────────────┐  ┌──────────┐
│ Generate JWT │  │ HTTP 401 │
│ Session Token│  └──────────┘
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Return Token │
│ + Set Cookie │
└──────────────┘
```

### JWT Token Structure

```python
{
    "sub": "admin",           # Username
    "iat": 1703123456,        # Issued at
    "exp": 1703209856,        # Expires (24h)
    "type": "admin_session"
}
```

---

## User Management Flow

### Create User

```
POST /admin/users
{name, description}
        │
        ▼
┌────────────────┐
│ Validate Input │
│ - name required│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Create User    │
│ status=active  │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return User    │
│ (without keys) │
└────────────────┘
```

### Deactivate User

```
PATCH /admin/users/{id}
{status: "inactive"}
        │
        ▼
┌────────────────┐
│ Validate       │
│ Transition     │
│ active→inactive│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Update User    │
│ status=inactive│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Revoke ALL     │
│ Access Keys    │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Invalidate     │
│ All Caches     │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return Updated │
│ User           │
└────────────────┘
```

---

## Access Key Management Flow

### Issue Access Key

```
POST /admin/users/{user_id}/access-keys
        │
        ▼
┌────────────────┐
│ Validate User  │
│ exists & active│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Generate Key   │
│ ak_{random}    │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Compute HMAC   │
│ Hash           │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Store Key      │
│ (hash + prefix)│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return Full Key│
│ (ONCE ONLY)    │
└────────────────┘
```

### Rotate Access Key

```
POST /admin/access-keys/{id}/rotate
        │
        ▼
┌────────────────┐
│ Get Old Key    │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Set Old Key    │
│ status=rotating│
│ expires=now+5m │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Generate New   │
│ Key            │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Transfer       │
│ Bedrock Key    │
│ (if exists)    │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Schedule Old   │
│ Key Revocation │
│ (5 min)        │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return New Key │
│ (ONCE ONLY)    │
└────────────────┘
```

### Revoke Access Key

```
DELETE /admin/access-keys/{id}
        │
        ▼
┌────────────────┐
│ Set Key        │
│ status=revoked │
│ revoked_at=now │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Delete Bedrock │
│ Key (if exists)│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Invalidate     │
│ Caches         │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return Success │
└────────────────┘
```

---

## Bedrock Key Management Flow

### Register Bedrock Key

```
POST /admin/access-keys/{id}/bedrock-key
{bedrock_key}
        │
        ▼
┌────────────────┐
│ Validate       │
│ Access Key     │
│ exists & active│
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Encrypt Key    │
│ with KMS       │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Compute HMAC   │
│ Hash           │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Upsert to DB   │
│ (replace if    │
│  exists)       │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Invalidate     │
│ Key Cache      │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return Success │
│ (no key shown) │
└────────────────┘
```

---

## Usage Query Flow

```
GET /admin/usage?user_id=...&bucket=hour&start=...&end=...
        │
        ▼
┌────────────────┐
│ Parse Query    │
│ Parameters     │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Query          │
│ usage_aggregates│
│ table          │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Compute Totals │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Return         │
│ UsageResult    │
└────────────────┘
```

---

## API Response Formats

### Success Response

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req_..."
  }
}
```

### Error Response

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Name is required"
  },
  "meta": {
    "request_id": "req_..."
  }
}
```

### Paginated Response

```json
{
  "data": [ ... ],
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 20,
    "request_id": "req_..."
  }
}
```

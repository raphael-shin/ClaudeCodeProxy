# Integration Test Instructions

## Purpose

Test interactions between components to ensure the proxy system works end-to-end.

---

## Setup Integration Test Environment

### 1. Start All Services

```bash
cd /Users/jungseob/workspace/ClaudeCodeProxy
docker-compose up -d
```

### 2. Run Migrations

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### 3. Create Test Admin User

```bash
# Generate password hash
python -c "import hashlib; print(hashlib.sha256('testpass'.encode()).hexdigest())"

# Set in .env
PROXY_ADMIN_PASSWORD_HASH=<hash-from-above>
```

---

## Integration Test Scenarios

### Scenario 1: Admin Authentication Flow

**Description**: Test admin login and JWT token generation

```bash
# Login
curl -X POST http://localhost:8000/admin/auth/login \
  -u admin:testpass \
  -H "Content-Type: application/json"

# Expected: {"access_token": "...", "token_type": "bearer"}
```

### Scenario 2: User Management Flow

**Description**: Create user, issue access key, register Bedrock key

```bash
# Set token from login
TOKEN="<jwt-token>"

# Create user
curl -X POST http://localhost:8000/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test User", "description": "Integration test"}'

# Issue access key (use user_id from response)
curl -X POST http://localhost:8000/admin/users/<user_id>/access-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bedrock_region": "ap-northeast-2"}'

# Expected: Access key with raw_key in response
```

### Scenario 3: Proxy Request Flow (Plan Upstream)

**Description**: Test proxy routing to Plan upstream

```bash
ACCESS_KEY="<raw-access-key>"

curl -X POST "http://localhost:8000/ak/$ACCESS_KEY/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# Expected: Anthropic-compatible response or error
```

### Scenario 4: Proxy Fallback to Bedrock

**Description**: Test fallback when Plan fails (requires Bedrock key)

```bash
# Register Bedrock key first
curl -X POST http://localhost:8000/admin/access-keys/<key_id>/bedrock-key \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bedrock_api_key": "<your-bedrock-key>"}'

# Then make proxy request (will fallback if Plan fails)
```

### Scenario 5: Usage Tracking

**Description**: Verify usage is recorded after Bedrock requests

```bash
# After making Bedrock requests, check usage
curl "http://localhost:8000/admin/usage?bucket_type=hour" \
  -H "Authorization: Bearer $TOKEN"

# Expected: Usage buckets with token counts
```

### Scenario 6: Access Key Rotation

**Description**: Test key rotation with Bedrock key transfer

```bash
# Rotate key
curl -X POST http://localhost:8000/admin/access-keys/<key_id>/rotate \
  -H "Authorization: Bearer $TOKEN"

# Expected: New key with raw_key, old key in ROTATING status
# Bedrock key should be copied to new key
```

### Scenario 7: User Deactivation

**Description**: Test user deactivation revokes keys and invalidates cache

```bash
# Deactivate user
curl -X POST http://localhost:8000/admin/users/<user_id>/deactivate \
  -H "Authorization: Bearer $TOKEN"

# Try to use old access key
curl -X POST "http://localhost:8000/ak/$ACCESS_KEY/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-20250514", "max_tokens": 10, "messages": [{"role": "user", "content": "test"}]}'

# Expected: 404 Not Found
```

---

## Run Integration Tests

### Automated Integration Tests

```bash
cd backend
pytest tests/integration -v
```

### Manual Verification Checklist

- [ ] Admin login returns valid JWT
- [ ] User CRUD operations work
- [ ] Access key issuance returns raw key
- [ ] Proxy endpoint accepts requests
- [ ] Usage is recorded for Bedrock requests
- [ ] Key rotation transfers Bedrock key
- [ ] User deactivation invalidates keys

---

## Cleanup

```bash
docker-compose down -v  # Remove volumes to reset database
```

# Performance Test Instructions

## Purpose

Validate proxy performance under load to ensure it meets requirements.

---

## Performance Requirements

| Metric | Target |
|--------|--------|
| Response Time (P95) | < 500ms (excluding upstream latency) |
| Throughput | 100+ requests/second |
| Concurrent Users | 50+ simultaneous connections |
| Error Rate | < 1% |

---

## Setup Performance Test Environment

### 1. Install k6 (Load Testing Tool)

```bash
# macOS
brew install k6

# Linux
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

### 2. Start Services

```bash
docker-compose up -d
cd backend && uvicorn src.main:app --workers 4 --port 8000
```

### 3. Create Test Data

```bash
# Create test user and access key via admin API
# Save access key for load tests
```

---

## Load Test Script

Create `tests/performance/load-test.js`:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

const ACCESS_KEY = __ENV.ACCESS_KEY || 'test-key';
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  stages: [
    { duration: '30s', target: 10 },  // Ramp up
    { duration: '1m', target: 50 },   // Stay at 50 users
    { duration: '30s', target: 0 },   // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export default function () {
  const payload = JSON.stringify({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 10,
    messages: [{ role: 'user', content: 'Hello' }],
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const res = http.post(
    `${BASE_URL}/ak/${ACCESS_KEY}/v1/messages`,
    payload,
    params
  );

  check(res, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  sleep(0.1);
}
```

---

## Run Performance Tests

### 1. Basic Load Test

```bash
cd tests/performance
ACCESS_KEY=<your-access-key> k6 run load-test.js
```

### 2. Stress Test (Find Breaking Point)

```bash
k6 run --vus 100 --duration 2m load-test.js
```

### 3. Spike Test

```bash
k6 run --stage 10s:10,10s:100,10s:10 load-test.js
```

---

## Analyze Results

### Key Metrics to Monitor

- **http_req_duration**: Request latency (p50, p95, p99)
- **http_req_failed**: Error rate
- **http_reqs**: Total requests per second
- **vus**: Virtual users

### Expected Output

```
✓ status is 200 or 429
✓ response time < 500ms

http_req_duration..............: avg=45ms  min=10ms  med=40ms  max=200ms  p(90)=80ms  p(95)=100ms
http_req_failed................: 0.50%  ✓ 50   ✗ 9950
http_reqs......................: 10000  166.67/s
```

---

## Performance Optimization

If performance doesn't meet targets:

1. **High Latency**
   - Check database query performance
   - Add database indexes
   - Increase connection pool size
   - Enable response caching

2. **High Error Rate**
   - Check circuit breaker thresholds
   - Increase timeout values
   - Scale backend instances

3. **Low Throughput**
   - Increase uvicorn workers
   - Use async database operations
   - Optimize serialization

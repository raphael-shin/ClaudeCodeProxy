# Unit Test Execution

## Backend Unit Tests

### 1. Install Test Dependencies

```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run All Unit Tests

```bash
cd backend
pytest tests/unit -v
```

### 3. Run with Coverage

```bash
cd backend
pytest tests/unit --cov=src --cov-report=html --cov-report=term
```

### 4. Run Specific Test Modules

```bash
# Test proxy logic
pytest tests/unit/test_proxy_router.py -v

# Test authentication
pytest tests/unit/test_auth.py -v

# Test repositories
pytest tests/unit/test_repositories.py -v

# Test circuit breaker
pytest tests/unit/test_circuit_breaker.py -v
```

---

## Expected Test Coverage

| Module | Target Coverage |
|--------|-----------------|
| `proxy/router.py` | 90%+ |
| `proxy/auth.py` | 90%+ |
| `proxy/circuit_breaker.py` | 85%+ |
| `repositories/` | 80%+ |
| `api/` | 75%+ |

---

## Frontend Unit Tests

### 1. Run Frontend Tests

```bash
cd frontend
npm test
```

### 2. Run with Coverage

```bash
cd frontend
npm test -- --coverage
```

---

## Test Report Locations

- **Backend HTML Report**: `backend/htmlcov/index.html`
- **Backend Terminal Report**: Displayed after `pytest --cov`
- **Frontend Report**: `frontend/coverage/lcov-report/index.html`

---

## Fix Failing Tests

1. Review test output for failure details
2. Check test assertions vs actual behavior
3. Fix code or update test expectations
4. Rerun specific failing test: `pytest tests/unit/test_file.py::test_name -v`
5. Rerun all tests to ensure no regressions

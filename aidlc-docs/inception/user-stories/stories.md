# User Stories - ClaudeCodeProxy

## Story Organization
Stories are organized by **User Journey** following the natural workflow of each persona.

---

# Journey 1: Admin Onboarding & Authentication

## US-1.1: Admin Login
**As a** Platform Engineer  
**I want to** log into the Admin dashboard securely  
**So that** I can manage users and access keys

### Acceptance Criteria
```gherkin
Given I am on the Admin login page in development environment
When I enter admin/admin credentials
Then I am redirected to the Admin dashboard

Given I am on the Admin login page in production environment
When I enter credentials from Secrets Manager or OIDC
Then I am redirected to the Admin dashboard

Given I am on the Admin login page
When I enter invalid credentials
Then I see an error message "Invalid credentials"
And I remain on the login page
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-10

---

# Journey 2: Developer Onboarding

## US-2.1: Create New User
**As a** Platform Engineer  
**I want to** create a new user account for a developer  
**So that** they can be assigned access keys

### Acceptance Criteria
```gherkin
Given I am logged into the Admin dashboard
When I navigate to User Management and click "Create User"
And I enter a name, description, and set status to "active"
And I click "Save"
Then a new user is created with the provided details
And I see a success confirmation

Given I am creating a new user
When I submit without a required field (name)
Then I see a validation error
And the user is not created
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-6.1, FR-6.4

---

## US-2.2: Issue Access Key for User
**As a** Platform Engineer  
**I want to** generate an Access Key for a user  
**So that** they can authenticate with the proxy

### Acceptance Criteria
```gherkin
Given I am viewing a user's details
When I click "Generate Access Key"
Then a new Access Key is created with ak_ prefix
And the full Access Key is displayed ONCE
And I can copy the key to clipboard
And subsequent views show only prefix + masked value

Given a user already has active Access Keys
When I generate a new Access Key
Then the new key is added (user can have multiple keys)
And existing keys remain active
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-7.1, FR-7.4, FR-7.5

---

## US-2.3: Register Bedrock API Key
**As a** Platform Engineer  
**I want to** register a Bedrock API Key for an Access Key  
**So that** the proxy can call Bedrock when Plan limits are hit

### Acceptance Criteria
```gherkin
Given I am viewing an Access Key's details
When I click "Register Bedrock API Key"
And I enter the Bedrock Bearer Token
And I click "Save"
Then the key is encrypted and stored
And I see only the prefix + masked value
And the full key is never shown again
And Bedrock fallback is now enabled for this Access Key

Given an Access Key already has a Bedrock API Key
When I register a new Bedrock API Key
Then the old key is replaced
And the new key is encrypted and stored

Given an Access Key does NOT have a Bedrock API Key configured
When Plan upstream fails for requests using this key
Then the proxy returns HTTP 503 (Service Unavailable)
And Bedrock fallback is NOT attempted
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-8.1, FR-8.3, FR-8.4, FR-2.4

---

## US-2.4: Configure Bedrock Settings
**As a** Platform Engineer  
**I want to** configure Bedrock region and model for an Access Key  
**So that** I can customize the fallback behavior per user

### Acceptance Criteria
```gherkin
Given I am viewing an Access Key's details
When I set the Bedrock region to "ap-northeast-2"
And I set the Bedrock model to a specific model ID
And I click "Save"
Then the settings are saved for that Access Key

Given I don't specify region or model
When the Access Key is used
Then default values are applied (ap-northeast-2, claude-sonnet-4-5)
```

**Persona**: Platform Engineer (Alex)  
**Priority**: Medium  
**Related Requirements**: FR-5.1, FR-5.2

---

## US-2.5: Share Access Key with Developer
**As a** Platform Engineer  
**I want to** securely share the Access Key with the developer  
**So that** they can configure their Claude Code client

### Acceptance Criteria
```gherkin
Given I have just generated an Access Key
When I copy the full key (shown only once)
Then I can share it with the developer via secure channel
And the developer receives the complete ak_* key

Given the developer has received the Access Key
When they configure ANTHROPIC_BASE_URL
Then they set it to https://proxy.example.com/ak/{access_key}
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: TS-1, TS-3

---

# Journey 3: Developer Using Proxy

## US-3.1: Configure Claude Code with Proxy
**As a** Developer  
**I want to** configure Claude Code to use the proxy  
**So that** I can benefit from automatic Bedrock failover

### Acceptance Criteria
```gherkin
Given I have received my Access Key from the Platform Engineer
When I set ANTHROPIC_BASE_URL to https://proxy.example.com/ak/{my_access_key}
Then Claude Code uses the proxy for all API calls
And I don't need to change any other settings
```

**Persona**: Developer (Jordan)  
**Priority**: High  
**Related Requirements**: FR-1.4, TS-3

---

## US-3.2: Make API Request via Proxy
**As a** Developer  
**I want to** use Claude Code normally through the proxy  
**So that** my workflow is uninterrupted

### Acceptance Criteria
```gherkin
Given my Claude Code is configured with the proxy
When I make a request to Claude
Then the proxy forwards my request to Plan upstream
And I receive a response in Anthropic-compatible format
And the response time overhead is < 100ms

Given my Access Key is valid and active
When I make an API request
Then the request is processed successfully
```

**Persona**: Developer (Jordan)  
**Priority**: High  
**Related Requirements**: FR-1.1, FR-1.2, FR-1.3, NFR-1.1

---

## US-3.3: Automatic Failover to Bedrock
**As a** Developer  
**I want to** continue working when Plan limits are hit  
**So that** my productivity is not interrupted

### Acceptance Criteria
```gherkin
Given my Access Key has a Bedrock API Key configured
And Plan upstream returns HTTP 429 (rate limit)
When the proxy receives this error
Then the proxy automatically retries with Bedrock
And I receive a successful response
And I don't notice the failover occurred

Given my Access Key has a Bedrock API Key configured
And Plan upstream returns HTTP 5xx error
When the proxy detects this error
Then the proxy automatically retries with Bedrock
And the response format remains Anthropic-compatible

Given my Access Key does NOT have a Bedrock API Key configured
And Plan upstream fails
When the proxy cannot fallback to Bedrock
Then I receive HTTP 503 (Service Unavailable)
And the error message clearly indicates Bedrock fallback is not configured
And the response includes a request_id for debugging
```

**Persona**: Developer (Jordan)  
**Priority**: High  
**Related Requirements**: FR-2.1, FR-2.2, FR-2.3, FR-2.4

---

## US-3.4: Handle Invalid Access Key
**As a** Developer  
**I want to** receive a clear error when my Access Key is invalid  
**So that** I can troubleshoot configuration issues

### Acceptance Criteria
```gherkin
Given my Access Key does not exist in the system
When I make an API request
Then I receive HTTP 404 response
And the error is in Anthropic-compatible format

Given my Access Key has been revoked
When I make an API request
Then I receive HTTP 404 response
And I understand I need to contact the Platform Engineer
```

**Persona**: Developer (Jordan)  
**Priority**: Medium  
**Related Requirements**: FR-3.2, FR-3.3

---

## US-3.5: Handle Complete Failure
**As a** Developer  
**I want to** receive a meaningful error when both providers fail  
**So that** I can report the issue appropriately

### Acceptance Criteria
```gherkin
Given Plan upstream fails with 429 or 5xx
And Bedrock also fails
When the proxy cannot complete my request
Then I receive an Anthropic-compatible error response
And the response includes a request_id for debugging
And I can share this request_id with the Platform Engineer

Given Bedrock fails with authentication error
When the proxy classifies the failure
Then the internal classification is "bedrock_auth_error"
And the external response remains Anthropic-compatible

Given Bedrock fails with quota exceeded
When the proxy classifies the failure
Then the internal classification is "bedrock_quota_exceeded"
And the external response remains Anthropic-compatible

Given Bedrock is unavailable
When the proxy classifies the failure
Then the internal classification is "bedrock_unavailable"
And the external response remains Anthropic-compatible
```

**Persona**: Developer (Jordan)  
**Priority**: Medium  
**Related Requirements**: FR-2.6, FR-2.7

---

# Journey 4: Usage Monitoring

## US-4.1: View Usage Dashboard
**As a** Platform Engineer  
**I want to** view Bedrock usage statistics across all users  
**So that** I can monitor Bedrock API consumption

### Acceptance Criteria
```gherkin
Given I am logged into the Admin dashboard
When I navigate to the Usage Dashboard
Then I see aggregated Bedrock usage metrics only
And Plan usage is NOT displayed (tracked by Claude Code plans)
And I can filter by time period (minute/hour/day/week/month)
And I can select custom date ranges

Given I am viewing the Usage Dashboard
When I look at the metrics
Then I see input_tokens, output_tokens, cache tokens, total_tokens
And all metrics are for Bedrock provider only
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-9.3, FR-9.4, FR-9.5, FR-9.6

---

## US-4.2: View Usage by User
**As a** Platform Engineer  
**I want to** view Bedrock usage statistics for a specific user  
**So that** I can track individual Bedrock consumption

### Acceptance Criteria
```gherkin
Given I am on the Usage Dashboard
When I filter by a specific user
Then I see Bedrock usage metrics for only that user
And I can see breakdown by their Access Keys
And Plan usage is NOT included

Given I am viewing a user's details
When I click "View Usage"
Then I am taken to the Usage Dashboard filtered for that user's Bedrock usage
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-9.1, FR-9.2, FR-9.6

---

# Journey 5: Access Management

## US-5.1: View All Users
**As a** Platform Engineer  
**I want to** see a list of all users  
**So that** I can manage access across the organization

### Acceptance Criteria
```gherkin
Given I am logged into the Admin dashboard
When I navigate to User Management
Then I see a list of all users
And I can see each user's name, status, and creation date
And I can search/filter the list
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-6.2

---

## US-5.2: Deactivate User
**As a** Platform Engineer  
**I want to** deactivate a user account  
**So that** I can revoke their access when needed

### Acceptance Criteria
```gherkin
Given I am viewing a user's details
When I click "Deactivate User"
And I confirm the action
Then the user's status is set to "inactive"
And all their Access Keys are automatically revoked
And they can no longer use the proxy
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-6.3

---

## US-5.3: Revoke Access Key
**As a** Platform Engineer  
**I want to** revoke a specific Access Key  
**So that** I can disable access without affecting other keys

### Acceptance Criteria
```gherkin
Given I am viewing an Access Key's details
When I click "Revoke Key"
And I confirm the action
Then the Access Key status is set to "revoked"
And requests using this key return 404
And other Access Keys for the same user remain active
```

**Persona**: Platform Engineer (Alex)  
**Priority**: High  
**Related Requirements**: FR-7.2

---

## US-5.4: Rotate Access Key
**As a** Platform Engineer  
**I want to** rotate an Access Key  
**So that** I can maintain security without disrupting the user

### Acceptance Criteria
```gherkin
Given I am viewing an Access Key's details
When I click "Rotate Key"
Then a new Access Key is generated
And the old key is revoked
And the new key is displayed ONCE for copying
And Bedrock API Key association is preserved
```

**Persona**: Platform Engineer (Alex)  
**Priority**: Medium  
**Related Requirements**: FR-7.3

---

## US-5.5: Rotate Bedrock API Key
**As a** Platform Engineer  
**I want to** rotate a Bedrock API Key  
**So that** I can update credentials without creating a new Access Key

### Acceptance Criteria
```gherkin
Given I am viewing an Access Key with a registered Bedrock API Key
When I click "Rotate Bedrock Key"
And I enter the new Bedrock Bearer Token
And I click "Save"
Then the old key is replaced with the new encrypted key
And the Access Key continues to work with the new Bedrock key
```

**Persona**: Platform Engineer (Alex)  
**Priority**: Medium  
**Related Requirements**: FR-8.2

---

# Journey 6: System Health

## US-6.1: Check System Health
**As a** Platform Engineer  
**I want to** verify the proxy service is running  
**So that** I can monitor system availability

### Acceptance Criteria
```gherkin
Given the proxy service is running
When I call GET /health
Then I receive HTTP 200 OK
And I know the service is operational

Given the proxy service is not running
When I call GET /health
Then the request fails
And I know there is an issue to investigate
```

**Persona**: Platform Engineer (Alex)  
**Priority**: Medium  
**Related Requirements**: NFR-3.4

---

## US-6.2: Monitor Circuit Breaker Status
**As a** Platform Engineer  
**I want to** know when the circuit breaker is triggered  
**So that** I can understand system behavior

### Acceptance Criteria
```gherkin
Given Plan upstream has failed 3 times (429 or 5xx) in 1 minute for an Access Key
When the circuit breaker opens
Then requests for that Access Key go directly to Bedrock (if configured)
And this state is visible in CloudWatch metrics

Given Bedrock fails for an Access Key
When the failure is recorded
Then the circuit breaker state is NOT affected
And Plan upstream remains the primary target

Given the circuit breaker has been open for 30 minutes
When the reset time is reached
Then the circuit breaker closes
And requests attempt Plan upstream again
```

**Persona**: Platform Engineer (Alex)  
**Priority**: Medium  
**Related Requirements**: FR-4.2, FR-4.3, FR-4.4, FR-4.5, FR-4.6, FR-4.7

---

# Story Summary

| Journey | Story Count | Priority Distribution |
|---------|-------------|----------------------|
| Admin Onboarding | 1 | 1 High |
| Developer Onboarding | 5 | 4 High, 1 Medium |
| Developer Using Proxy | 5 | 3 High, 2 Medium |
| Usage Monitoring | 2 | 2 High |
| Access Management | 5 | 3 High, 2 Medium |
| System Health | 2 | 2 Medium |
| **Total** | **20** | **13 High, 7 Medium** |

---

# INVEST Criteria Compliance

All stories have been verified against INVEST criteria:

- **I**ndependent: Each story can be developed and delivered separately
- **N**egotiable: Stories describe outcomes, not implementation details
- **V**aluable: Each story delivers value to a specific persona
- **E**stimable: Stories are scoped for estimation
- **S**mall: Stories are medium granularity, completable in a sprint
- **T**estable: All stories have Given-When-Then acceptance criteria

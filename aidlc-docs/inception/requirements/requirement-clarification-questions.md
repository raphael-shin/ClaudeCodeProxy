# Requirements Clarification Questions

I detected an ambiguity in your responses that needs clarification:

---

## Ambiguity 1: Usage Data vs Raw Request Logs

Your response to Q13 ("None. It has already been logged in the Bedrock Invocation Log") indicates you don't want to store raw request logs.

However, the original requirements specify:
- **FR-9**: Admin Usage Dashboard with token usage queries by user/access key
- **DR-1**: Request logs storing tokens, latency, provider_used, etc.
- **DR-2**: Usage aggregations (rollup tables) for minute/hour/day/month

**The dashboard requires usage metrics to be stored in the database.**

### Clarification Question 1
What data should be stored for the usage dashboard?

A) Store minimal usage metrics only (user_id, access_key_id, provider_used, model, input_tokens, output_tokens, total_tokens, timestamp) - no raw request/response bodies
B) Store no usage data at all - remove the usage dashboard feature
C) Store full request logs including all metadata (latency_ms, status_code, error_type, etc.) but no request/response bodies
D) Other (please describe after [Answer]: tag below)

[Answer]: D Store minimal usage metrics only (user_id, access_key_id, provider_used, model, input_tokens, output_tokens, total_tokens, cache_read_input_tokens, cache_creation_input_tokens, timestamp) - no raw request/response bodies

---

## Clarification 2: Bedrock API Key Format

Your response to Q16 ("The Bedrock API key must be issued using the AWS SDK or CLI") needs clarification.

### Clarification Question 2
What credentials will users provide for Bedrock access?

A) AWS IAM Access Key ID + Secret Access Key pair (long-term credentials)
B) AWS IAM Role ARN for cross-account assume role
C) AWS STS temporary credentials (Access Key + Secret Key + Session Token)
D) Other (please describe after [Answer]: tag below)

[Answer]: D - Users provide a Bedrock API Key (Bearer Token) generated in Amazon Bedrock console or via Bedrock-specific API. Used as Authorization: Bearer <bedrock-api-key> when calling Bedrock Runtime APIs. This is a Bedrock-scoped bearer token, limited to supported Bedrock operations, managed separately from standard AWS IAM credentials.

---

**Instructions:**
Please answer these clarification questions so I can finalize the requirements and proceed.

# Using Custom LLM Provider (Company AI Farm)

This guide explains how to configure and use the custom LLM provider (AI Farm) instead of OpenAI.

## Quick Start

### Step 1: Get Credentials from Your Admin
Ask your company IT/AI team for these credentials:
- **Endpoint**: Base URL (e.g., `https://aoai-farm.bosch-temp.com`)
- **API Key**: Bearer token for authentication
- **Deployment ID**: Model deployment name (e.g., `gpt-4o-mini`, `gpt-5-nano-2025-08-07`)
- **API Version**: Azure format (e.g., `2025-04-01-preview`)
- **Subscription ID** (optional): For tracking/auditing

### Step 2: Update `.env` File

Edit `.env` and set:
```bash
# Use custom provider
LLM_PROVIDER=custom

# Custom provider credentials (from your admin)
CUSTOM_LLM_ENDPOINT=https://aoai-farm.bosch-temp.com
CUSTOM_LLM_API_KEY=your_api_key_here
CUSTOM_LLM_DEPLOYMENT_ID=gpt-4o-mini
CUSTOM_LLM_API_VERSION=2025-04-01-preview
CUSTOM_LLM_SUBSCRIPTION_ID=your_subscription_id  # optional
CUSTOM_LLM_TEMPERATURE=0
```

### Step 3: Run the Project

```bash
python3 main.py --appkey YOUR_APP_KEY
```

The system will automatically use your custom provider instead of OpenAI.

## Architecture

The custom LLM provider is implemented in `processor/custom_llm.py` using the `AiFarmLLM` class:

- **Protocol**: Azure OpenAI compatible REST API
- **Authentication**: Bearer token in `Authorization` header
- **Request Format**: Standard OpenAI chat completions format
- **Timeout**: 120 seconds (configurable in `config/hyperparams.json`)

### Request Flow

```
main.py
  ↓
batch_orchestrator.py → checks LLM_PROVIDER env var
  ↓
batch_context.py → initializes correct LLM
  ├─ If "openai": ChatOpenAI from langchain_openai
  └─ If "custom": AiFarmLLM from processor/custom_llm.py
  ↓
skill_executor.py → uses LLM to evaluate checks
```

## What Works with Custom Provider?

✅ **All features work identically**:
- All 4 form quality skills (component_quality, form_structure_quality, etc.)
- All back-office quality skills
- Prompt improvements (camelCase validation, comprehensive violation reporting)
- Excel output generation
- JSON output generation
- Retry logic with simplification

The prompt improvements are **provider-agnostic** - they work with any LLM that accepts standard chat completions format.

## Configuration Details

### Environment Variables

#### When using Custom Provider
| Variable | Required | Example | Notes |
|----------|----------|---------|-------|
| `LLM_PROVIDER` | ✓ | `custom` | Must be set to "custom" |
| `CUSTOM_LLM_ENDPOINT` | ✓ | `https://aoai-farm.bosch-temp.com` | Base URL without trailing slash |
| `CUSTOM_LLM_API_KEY` | ✓ | (your token) | Bearer token for authentication |
| `CUSTOM_LLM_DEPLOYMENT_ID` | ✓ | `gpt-4o-mini` | Deployment ID on your server |
| `CUSTOM_LLM_API_VERSION` | ✓ | `2025-04-01-preview` | Azure API version format |
| `CUSTOM_LLM_SUBSCRIPTION_ID` | ✗ | (optional) | For tracking only |
| `CUSTOM_LLM_TEMPERATURE` | ✗ | `0` | Default 0 (most deterministic) |

#### When using OpenAI (default)
| Variable | Required | Example |
|----------|----------|---------|
| `LLM_PROVIDER` | ✓ | `openai` |
| `OPENAI_API_KEY` | ✓ | `sk-proj-...` |
| `OPENAI_MODEL` | ✗ | `gpt-4o` |
| `OPENAI_TEMPERATURE` | ✗ | `0` |

### Model Timeout

Set in `config/hyperparams.json`:
```json
{
  "model": {
    "timeout": 120
  }
}
```

Default: 120 seconds. Note: AI Farm server-side timeout may be ~35-40 seconds.

## Prompt Improvements

All recent improvements work with custom provider:

### 1. **Check Separation**
- A1, A2, A3 checks are evaluated independently
- Clear instructions for each check's scope

### 2. **Valid camelCase Examples**
- Explicit list of VALID camelCase keys (files, noOfParent, createdBy, etc.)
- Prevents false positives

### 3. **Exact Key Extraction**
- LLM extracts key values EXACTLY from JSON
- Prevents hallucinations like `created_By` when actual key is `createdBy`

### 4. **Comprehensive Violation Reporting**
- All violations listed (not just first one)
- Each violation includes line number and suggestions

### 5. **Auto-Generated Detection** (A2)
- Correctly identifies numeric suffixes (testTextField1 → testTextField)

### 6. **Admin Field Prefixing** (A3)
- Validates ADMIN_ prefix in Admin panel labels

## Troubleshooting

### Issue: "Custom LLM initialized with endpoint=... but no response"

**Cause**: API key, endpoint, or deployment ID is incorrect.

**Solution**:
1. Verify credentials with your admin
2. Test endpoint connectivity:
   ```bash
   curl -H "Authorization: Bearer YOUR_KEY" https://your-endpoint/api/health
   ```
3. Check logs in `VSCODE_TARGET_SESSION_LOG`

### Issue: "Timeout after 120s"

**Cause**: AI Farm server is slow or network issues.

**Solutions**:
1. Increase timeout in `config/hyperparams.json`:
   ```json
   {"model": {"timeout": 180}}
   ```
2. Check network connectivity to endpoint
3. Try a smaller input file first

### Issue: "Unexpected response format"

**Cause**: API response structure doesn't match expected format.

**Solution**:
1. Verify API version is correct (ask admin)
2. Check if deployment uses different response structure
3. Update `custom_llm.py` if needed for custom response format

## Comparing Providers

| Aspect | OpenAI | Custom (AI Farm) |
|--------|--------|-----------------|
| **Cost** | Pay-per-token | Company-managed |
| **Latency** | ~1-5s | Depends on company infra |
| **Model** | Latest GPT-4, GPT-4o | Company's deployed model |
| **Internet** | Requires external API | Internal network only |
| **Privacy** | Data sent to OpenAI | Data stays internal |

## File Structure

Key files for custom provider:

```
processor/
  ├── batch_context.py        # LLM provider selection logic
  ├── custom_llm.py           # AiFarmLLM implementation
  ├── batch_orchestrator.py   # Routes to skill executor
  └── skill_executor.py       # Uses LLM for evaluation

agents/
  └── review_prompt.py        # Prompt building (provider-agnostic)

config/
  └── hyperparams.json        # Model configuration including timeout
```

## Recent Updates for Custom Provider

All prompt improvements made for accuracy now work with custom provider:

1. **A1 Check (camelCase)**
   - Added explicit valid examples: files, data, main, visitName, noOfParent, etc.
   - Added instruction to extract EXACT key values from JSON
   - Prevents reporting "created_By" when actual key is "createdBy"

2. **A2 Check (Auto-generated suffix)**
   - Correctly identifies testTextField1 vs testTextField
   - Works across all providers

3. **A3 Check (Admin prefix)**
   - Validates ADMIN_ prefix correctly
   - Independent from A1/A2

All changes are prompt-based, so they work identically with custom or OpenAI providers.

## Need Help?

1. Check logs: `VSCODE_TARGET_SESSION_LOG` environment variable
2. Verify credentials with IT/AI team
3. Test custom endpoint separately
4. Review custom_llm.py for implementation details
5. Check request/response formats match your AI Farm deployment


# Company Deployment Checklist

Use this checklist before deploying to your company's AI Farm environment.

## Pre-Deployment

### 1. Gather Credentials ☐
- [ ] Get **Endpoint URL** from IT/AI team (e.g., https://aoai-farm.bosch-temp.com)
- [ ] Get **API Key / Bearer Token** from IT/AI team
- [ ] Get **Deployment ID** (model name, e.g., gpt-4o-mini)
- [ ] Get **API Version** (e.g., 2025-04-01-preview)
- [ ] (Optional) Get **Subscription ID** for tracking

### 2. Setup Environment ☐
- [ ] Clone/download project to company machine
- [ ] Create Python virtual environment: `python -m venv .venv`
- [ ] Activate venv: `.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate` (Mac/Linux)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Copy `.env.example` to `.env`

### 3. Configure Custom Provider ☐
- [ ] Open `.env` file
- [ ] Set `LLM_PROVIDER=custom`
- [ ] Set `CUSTOM_LLM_ENDPOINT=<your_endpoint>`
- [ ] Set `CUSTOM_LLM_API_KEY=<your_api_key>`
- [ ] Set `CUSTOM_LLM_DEPLOYMENT_ID=<your_deployment_id>`
- [ ] Set `CUSTOM_LLM_API_VERSION=<your_api_version>`
- [ ] Set `CUSTOM_LLM_TEMPERATURE=0` (recommended)
- [ ] (Optional) Set `CUSTOM_LLM_SUBSCRIPTION_ID` if tracking needed

### 4. Security Check ☐
- [ ] Verify `.env` is in `.gitignore` (prevent accidental commits)
- [ ] Do NOT commit `.env` to version control
- [ ] Do NOT share `.env` file (contains API key)
- [ ] Store API key securely (password manager, vault, etc.)

### 5. Network Connectivity ☐
- [ ] Verify machine can reach endpoint URL
- [ ] Test with curl (if available):
  ```bash
  curl -H "Authorization: Bearer YOUR_KEY" https://your-endpoint/health
  ```
- [ ] Check firewall rules if behind corporate firewall
- [ ] Verify no VPN blocking required

## Testing

### 6. Initial Setup Test ☐
- [ ] Run: `python3 main.py --appkey TEST_KEY` with small test file
- [ ] Check logs for "Custom LLM initialized"
- [ ] Check logs for successful "Agent succeeded"
- [ ] Verify output JSON was created: `output/TEST_KEY/output_*.json`

### 7. Feature Validation ☐
- [ ] Test **A1 (camelCase)**: Should report ONLY keys with underscores/invalid chars
  - [ ] Verify: No false positives for `files`, `data`, `main`, `visitName`, `noOfParent`
  - [ ] Verify: Correctly reports `sys_attachment_auth`, `visit_name`, etc.
  
- [ ] Test **A2 (Numeric suffix)**: Should report ONLY keys ending in numbers
  - [ ] Verify: `testField1` reported as violation
  - [ ] Verify: `testField` (without number) reported as PASSED
  
- [ ] Test **A3 (Admin prefix)**: Should check ONLY Admin panel labels
  - [ ] Verify: Suggests `ADMIN_` prefix for admin components
  - [ ] Verify: Ignores non-admin components

### 8. Output Validation ☐
- [ ] JSON output created: `output/output_*.json`
- [ ] Excel output created: `output/output_*.xlsx`
- [ ] All checks present (A1, A2, A3 for component_quality)
- [ ] Status values correct (PASSED or FAILED)
- [ ] Feedback includes line numbers and suggestions

### 9. Performance Check ☐
- [ ] Measure time per file: ~3-10 seconds typical
- [ ] Check if timeout needed (default 120s in .env)
- [ ] Monitor memory usage
- [ ] Verify no timeout errors on normal-sized files

## Production Deployment

### 10. Production Setup ☐
- [ ] Copy configured project to production environment
- [ ] Re-verify `.env` is NOT committed to git
- [ ] Test with actual company data sample
- [ ] Review output quality and accuracy
- [ ] Verify all forms process without errors

### 11. Monitoring ☐
- [ ] Set up log file rotation (if long-running)
- [ ] Monitor for API errors in logs
- [ ] Track API usage/cost (if applicable)
- [ ] Document any issues for IT team

### 12. Documentation ☐
- [ ] Share CUSTOM_PROVIDER_SETUP.md with team
- [ ] Share DEPLOYMENT_SUMMARY.md with stakeholders
- [ ] Document any company-specific deviations
- [ ] Create runbook for operational team

## Troubleshooting

### If Tests Fail

**"Cannot reach endpoint"**
- [ ] Verify endpoint URL is correct
- [ ] Test with `curl` command
- [ ] Check firewall/proxy settings
- [ ] Try from different network

**"Authentication failed / 401 error"**
- [ ] Verify API key is correct
- [ ] Check if key has expired (ask IT team)
- [ ] Verify Bearer token format in .env
- [ ] Test with curl: `curl -H "Authorization: Bearer YOUR_KEY" ENDPOINT`

**"Deployment not found / 404 error"**
- [ ] Verify deployment ID is correct
- [ ] Check if deployment is active
- [ ] List available deployments with IT team
- [ ] Verify API version matches deployment

**"Timeout after 120s"**
- [ ] Check network latency to endpoint
- [ ] Try with smaller test file
- [ ] Increase timeout in config/hyperparams.json
- [ ] Check if server-side timeout is reached

**"A1 check still reports false positives"**
- [ ] Verify skill definition loaded: `skills/form_quality/component_quality.json`
- [ ] Restart Python to reload modules
- [ ] Check if prompt was overridden somewhere
- [ ] Compare with original test data

**"Different accuracy between OpenAI and Custom Provider"**
- [ ] This may be expected if models are different
- [ ] Can adjust prompts in agents/review_prompt.py if needed
- [ ] Ask IT team about model differences
- [ ] Compare outputs to determine if acceptable

## Support Resources

- **CUSTOM_PROVIDER_SETUP.md**: Detailed setup guide
- **DEPLOYMENT_SUMMARY.md**: What's been updated
- **README.md**: Project overview
- **processor/custom_llm.py**: Implementation details
- **processor/batch_context.py**: Provider selection logic

## Post-Deployment Sign-Off

- [ ] Initial testing passed
- [ ] Production data tested
- [ ] Documentation shared
- [ ] Team trained
- [ ] Go-live approved
- [ ] Monitoring in place

## Contact Information

For issues with:
- **Custom provider setup**: Contact your company's IT/AI team
- **Project code/features**: See documentation files
- **API compatibility**: Ask IT team about Azure OpenAI compatibility
- **Prompt accuracy**: Review CUSTOM_PROVIDER_SETUP.md troubleshooting section

---

**Deployment Date**: _________________

**Tested By**: _________________

**Approved By**: _________________

**Notes**: 

_________________________________________________________________

_________________________________________________________________


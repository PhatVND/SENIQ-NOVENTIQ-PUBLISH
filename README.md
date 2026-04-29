# SENIQ Security Copilot Agent – Deployment Guide

This guide walks you through the full setup after deploying the Azure infrastructure via Marketplace.

---

# 🚀 Step 1 – Grant Permissions (Required)

Before sending logs, ensure the ingestion app has permission to send data to the Data Collection Rule (DCR).

### Required:
- Azure AD App Registration (client_id, client_secret)
- Role assignment to allow log ingestion

Refer to Azure Monitor ingestion requirements:
- DCE (Data Collection Endpoint)
- DCR (Data Collection Rule)
- Log Analytics workspace

---

# 📥 Step 2 – Send Test Logs (Ingestion)

Use the provided ingestion script (e.g. `send_waf_logs.py`) and configure it using the deployment outputs:

### Required values:
- `dceLogsIngestionUri`
- `dcrImmutableId`
- `streamName`
- `tenantId`
- `clientId`
- `clientSecret`

---

### Example:
```python
endpoint = "<dceLogsIngestionUri>"
dcr_id = "<dcrImmutableId>"
stream = "<streamName>"
Validate ingestion:

Run this KQL query in Log Analytics:

CustomTable_CL
| take 10

✔ If data appears → ingestion is working

🤖 Step 3 – Deploy the Agent (YAML)

You can deploy the agent using the provided YAML:

👉 Download:
https://raw.githubusercontent.com/PhatVND/SENIQ-NOVENTIQ-PUBLISH/refs/heads/main/SENIQ_Plugin_v1/AgentManifest.yaml

Upload Agent to Security Copilot
Go to:
👉 https://securitycopilot.microsoft.com
Navigate to:
Build
Add plugin / Upload YAML
Upload the YAML file
Select:
✔ "Security Copilot plugin"
✔ Scope: Anyone in workspace

📌 The YAML must include:

Descriptor
SkillGroups
AgentDefinitions
🧠 Step 4 – Enable Required Tools

After uploading the agent:

Click Add tools
Enable the following 4 tools:
✅ Required tools:
SENIQ Parse & Triage v3
Resolve Parameter Hash
List Sentinel Workspaces
Execute KQL

👉 These tools are required for:

Querying Sentinel
Running KQL queries
Processing alerts
Agent orchestration

📌 Tools must be enabled manually after upload:

Plugins appear under "Custom" and must be toggled on to be usable

🧪 Step 5 – Test the Agent
Go to Chat / Prompt
Select your agent
Run a test prompt:
Investigate recent WAF activity
Expected behavior:
Agent queries CustomTable_CL
Processes logs
Returns analysis
⚠️ Troubleshooting
❌ No data returned
Check ingestion step
Verify DCR + DCE config
❌ Agent not visible
YAML upload failed
Missing AgentDefinitions
❌ Tools not working
Tools not enabled
Missing RequiredSkillsets
🎯 Final Flow
Deploy → Send Logs → Upload YAML → Enable Tools → Use Agent
💡 Notes
This solution is NOT SaaS
All resources run in the customer's Azure environment
The agent is deployed manually via YAML
✅ You're Done

Once all steps are complete:

Logs flow into Sentinel
Agent can query + analyze data
Security Copilot becomes fully operational
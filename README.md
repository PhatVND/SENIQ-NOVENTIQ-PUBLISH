# SENIQ Security Copilot Agent – Deployment Guide

This guide walks you through the full setup after deploying the Azure infrastructure via Marketplace.

---

## 🚀 Step 1 – Grant Permissions (Required)

Before sending logs, ensure the ingestion app has permission to send data to the Data Collection Rule (DCR).

### Required:

* Azure AD App Registration (`client_id`, `client_secret`)
* Role assignment for log ingestion

### Required Azure components:

* Data Collection Endpoint (DCE)
* Data Collection Rule (DCR)
* Log Analytics Workspace

📌 These components form the ingestion pipeline for Azure Monitor logs ([Fluent Bit Documentation][1])

---

## 📥 Step 2 – Send Test Logs (Ingestion)

Use the provided ingestion script (e.g. `send_waf_logs.py`) and configure it using deployment outputs.

### Required values:

* `dceLogsIngestionUri`
* `dcrImmutableId`
* `streamName`
* `tenantId`
* `clientId`
* `clientSecret`

### Example:

```python
endpoint = "<dceLogsIngestionUri>"
dcr_id = "<dcrImmutableId>"
stream = "<streamName>"
```

---

### Validate ingestion

Run this KQL query in Log Analytics:

```kql
CustomTable_CL
| take 10
```

✔ If data appears → ingestion is working

---

## 🤖 Step 3 – Deploy the Agent (YAML)

Download the agent YAML:

👉 https://raw.githubusercontent.com/PhatVND/SENIQ-NOVENTIQ-PUBLISH/refs/heads/main/SENIQ_Plugin_v1/AgentManifest.yaml

---

### Upload to Security Copilot

1. Go to:
   👉 https://securitycopilot.microsoft.com

2. Navigate to:

* **Build**
* **Add plugin / Upload YAML**

3. Upload the YAML file

4. Select:

* ✔ Security Copilot plugin
* ✔ Scope: *Anyone in workspace*

---

📌 The YAML must include:

* Descriptor
* SkillGroups
* AgentDefinitions

---

## 🧠 Step 4 – Enable Required Tools

After uploading the agent:

1. Click **Add tools**
2. Enable the following tools:

### ✅ Required tools:

* SENIQ Parse & Triage v3
* Resolve Parameter Hash
* List Sentinel Workspaces
* Execute KQL

👉 These tools enable:

* Querying Sentinel data
* Running KQL queries
* Processing alerts
* Agent orchestration

📌 Tools must be enabled manually after upload.

---

---

## ⚠️ Troubleshooting

### ❌ No data returned

* Verify ingestion step
* Check DCR / DCE configuration

### ❌ Agent not visible

* YAML upload failed
* Missing required fields

### ❌ Tools not working

* Tools not enabled
* Missing RequiredSkillsets

---

## 🎯 Final Flow

```
Deploy → Send Logs → Upload YAML → Enable Tools → Use Agent
```

---

## 💡 Notes
* All resources run in the **customer’s Azure environment**
* The agent is deployed manually via YAML

---

## ✅ You're Done

Once completed:

* Logs flow into Sentinel
* Agent can query and analyze data
* Security Copilot becomes operational


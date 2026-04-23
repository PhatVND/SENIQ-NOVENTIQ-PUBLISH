# Azure Infrastructure Deployment Guide

This guide explains how to deploy the required Data Collection Endpoint (DCE), Data Collection Rule (DCR), and Log Analytics Custom Table using the Azure Portal. 

By following this guide, you will provision the necessary resources and collect the configuration values required to run the `send_waf_logs.py` script.

---

## Prerequisites
- **Azure CLI** installed and authenticated (`az login`) OR access to the **Azure Portal**.
- A target **Resource Group**.
- An existing **Log Analytics Workspace (LAW)**. You will need its full Resource ID.

---

## Step 1: Deploy Data Collection Endpoint (DCE)

The DCE acts as the entry point for logs. We will create it directly through the Azure Portal.

1. In the Azure Portal, search for and select **Data Collection Endpoints**.
2. Click **+ Create** to create a new endpoint.
3. Select your **Subscription** and **Resource Group**.
4. Enter an **Endpoint name** (e.g., `waf-logs-dce`) and select your desired **Region**.
5. Click **Review + create** and then **Create**.
6. Once deployed, navigate to the newly created Data Collection Endpoint. From the **Overview** page, copy its **Logs Ingestion URI**. (Optional: You can also copy its **Resource ID** by clicking **JSON View** on the top right, if needed for other configurations).

### 📝 Information to record from Step 1:
* Copy the **Logs Ingestion URI** from the DCE Overview page. This is your `DCE_ENDPOINT` for the Python script.

---

## Step 2: Create Custom Table and Data Collection Rule (DCR)

You can create both the destination custom table (`CustomTable_CL`) and the Data Collection Rule (DCR) simultaneously via the Azure Portal wizard, which ensures the schema is mapped correctly.

1. Go to your **Log Analytics Workspace** in the Azure Portal.
2. Select **Tables** > **+ Create** > **New custom log (DCR-based)**.
3. **Table Name**: Enter `CustomTable` (Azure appends `_CL`).
4. **Data Collection Rule**: Click the **Create a new data collection rule** link. Give it a name (e.g., `waf-logs-dcr`) and select the Data Collection Endpoint you created in Step 1 (`waf-logs-dce`) from the dropdown.
5. **Schema**: Click **Browse for files** and upload the example schema file provided in this repository:
   👉 `Azure-Infra-ARM/CustomTable_schema/CustomTable.json`
   *(Azure will parse this file and automatically generate the exact columns needed for the WAF logs).*
6. Click **Next** to review the Transformation schema (you can leave the transformation query as `source`), then click **Create** to deploy both the Table and the DCR.

### 📝 Information to record from Step 2:
Once created, search for **Data Collection Rules** in the portal, select the rule you just created (`waf-logs-dcr`), and go to the **Overview** page:
* Copy the **Immutable Id** (e.g., `dcr-xxxxxx`). This is your `DCR_IMMUTABLE_ID` for the Python script.
* The **Stream Name** will be exactly `Custom-CustomTable_CL`. This is your `STREAM_NAME`.

---

## Step 3: Grant "Monitoring Metrics Publisher" Role

For your Python script to push logs, the App Registration (Service Principal) must be granted the **Monitoring Metrics Publisher** role on the DCR.

### Option A: Using Azure CLI
1. Retrieve the Object ID of your Service Principal (App Registration):
   ```bash
   az ad sp list --display-name "<Your-App-Name>" --query "[0].id" -o tsv
   ```
2. Retrieve the Resource ID of your DCR:
   ```bash
   az monitor data-collection rule show \
     --resource-group <Your-Resource-Group> \
     --name "waf-logs-dcr" \
     --query id -o tsv
   ```
3. Assign the role:
   ```bash
   az role assignment create \
     --assignee <Service-Principal-Object-ID> \
     --role "Monitoring Metrics Publisher" \
     --scope <DCR-Resource-ID>
   ```

### Option B: Using Azure Portal
1. Navigate to the **Data Collection Rule** (`waf-logs-dcr`) you created in Step 2.
2. Select **Access control (IAM)** on the left menu.
3. Click **+ Add** > **Add role assignment**.
4. Search for and select the **Monitoring Metrics Publisher** role. Click **Next**.
5. Select **User, group, or service principal**.
6. Click **+ Select members**, search for your App Registration (e.g., `WAF-Log-Ingestion-App`), select it, and click **Review + assign**.

---

## Summary Checklist for `send_waf_logs.py`

Before executing your script, ensure you have gathered the following configuration values:

- [ ] `TENANT_ID`: Directory ID of your App Registration.
- [ ] `CLIENT_ID`: Application ID of your App Registration.
- [ ] `CLIENT_SECRET`: Secret Value of your App Registration.
- [ ] `DCE_ENDPOINT`: The **Logs Ingestion URI** (from Step 1).
- [ ] `DCR_IMMUTABLE_ID`: The **Immutable ID** (`dcr-...`) (from Step 2).
- [ ] `STREAM_NAME`: `Custom-CustomTable_CL` (from Step 2).

Once these values are populated in `send_waf_logs.py`, you can test it:
```bash
python send_waf_logs.py
```

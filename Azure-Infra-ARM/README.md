# Azure Infrastructure Deployment Guide using ARM Templates

This guide explains how to deploy the required Data Collection Endpoint (DCE), Data Collection Rule (DCR), and Log Analytics Custom Table using the provided ARM templates and schema files in the `Azure-Infra-ARM` directory. 

By following this guide, you will provision the necessary resources (via Azure CLI or Azure Portal) and collect the configuration values required to run the `send_waf_logs.py` script.

---

## Prerequisites
- **Azure CLI** installed and authenticated (`az login`) OR access to the **Azure Portal**.
- A target **Resource Group**.
- An existing **Log Analytics Workspace (LAW)**. You will need its full Resource ID.

---

## Step 1: Deploy Data Collection Endpoint (DCE)

The DCE acts as the entry point for logs. We will deploy it using the `DCEtemplate.json`.

### Option A: Using Azure CLI
1. Run the following Azure CLI command to deploy the DCE:
   ```bash
   az deployment group create \
     --resource-group <Your-Resource-Group> \
     --template-file Azure-Infra-ARM/DCE/DCEtemplate.json \
     --parameters dceName="waf-logs-dce"
   ```
2. Once deployed, get the **Logs Ingestion URI** of the DCE and its **Resource ID**:
   ```bash
   az monitor data-collection endpoint show \
     --resource-group <Your-Resource-Group> \
     --name "waf-logs-dce" \
     --query "{LogsIngestionURI:logsIngestion.endpoint, ResourceId:id}" -o table
   ```

### Option B: Using Azure Portal ("Deploy a custom template")
1. In the Azure Portal, search for and select **Deploy a custom template**.
2. Click **Build your own template in the editor**.
3. Click **Load file** and upload `Azure-Infra-ARM/DCE/DCEtemplate.json`. Click **Save**.
4. Select your Subscription, Resource group, and Location. Enter a name for `Dce Name` (e.g., `waf-logs-dce`).
5. Click **Review + create** and then **Create**.
6. Once deployed, navigate to the newly created Data Collection Endpoint. From the **Overview** page, click **JSON View** (top right) to copy its **Resource ID**.

### 📝 Information to record from Step 1:
* Copy the **Logs Ingestion URI** from the DCE Overview page (or CLI output). This is your `DCE_ENDPOINT` for the Python script.
* Copy the **Resource ID** of the DCE. You will need this for Step 3.

---

## Step 2: Create the Custom Table in Log Analytics Workspace

Before creating the DCR, the destination custom table (`CustomTable_CL`) **must exist** in your Log Analytics Workspace. You can create this table quickly via the Azure Portal using the provided sample JSON.

1. Go to your **Log Analytics Workspace** in the Azure Portal.
2. Select **Tables** > **+ Create** > **New custom log (DCR-based)**.
3. **Table Name**: Enter `CustomTable` (Azure appends `_CL`).
4. **Data Collection Rule**: Select the DCE you just created (`waf-logs-dce`) and create a temporary DCR here, OR skip and use the API. *(It is highly recommended to upload `Azure-Infra-ARM/CustomTable_schema/CustomTable.json` here so Azure auto-generates the table schema perfectly).*
5. Click **Create**.

---

## Step 3: Deploy Data Collection Rule (DCR)

Now deploy the DCR using `DCRtemplate.json`. This template explicitly defines the schema columns for `Custom-CustomTable_CL` and routes data to your Log Analytics Workspace.

### Option A: Using Azure CLI
1. Run the following Azure CLI command. Replace the `<DCE-Resource-ID>` and `<LAW-Resource-ID>` with your actual IDs:
   ```bash
   az deployment group create \
     --resource-group <Your-Resource-Group> \
     --template-file Azure-Infra-ARM/DCR/DCRtemplate.json \
     --parameters \
       dataCollectionRules_Custom_DCR_name="waf-logs-dcr" \
       dataCollectionEndpoints_Logstash_DCE_externalid="<DCE-Resource-ID>" \
       workspaces_sentinel_law_externalid="<LAW-Resource-ID>"
   ```
2. Once deployed, get the **Immutable ID** of the newly created DCR:
   ```bash
   az monitor data-collection rule show \
     --resource-group <Your-Resource-Group> \
     --name "waf-logs-dcr" \
     --query immutableId -o tsv
   ```

### Option B: Using Azure Portal ("Deploy a custom template")
1. In the Azure Portal, search for and select **Deploy a custom template**.
2. Click **Build your own template in the editor**.
3. Click **Load file** and upload `Azure-Infra-ARM/DCR/DCRtemplate.json`. Click **Save**.
4. Select your Subscription and Resource group.
5. Fill in the parameters:
   - **Data Collection Rules Custom DCR Name**: e.g., `waf-logs-dcr`
   - **Data Collection Endpoints Logstash DCE Externalid**: Paste the **Resource ID of the DCE** you created in Step 1.
   - **Workspaces Sentinel Law Externalid**: Paste the **Resource ID of your Log Analytics Workspace**.
6. Click **Review + create** and then **Create**.
7. Once deployed, navigate to the newly created Data Collection Rule. 

### 📝 Information to record from Step 3:
* From the DCR Overview page (or CLI output), copy the **Immutable Id** (e.g., `dcr-xxxxxx`). This is your `DCR_IMMUTABLE_ID` for the Python script.
* The **Stream Name** is hardcoded in the ARM template as `Custom-CustomTable_CL`. This is your `STREAM_NAME`.

---

## Step 4: Grant "Monitoring Metrics Publisher" Role

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
1. Navigate to the **Data Collection Rule** (`waf-logs-dcr`) you created in Step 3.
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
- [ ] `DCR_IMMUTABLE_ID`: The **Immutable ID** (`dcr-...`) (from Step 3).
- [ ] `STREAM_NAME`: `Custom-CustomTable_CL` (Defined in the DCR ARM template).

Once these values are populated in `send_waf_logs.py`, you can test it:
```bash
python send_waf_logs.py
```

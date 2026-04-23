# Guide to Configuring and Running `send_waf_logs.py`

The `send_waf_logs.py` script uses the **Azure Monitor Logs Ingestion API** to push WAF log data from a local CSV file to a custom table (`CustomTable_CL`) in a Log Analytics Workspace / Microsoft Sentinel via a **Data Collection Rule (DCR)** and a **Data Collection Endpoint (DCE)**.

Below are the detailed steps to create an App Registration, create a Secret, grant permissions, configure, and run the script.

---

## Step 1: Create an App Registration (Service Principal) in Microsoft Entra ID

1. Log in to the **Azure Portal** (https://portal.azure.com).
2. Search for and select **Microsoft Entra ID** (formerly Azure Active Directory).
3. On the left menu, select **App registrations** > **New registration**.
4. Fill in the details:
   * **Name**: The application name (e.g., `WAF-Log-Ingestion-App`).
   * **Supported account types**: Select *Accounts in this organizational directory only*.
5. Click **Register**.
6. After creation, on the App's **Overview** page, save the following 2 values to configure the script later:
   * **Application (client) ID** (`CLIENT_ID`)
   * **Directory (tenant) ID** (`TENANT_ID`)

---

## Step 2: Create a Client Secret for the App

1. In the management page of the newly created App Registration, look at the left menu and select **Certificates & secrets**.
2. Switch to the **Client secrets** tab and click **+ New client secret**.
3. Enter a **Description** (e.g., `Key for WAF Script`) and choose an appropriate **Expires** duration.
4. Click **Add**.
5. **EXTREMELY IMPORTANT**: Immediately after the secret is created, copy the value in the **Value** column (this is your `CLIENT_SECRET`). Azure will hide this value if you reload the page.

---

## Step 3: Grant Permissions to the App on the Data Collection Rule (DCR)

For the App Registration to have permission to push log data via the DCR, it **must be assigned the "Monitoring Metrics Publisher" role** directly on the DCR resource (or the Resource Group containing the DCR).

1. In the Azure Portal, search for and open **Data Collection Rules**.
2. Select the DCR you created for receiving logs (e.g., `waf-ingestion-dcr`).
3. On the DCR's left menu, select **Access control (IAM)**.
4. Click **+ Add** > **Add role assignment**.
5. In the list of roles, search for and select the **Monitoring Metrics Publisher** role. Then click **Next**.
6. Under the *Assign access to* section, select **User, group, or service principal**.
7. Click **+ Select members**, search for the name of the App Registration you created in Step 1 (`WAF-Log-Ingestion-App`), and select it.
8. Click **Select** > **Review + assign** > **Review + assign** again to complete the role assignment.

*(Note: It may take about 1-5 minutes for this permission to take effect across the Azure system after assignment).*

---

## Step 4: Update the Configuration in `send_waf_logs.py`

Open the `send_waf_logs.py` file and update the parameters in the `CONFIGURATION` section using the values you gathered:

```python
# --- Azure AD / Entra ID ---
TENANT_ID     = "<Replace with Directory (tenant) ID>"
CLIENT_ID     = "<Replace with Application (client) ID>"
CLIENT_SECRET = "<Replace with Client Secret Value>"

# --- Data Collection Endpoint (DCE) ---
DCE_ENDPOINT = "https://<Your DCE Name>.ingest.monitor.azure.com"

# --- Data Collection Rule (DCR) ---
DCR_IMMUTABLE_ID = "dcr-<The ID string from the DCR Overview page>"
STREAM_NAME      = "Custom-CustomTable_CL" # Ensure the stream name starts with Custom-

# --- Input Data ---
CSV_FILE = "azure_waf.csv" # Path to your csv file
```

---

## Step 5: Run the Script

1. **Install required libraries** (if you haven't already):
   Open a terminal/command prompt and run the following command to install the Python libraries:
   ```bash
   pip install pandas requests
   ```

2. **Run the script in TEST mode (Sends only the first 3 rows)**:
   This mode helps you verify whether the Entra ID authentication and DCR schema configuration are correct without pushing the entire file.
   ```bash
   python send_waf_logs.py
   ```
   If the terminal outputs `TEST SUCCESSFUL! HTTP 204` (or 200), it means the connection and schema are correct.

3. **Run the script to push all data**:
   After a successful test, run the following command to send all logs from the CSV:
   ```bash
   python send_waf_logs.py --all
   ```
   The script will automatically split the CSV file into smaller batches (under 1MB/batch) and push them sequentially to Sentinel.

---

### Troubleshooting Common Errors
* **Error 401 Unauthorized**: The `CLIENT_ID`, `TENANT_ID`, or `CLIENT_SECRET` might be incorrect.
* **Error 403 Forbidden**: The App has not been granted the **Monitoring Metrics Publisher** role on the DCR, or the permission hasn't synced yet (wait a few minutes and try again).
* **Error 400 Bad Request / 404 Not Found**: The DCE endpoint might be wrong, the `DCR_IMMUTABLE_ID` or `STREAM_NAME` might be configured incorrectly, or the data schema does not match the table structure you defined in the DCR.

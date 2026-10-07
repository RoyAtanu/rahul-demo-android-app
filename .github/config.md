# Android Demo Application --- CI/CD and pCloudy Appium Test Configuration

## 1. Project Overview

This document explains the Android demo application testing workflow
from the beginning, including the GitHub Actions pipeline, Firebase App
Distribution APK retrieval, pCloudy device selection, APK upload, Appium
lifecycle automation, and result collection.

**Application package:** `com.epam.mobitru`\
**APK filename used in the pipeline:** `firebase-app.apk`\
**Appium endpoint:** `https://device.pcloudy.com/appiumcloud/wd/hub`\
**Python version in CI:** `3.12`\
**Appium version requested in capabilities:** `3.1.1`\
**Target platform:** Android\
**Performance data:** Enabled by default

The workflow uses GitHub Actions jobs to separate the main operations.
Files needed by later jobs are transferred using GitHub Actions
artifacts.

## 2. High-Level Workflow

1.  **Checkout Repository** --- check out the source code.
2.  **Firebase Authentication and APK Download** --- authenticate to
    Google Cloud/Firebase, obtain an access token, find the latest
    Firebase App Distribution release, download its APK, and upload the
    APK as an artifact.
3.  **Verify APK** --- download the artifact and check that the APK
    exists and is not empty.
4.  **pCloudy Authentication** --- authenticate to pCloudy and verify
    that an API token can be extracted.
5.  **Fetch Target Devices** --- request currently available Android
    devices and validate the enabled device list in
    `config/devices.json`.
6.  **Upload APK to pCloudy** --- upload the downloaded APK and capture
    the filename returned by pCloudy.
7.  **Execute Tests on Devices** --- set up Python, install
    dependencies, run the lifecycle test sequentially on enabled
    devices, collect summaries, and upload results as an artifact.

> GitHub Actions creates a separate runner for each job. The workflow
> therefore passes the APK and device snapshot through artifacts.
> Credentials are stored in GitHub Secrets rather than hard-coded in the
> workflow.

## 3. Repository Files

The workflow expects the following project files:

  -----------------------------------------------------------------------------
  File                                      Purpose
  ----------------------------------------- -----------------------------------
  `.github/workflows/<workflow-file>.yml`   Defines the GitHub Actions workflow
                                            and its jobs.

  `config/devices.json`                     Lists target devices and whether
                                            each device is enabled.

  `automation/test_app_lifecycle.py`        Appium test that checks the
                                            application's lifecycle.

  `requirements.txt`                        Python dependencies installed by
                                            the workflow.
  -----------------------------------------------------------------------------

### Example device configuration

Use the exact device names returned by pCloudy. The following is an
example format; device names must match the devices configured for the
actual run.

``` json
{
  "devices": [
    {
      "name": "Samsung_GalaxyS25_Android_15.0.0_d9af3",
      "enabled": true
    },
    {
      "name": "Samsung_GalaxyS22_Android_14.0.0_09b8b",
      "enabled": true
    }
  ]
}
```

A device with `"enabled": false` is not included in the test loop. At
least one device must be enabled.

## 4. GitHub Repository Secrets

Configure these values under **GitHub repository → Settings → Secrets
and variables → Actions → New repository secret**.

  -----------------------------------------------------------------------
  Secret                              Purpose
  ----------------------------------- -----------------------------------
  `FIREBASE_SERVICE_ACCOUNT`          Google service-account JSON used by
                                      the Google GitHub authentication
                                      action.

  `FIREBASE_PROJECT_NUMBER`           Firebase/Google Cloud project
                                      number used in the release API URL.

  `FIREBASE_APP_ID`                   Firebase Android application ID,
                                      expected to contain `:android:`.

  `PCLOUDY_EMAIL`                     pCloudy account email used for API
                                      authentication.

  `PCLOUDY_ACCESS_KEY`                pCloudy API access key.
  -----------------------------------------------------------------------

Never commit credentials, access tokens, service-account JSON, or API
keys to the repository. The workflow masks access tokens in its logs.

## 5. Workflow Environment Variables

The workflow defines these shared variables:

``` yaml
env:
  APP_PACKAGE: com.epam.mobitru
  PCLOUDY_DURATION: "30"
  PCLOUDY_APPIUM_URL: https://device.pcloudy.com/appiumcloud/wd/hub
  PCLOUDY_ENABLE_PERFORMANCE_DATA: "true"
  PYTHONUNBUFFERED: "1"
```

The test file also supports these environment variables:

-   `APP_PACKAGE` --- application package; defaults to
    `com.epam.mobitru`.
-   `PCLOUDY_DEVICE` --- full pCloudy device name for the current test.
-   `RID` --- optional pCloudy reservation ID. If supplied, it is used
    instead of the device name.
-   `PCLOUDY_EMAIL` --- pCloudy email.
-   `PCLOUDY_ACCESS_KEY` --- pCloudy API key.
-   `PCLOUDY_APP_NAME` --- uploaded pCloudy application filename;
    defaults to `firebase-app.apk`.
-   `PCLOUDY_ENABLE_PERFORMANCE_DATA` --- controls the test's
    performance-data flag; defaults to `true`.

## 6. Step-by-Step Commands and Operations

The following commands describe the main commands executed by the
workflow. In CI, secrets and tokens are passed through environment
variables; do not paste real credentials into a terminal or
documentation.

### Step 1 --- Check out the repository

GitHub Actions uses:

``` yaml
uses: actions/checkout@v4
```

This checks out the repository on the job runner so workflow files,
`config/devices.json`, the test code, and `requirements.txt` can be
accessed.

### Step 2 --- Authenticate to Google Cloud/Firebase

The workflow uses:

``` yaml
uses: google-github-actions/auth@v2
with:
  credentials_json: '${{ secrets.FIREBASE_SERVICE_ACCOUNT }}'
```

The service-account JSON comes from GitHub Secrets. The workflow then
requests an access token:

``` bash
ACCESS_TOKEN="$(gcloud auth print-access-token)"
```

It checks that the token is not empty and masks it in GitHub Actions
logs.

### Step 3 --- Fetch the latest Firebase App Distribution release

The workflow constructs the Firebase App Distribution releases endpoint:

``` text
https://firebaseappdistribution.googleapis.com/v1/projects/PROJECT_NUMBER/apps/APP_ID/releases
```

The request uses an access token and asks for one release ordered by
creation time, newest first. The core request is equivalent to:

``` bash
curl --silent --show-error --fail-with-body \
  --get \
  --url "$API_URL" \
  --header "Authorization: Bearer ${ACCESS_TOKEN}" \
  --header "Accept: application/json" \
  --data-urlencode "pageSize=1" \
  --data-urlencode "orderBy=createTime desc"
```

The response is saved as `firebase-release.json`. The workflow validates
that the response is JSON and extracts:

-   `releases[0].binaryDownloadUri` --- download URL for the APK.
-   `releases[0].name` --- release name for logging.

If project number, app ID, access token, or download URL is missing, the
step fails.

### Step 4 --- Download the APK

The workflow downloads the release APK to `firebase-app.apk`:

``` bash
curl \
  --fail-with-body \
  --location \
  --silent \
  --show-error \
  --retry 5 \
  --retry-delay 3 \
  --retry-all-errors \
  --connect-timeout 30 \
  --max-time 300 \
  "$DOWNLOAD_URL" \
  --output firebase-app.apk
```

It then checks that the downloaded file exists and is not empty:

``` bash
test -s firebase-app.apk
ls -lh firebase-app.apk
```

### Step 5 --- Transfer the APK to the verification job

The workflow uploads the file as an artifact:

``` yaml
uses: actions/upload-artifact@v4
with:
  name: firebase-apk
  path: firebase-app.apk
  if-no-files-found: error
  retention-days: 1
```

The next job downloads it:

``` yaml
uses: actions/download-artifact@v4
with:
  name: firebase-apk
  path: .
```

This is needed because separate GitHub Actions jobs run on separate
runners.

### Step 6 --- Verify the APK

The verification job executes:

``` bash
file firebase-app.apk
APK_SIZE="$(stat -c%s firebase-app.apk)"

if [ "$APK_SIZE" -le 0 ]; then
  echo "ERROR: APK is empty"
  exit 1
fi

echo "APK size: ${APK_SIZE} bytes"
```

This confirms the file exists and has a non-zero size. It is a basic
file check, not a full Android package/signature validation.

### Step 7 --- Authenticate to pCloudy

The workflow requests a pCloudy token using HTTP Basic authentication:

``` bash
curl --silent --show-error --fail-with-body \
  --retry 5 \
  --retry-delay 3 \
  --retry-all-errors \
  -u "${PCLOUDY_EMAIL}:${PCLOUDY_ACCESS_KEY}" \
  "https://device.pcloudy.com/api/access"
```

The response is saved to `pcloudy-auth.json`. The workflow extracts:

``` bash
TOKEN="$(jq -r '.result.token // empty' pcloudy-auth.json)"
```

The token must be present before continuing. The workflow masks it in
logs. Other jobs authenticate again because outputs from a previous job
are not automatically available to all later jobs.

### Step 8 --- Fetch currently available Android devices

The workflow sends a POST request to:

``` text
https://device.pcloudy.com/api/devices
```

The request body includes the token, requested duration, Android
platform, and availability filter. The response is saved as
`pcloudy-devices.json`.

The workflow lists available Android devices from the response with
`jq`, including the full device name, display name, and Android version.
The device snapshot is uploaded as an artifact named
`pcloudy-device-snapshot` for the test job.

### Step 9 --- Validate configured target devices

The workflow validates `config/devices.json`:

``` bash
DEVICES_FILE="config/devices.json"
test -f "$DEVICES_FILE"
jq empty "$DEVICES_FILE"

ENABLED_COUNT="$(jq '[.devices[]? | select(.enabled == true)] | length' "$DEVICES_FILE")"

if [ "$ENABLED_COUNT" -eq 0 ]; then
  echo "ERROR: No enabled devices configured in $DEVICES_FILE"
  exit 1
fi

jq -r '.devices[]? | select(.enabled == true) | .name' "$DEVICES_FILE"
```

This validates the JSON and requires at least one enabled device. The
test job refreshes availability before each device test, because the
earlier device list is only a snapshot.

### Step 10 --- Upload the APK to pCloudy

The upload request sends the APK as a multipart form:

``` bash
curl \
  --http1.1 \
  --silent \
  --show-error \
  --location \
  --retry 5 \
  --retry-delay 5 \
  --retry-all-errors \
  --connect-timeout 30 \
  --max-time 300 \
  --output pcloudy-upload.json \
  --write-out "%{http_code}" \
  --request POST \
  --form "file=@firebase-app.apk" \
  --form "source_type=raw" \
  --form "token=${PCLOUDY_TOKEN}" \
  --form "filter=all" \
  "https://device.pcloudy.com/api/upload_file"
```

The workflow checks for an HTTP 2xx response, saves the response as
`pcloudy-upload.json`, and attempts to extract the uploaded application
filename from the returned JSON. That filename is passed to the test job
as a job output and used in the Appium capabilities.

### Step 11 --- Set up Python and install dependencies

The test job sets up Python 3.12:

``` yaml
uses: actions/setup-python@v5
with:
  python-version: "3.12"
```

It then installs the dependencies declared by the repository:

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip list
```

The workflow fails if `requirements.txt` is missing.

### Step 12 --- Create the pCloudy Appium session

The test uses the Appium Python client and Android UiAutomator2 options.
The remote session endpoint is:

``` text
https://device.pcloudy.com/appiumcloud/wd/hub
```

The test sets standard capabilities including:

-   `platformName`: `Android`
-   `appium:automationName`: `UiAutomator2`
-   `appium:appPackage`: `com.epam.mobitru`
-   `appium:noReset`: `false`
-   `appium:autoGrantPermissions`: `true`
-   `appium:newCommandTimeout`: `600`
-   `appium:launchTimeout`: `90000`
-   `appium:instrumentAppPerformance`: `true`
-   `appium:appPerformance`: `true`

The nested `pcloudy:options` include the pCloudy username, API key,
uploaded application filename, duration, video setting, performance-data
setting, device-logs setting, and Appium version. The test uses either a
reservation ID (`RID`) or the full target device name.

Session creation is retried up to three times, with a 15-second wait
between attempts.

### Step 13 --- Run the Android application lifecycle test

The test file `automation/test_app_lifecycle.py` checks the following
sequence:

1.  Create the pCloudy Appium session.
2.  Wait for the application to launch.
3.  Read `driver.current_package` and assert it matches
    `com.epam.mobitru`.
4.  Wait five seconds.
5.  Send the application to the background for five seconds.
6.  Bring the application to the foreground using
    `driver.activate_app(APP_PACKAGE)`.
7.  Terminate the application using `driver.terminate_app(APP_PACKAGE)`.
8.  Relaunch it using `driver.activate_app(APP_PACKAGE)`.
9.  Check the current package again and assert that it matches the
    expected package.
10. Print `APP LIFECYCLE TEST PASSED` if all assertions pass.
11. Close the Appium session in a `finally` block using `driver.quit()`.

The main test command is:

``` bash
PCLOUDY_DEVICE="$DEVICE_NAME" \
pytest \
  automation/test_app_lifecycle.py \
  -v -s --tb=short \
  --junitxml="$XML_FILE"
```

The workflow runs enabled devices sequentially, not in parallel. It
refreshes device availability before each test. A device that is not
available at the pre-check is recorded as skipped. Explicit
performance-capability errors and other Appium failures are not silently
treated as passes.

### Step 14 --- Collect results and upload artifacts

The workflow writes a per-device TSV summary to:

``` text
device-results/summary.tsv
```

It also creates log and summary files under:

``` text
device-results/
performance-results/
```

The summary records each device's status and reason, such as `PASSED`,
`FAILED`, or `SKIPPED`. The final status is failed if any device test
fails. If no test passes, the workflow exits with failure rather than
reporting a green run when no tests actually executed.

The final artifacts are uploaded using `actions/upload-artifact@v4`
under the name:

``` text
android-pcloudy-results
```

The artifact can include per-device logs, summaries, JUnit XML, Firebase
release metadata, pCloudy device data, and upload response data when
those files exist.

## 7. Running the Workflow

1.  Commit and push the workflow and test files to the configured
    repository branch (`main` for the push trigger).
2.  Open the repository on GitHub.
3.  Select **Actions**.
4.  Select **Android - Firebase to pCloudy Appium Performance**.
5.  Choose **Run workflow** if using the manual `workflow_dispatch`
    trigger.
6.  Open the run and inspect each job in order.
7.  Download the `android-pcloudy-results` artifact to review logs and
    summaries.

## 8. Expected Results

A successful run should show the relevant jobs completed successfully,
and the test logs should contain:

``` text
APP LIFECYCLE TEST PASSED
Appium session closed successfully
```

The per-device summary should show at least one `PASSED` result and no
failed tests for the overall run to finish successfully.

A report-link warning is not the same as an app lifecycle test failure
if the test itself passed. If the Appium driver reports that a
report-link command is not implemented, retrieve the report using a
pCloudy-supported reporting method or the pCloudy dashboard. Do not
treat an unsupported report-link command as proof that the test failed.

## 9. Troubleshooting

### Firebase token or release retrieval fails

-   Check that `FIREBASE_SERVICE_ACCOUNT`, `FIREBASE_PROJECT_NUMBER`,
    and `FIREBASE_APP_ID` are configured correctly.
-   Confirm the service account has access to the Firebase App
    Distribution app.
-   Review the API response in the failed step without exposing tokens
    or secrets.

### APK download or verification fails

-   Check the Firebase release exists and has an APK download URI.
-   Confirm the download URL remains valid during the download.
-   Check that the `firebase-apk` artifact upload and download steps
    both succeed.

### pCloudy authentication fails

-   Check `PCLOUDY_EMAIL` and `PCLOUDY_ACCESS_KEY` in GitHub Secrets.
-   Review the pCloudy API response, taking care not to expose
    credentials or tokens.

### Target device is unavailable

-   Confirm the exact full device name in `config/devices.json` matches
    the pCloudy device inventory.
-   Check the device's current availability. A device available during
    the initial fetch can become unavailable before the test starts.

### Appium session cannot be created

-   Check the Appium endpoint and pCloudy credentials.
-   Inspect the session error and determine whether it is a network
    connection issue, device availability issue, or capability error.
-   Performance capabilities may require a supported Android/iOS version
    and pCloudy plan/device configuration.

### Report link is not returned

-   A `Method is not implemented` message indicates that the requested
    Appium driver command is not implemented by the active driver.
-   The app lifecycle test may still pass if the lifecycle assertions
    succeed.
-   Use a pCloudy-supported reporting API or the pCloudy dashboard to
    obtain the report link.

## 10. Security Notes

-   Store all credentials in GitHub Secrets.
-   Do not commit `.json` files containing service-account credentials,
    API keys, or live access tokens.
-   Do not print access tokens or credentials in workflow logs.
-   Treat uploaded logs and API response artifacts as potentially
    sensitive and restrict access to the repository and workflow
    artifacts appropriately.
-   Review artifact contents before sharing them with a client.

## 11. Client Demo Walkthrough

Use this order for a short client demonstration:

1.  Explain that the APK is fetched from the latest Firebase App
    Distribution release.
2.  Show the APK verification step and its non-zero file size.
3.  Show pCloudy authentication and the target Android device list.
4.  Show the APK upload result and the uploaded application filename.
5.  Open the Appium lifecycle test logs.
6.  Demonstrate the launch, background, foreground, terminate, and
    relaunch checks.
7.  Show the per-device summary and downloadable result artifact.
8.  Explain any skipped device or warning transparently; do not describe
    a skipped test as passed.

This document describes the commands and operations represented in the
current workflow and test configuration. Exact API response fields and
pCloudy reporting capabilities depend on the active pCloudy service
implementation.

import os
import time

import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options


# ============================================================
# Configuration
# ============================================================

APP_PACKAGE = os.getenv(
    "APP_PACKAGE",
    "com.epam.mobitru",
)

DEVICE_NAME = os.getenv(
    "PCLOUDY_DEVICE",
    "",
)

# Optional legacy reservation support.
# For the current Perf. Automation flow, PCLOUDY_DEVICE is used.
RID = os.getenv(
    "RID",
    "",
)

PCLOUDY_EMAIL = os.environ["PCLOUDY_EMAIL"]
PCLOUDY_ACCESS_KEY = os.environ["PCLOUDY_ACCESS_KEY"]

PCLOUDY_APP_NAME = os.getenv(
    "PCLOUDY_APP_NAME",
    "firebase-app.apk",
)

PCLOUDY_APPIUM_URL = os.getenv(
    "PCLOUDY_APPIUM_URL",
    "https://device.pcloudy.com/appiumcloud/wd/hub",
)

PCLOUDY_DURATION = int(
    os.getenv("PCLOUDY_DURATION", "5")
)

PERFORMANCE_DATA = (
    os.getenv(
        "PCLOUDY_ENABLE_PERFORMANCE_DATA",
        "true",
    ).lower()
    == "true"
)


# ============================================================
# Create pCloudy Appium Driver
# ============================================================

def create_driver():
    """
    Create a pCloudy Appium Cloud session.

    Important:
    - This function does NOT perform manual booking.
    - It creates the pCloudy Appium/Perf. Automation session
      using pCloudy DeviceFullName.
    - Any Appium session-creation failure is a TEST FAILURE.
      It must not be converted into SKIPPED here.
    """

    if not DEVICE_NAME and not RID:
        raise RuntimeError(
            "PCLOUDY_DEVICE is empty and no RID was supplied."
        )

    options = UiAutomator2Options()

    # ========================================================
    # Standard W3C Android Capabilities
    # ========================================================

    options.set_capability(
        "platformName",
        "Android",
    )

    options.set_capability(
        "appium:automationName",
        "UiAutomator2",
    )

    options.set_capability(
        "appium:appPackage",
        APP_PACKAGE,
    )

    options.set_capability(
        "appium:noReset",
        False,
    )

    options.set_capability(
        "appium:autoGrantPermissions",
        True,
    )

    options.set_capability(
        "appium:newCommandTimeout",
        600,
    )

    options.set_capability(
        "appium:launchTimeout",
        90000,
    )

    # ========================================================
    # pCloudy App Performance / Perf. Automation
    # ========================================================

    options.set_capability(
        "appium:instrumentAppPerformance",
        True,
    )

    options.set_capability(
        "appium:appPerformance",
        True,
    )

    # ========================================================
    # pCloudy Options
    # ========================================================

    pcloudy_opts = {
        "pCloudy_Username": PCLOUDY_EMAIL,
        "pCloudy_ApiKey": PCLOUDY_ACCESS_KEY,
        "pCloudy_ApplicationName": PCLOUDY_APP_NAME,
        "pCloudy_DurationInMinutes": PCLOUDY_DURATION,
        "pCloudy_EnableVideo": False,
        "pCloudy_EnablePerformanceData": PERFORMANCE_DATA,
        "pCloudy_EnableDeviceLogs": False,
        "appiumVersion": "3.1.1",
    }

    # Current workflow:
    # devices.json -> PCLOUDY_DEVICE -> Perf. Automation
    if RID:
        pcloudy_opts["pCloudy_ReservationId"] = int(RID)
    else:
        pcloudy_opts["pCloudy_DeviceFullName"] = DEVICE_NAME

    options.set_capability(
        "pcloudy:options",
        pcloudy_opts,
    )

    # ========================================================
    # Print Configuration
    # ========================================================

    print("")
    print("==========================================")
    print("Starting pCloudy Appium session")
    print("==========================================")
    print(f"Device           : {DEVICE_NAME}")

    if RID:
        print(f"Reservation ID   : {RID}")

    print(f"Package          : {APP_PACKAGE}")
    print(f"Application      : {PCLOUDY_APP_NAME}")
    print(f"Duration         : {PCLOUDY_DURATION} minutes")
    print(f"Performance Data : {PERFORMANCE_DATA}")
    print("Appium Instrument : True")
    print("App Performance   : True")
    print(f"Appium URL       : {PCLOUDY_APPIUM_URL}")
    print("==========================================")

    # ========================================================
    # Retry Appium Session
    # ========================================================

    last_error = None

    for attempt in range(1, 4):
        try:
            print(
                f"Creating pCloudy Appium session "
                f"(attempt {attempt}/3)..."
            )

            driver = webdriver.Remote(
                command_executor=PCLOUDY_APPIUM_URL,
                options=options,
            )

            print("")
            print("==========================================")
            print("PCLOUDY APPIUM SESSION CREATED")
            print("==========================================")
            print(f"Device: {DEVICE_NAME}")
            print("Session type: Perf. Automation")
            print("==========================================")

            return driver

        except Exception as exc:
            last_error = exc
            error_text = str(exc)

            print("")
            print(
                f"Appium session attempt {attempt} failed:"
            )
            print(error_text)

            if "ECONNREFUSED" in error_text:
                print(
                    "ERROR TYPE: PCLOUDY_APPIUM_CONNECTION_REFUSED"
                )

            elif "Requested device not available" in error_text:
                print(
                    "ERROR TYPE: "
                    "PCLOUDY_APPIUM_DEVICE_SESSION_UNAVAILABLE"
                )

            else:
                print(
                    "ERROR TYPE: PCLOUDY_APPIUM_SESSION_ERROR"
                )

            if attempt < 3:
                print(
                    "Waiting 15 seconds before retry..."
                )
                time.sleep(15)

    # ========================================================
    # IMPORTANT:
    # Never mark this as SKIPPED here.
    #
    # Stage 9 already determines whether the device was
    # available before this test starts.
    #
    # If Appium session creation fails here, this device
    # has FAILED its Perf. Automation run.
    # ========================================================

    print("")
    print("==========================================")
    print("APPIUM SESSION FAILED")
    print("==========================================")
    print(f"Device: {DEVICE_NAME}")
    print(f"Last error: {last_error}")
    print("==========================================")

    raise RuntimeError(
        "APPIUM_SESSION_FAILED: "
        "Could not create pCloudy Appium session "
        f"after 3 attempts for device: {DEVICE_NAME}. "
        f"Last error: {last_error}"
    ) from last_error


# ============================================================
# App Lifecycle Test
# ============================================================

@pytest.mark.lifecycle
def test_app_lifecycle():

    driver = None

    try:
        # ====================================================
        # Create Appium Session
        # ====================================================

        driver = create_driver()

        print("")
        print("==========================================")
        print("Appium session created successfully")
        print("==========================================")
        print(f"Device           : {DEVICE_NAME}")
        print(f"Package          : {APP_PACKAGE}")
        print(f"Performance Data : {PERFORMANCE_DATA}")
        print("Appium Instrument : True")
        print("App Performance   : True")
        print("==========================================")

        # ====================================================
        # 1. Launch Application
        # ====================================================

        print("")
        print("Step 1: Launching application")

        driver.activate_app(APP_PACKAGE)

        time.sleep(10)

        current_package = driver.current_package

        print(
            f"Current package: {current_package}"
        )

        assert current_package == APP_PACKAGE, (
            f"Expected {APP_PACKAGE}, "
            f"but found {current_package}"
        )

        print(
            "Application launch verified"
        )

        # ====================================================
        # 2. Wait for Application
        # ====================================================

        print("")
        print(
            "Step 2: Waiting for application"
        )

        time.sleep(5)

        print(
            "Application wait completed"
        )

        # ====================================================
        # 3. Background Application
        # ====================================================

        print("")
        print(
            "Step 3: Sending application "
            "to background"
        )

        driver.background_app(5)

        print(
            "Application backgrounded successfully"
        )

        # ====================================================
        # 4. Bring Application to Foreground
        # ====================================================

        print("")
        print(
            "Step 4: Bringing application "
            "to foreground"
        )

        driver.activate_app(APP_PACKAGE)

        time.sleep(5)

        print(
            "Application foregrounded successfully"
        )

        # ====================================================
        # 5. Terminate Application
        # ====================================================

        print("")
        print(
            "Step 5: Terminating application"
        )

        driver.terminate_app(APP_PACKAGE)

        time.sleep(3)

        print(
            "Application terminated successfully"
        )

        # ====================================================
        # 6. Relaunch Application
        # ====================================================

        print("")
        print(
            "Step 6: Relaunching application"
        )

        driver.activate_app(APP_PACKAGE)

        time.sleep(8)

        current_package = driver.current_package

        print(
            f"Package after relaunch: "
            f"{current_package}"
        )

        assert current_package == APP_PACKAGE, (
            "Application did not relaunch correctly"
        )

        print(
            "Application relaunch verified"
        )

        # ====================================================
        # Test Passed
        # ====================================================

        print("")
        print("------------------------------------------")
        print("APP LIFECYCLE TEST PASSED")
        print("------------------------------------------")

    finally:

        # ====================================================
        # Close Appium Session
        # ====================================================

        if driver is not None:

            print("")
            print(
                "Ending Appium session"
            )

            # =================================================
            # Retrieve pCloudy Report Link
            # =================================================

            try:
                report_link = driver.execute_script(
                    "Pcloudy_getReportLink"
                )

                print("")
                print(
                    "=================================================="
                )
                print(
                    "PCLOUDY LIVE PERFORMANCE REPORT LINK:"
                )
                print(report_link)
                print(
                    "=================================================="
                )
                print("")

            except Exception as report_exc:

                print(
                    "Warning: Could not retrieve "
                    "report link programmatically: "
                    f"{report_exc}"
                )

            # =================================================
            # Quit Appium Session
            # =================================================

            try:
                driver.quit()

                print(
                    "Appium session closed successfully"
                )

            except Exception as close_exc:

                print(
                    "Warning while closing "
                    f"Appium session: {close_exc}"
                )

import os
import time

import pytest
from appium import webdriver
from appium.options.android import UiAutomator2Options

# ============================================================
# Configuration (all values come from the GitHub Actions env)
# ============================================================

APP_PACKAGE = os.getenv("APP_PACKAGE", "com.epam.mobitru")
APP_ACTIVITY = os.getenv("APP_ACTIVITY", "").strip()

DEVICE_NAME = os.getenv("PCLOUDY_DEVICE", "")
RID = os.getenv("RID", "").strip()

PCLOUDY_EMAIL = os.environ["PCLOUDY_EMAIL"]
PCLOUDY_ACCESS_KEY = os.environ["PCLOUDY_ACCESS_KEY"]

PCLOUDY_APP_NAME = os.getenv("PCLOUDY_APP_NAME", "firebase-app.apk")
PCLOUDY_APPIUM_URL = os.getenv(
    "PCLOUDY_APPIUM_URL",
    "https://device.pcloudy.com/appiumcloud/wd/hub",
)

# Keep the same value as the booking duration in the workflow
DURATION_MINUTES = int(os.getenv("PCLOUDY_DURATION", "30"))

# Optional: leave empty to use pCloudy's default Appium version
APPIUM_VERSION = os.getenv("PCLOUDY_APPIUM_VERSION", "").strip()


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


# pCloudy_EnablePerformanceData capability
PERFORMANCE_DATA = _flag("PCLOUDY_ENABLE_PERFORMANCE_DATA", "false")

# appium:instrumentAppPerformance + appium:appPerformance (APK instrumentation)
INSTRUMENT_APP = _flag("PCLOUDY_INSTRUMENT_APP", "false")

# Pass pCloudy_ApplicationName (needed when pCloudy should resolve the uploaded app)
PASS_APP_NAME = _flag("PCLOUDY_PASS_APP", "true")

SESSION_ATTEMPTS = int(os.getenv("SESSION_ATTEMPTS", "3"))
SESSION_RETRY_WAIT = int(os.getenv("SESSION_RETRY_WAIT", "30"))
SESSION_TIMEOUT_SECONDS = int(os.getenv("SESSION_TIMEOUT_SECONDS", "150"))


# ============================================================
# Driver creation
# ============================================================

def build_options() -> UiAutomator2Options:
    options = UiAutomator2Options()

    options.set_capability("platformName", "Android")
    options.set_capability("appium:automationName", "UiAutomator2")
    options.set_capability("appium:appPackage", APP_PACKAGE)
    options.set_capability("appium:noReset", False)
    options.set_capability("appium:autoGrantPermissions", True)
    options.set_capability("appium:newCommandTimeout", 600)
    options.set_capability("appium:launchTimeout", 90000)

    if APP_ACTIVITY:
        options.set_capability("appium:appActivity", APP_ACTIVITY)

    if INSTRUMENT_APP:
        options.set_capability("appium:instrumentAppPerformance", True)
        options.set_capability("appium:appPerformance", True)

    pcloudy_opts = {
        "pCloudy_Username": PCLOUDY_EMAIL,
        "pCloudy_ApiKey": PCLOUDY_ACCESS_KEY,
        "pCloudy_DurationInMinutes": DURATION_MINUTES,
        "pCloudy_EnableVideo": False,
        "pCloudy_EnablePerformanceData": PERFORMANCE_DATA,
        "pCloudy_EnableDeviceLogs": False,
    }

    if PASS_APP_NAME:
        pcloudy_opts["pCloudy_ApplicationName"] = PCLOUDY_APP_NAME

    if APPIUM_VERSION:
        pcloudy_opts["appiumVersion"] = APPIUM_VERSION

    if RID:
        pcloudy_opts["pCloudy_ReservationId"] = int(RID)
    else:
        pcloudy_opts["pCloudy_DeviceFullName"] = DEVICE_NAME

    options.set_capability("pcloudy:options", pcloudy_opts)
    return options


def _new_remote(options: UiAutomator2Options):
    """Create the remote driver with a shorter per-attempt timeout when supported."""
    try:
        from appium.webdriver.client_config import AppiumClientConfig

        config = AppiumClientConfig(
            remote_server_addr=PCLOUDY_APPIUM_URL,
            timeout=SESSION_TIMEOUT_SECONDS,
        )
        return webdriver.Remote(options=options, client_config=config)
    except ImportError:
        # Older Appium-Python-Client versions
        return webdriver.Remote(
            command_executor=PCLOUDY_APPIUM_URL,
            options=options,
        )


def create_driver():
    if not DEVICE_NAME and not RID:
        raise RuntimeError("Both PCLOUDY_DEVICE and RID are empty")

    options = build_options()

    print("")
    print("==========================================")
    print("Starting pCloudy Appium session")
    print("==========================================")
    print(f"Device            : {DEVICE_NAME}")
    if RID:
        print(f"Reservation ID    : {RID}")
    print(f"Package           : {APP_PACKAGE}")
    print(f"Activity          : {APP_ACTIVITY or '<not set>'}")
    print(f"Duration (min)    : {DURATION_MINUTES}")
    print(f"Performance Data  : {PERFORMANCE_DATA}")
    print(f"Instrument App    : {INSTRUMENT_APP}")
    print(f"Pass App Name     : {PASS_APP_NAME}")
    print(f"Appium Version    : {APPIUM_VERSION or '<pCloudy default>'}")
    print("==========================================")

    last_error = None

    for attempt in range(1, SESSION_ATTEMPTS + 1):
        try:
            print(
                f"Creating pCloudy Appium session "
                f"(attempt {attempt}/{SESSION_ATTEMPTS})..."
            )
            driver = _new_remote(options)
            print("Appium session created successfully")
            return driver

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            # Print only the first part of the message to keep logs readable
            print(f"Appium session attempt {attempt} failed:")
            print(str(exc)[:600])

            if attempt < SESSION_ATTEMPTS:
                print(f"Waiting {SESSION_RETRY_WAIT} seconds before retry...")
                time.sleep(SESSION_RETRY_WAIT)

    raise RuntimeError(
        f"Could not create pCloudy Appium session after "
        f"{SESSION_ATTEMPTS} attempts for device: {DEVICE_NAME}"
    ) from last_error


# ============================================================
# App Lifecycle Test
# ============================================================

@pytest.mark.lifecycle
def test_app_lifecycle():
    driver = None

    try:
        # ----------------------------------------------------
        # Create Appium session
        # ----------------------------------------------------
        driver = create_driver()

        print("")
        print("==========================================")
        print("Appium session created successfully")
        print("==========================================")

        # ----------------------------------------------------
        # 1. Launch application
        # ----------------------------------------------------
        print("\nStep 1: Launching application")
        time.sleep(10)

        current_package = driver.current_package
        print(f"Current package: {current_package}")

        assert current_package == APP_PACKAGE, (
            f"Expected {APP_PACKAGE}, but found {current_package}"
        )
        print("Application launch verified")

        # ----------------------------------------------------
        # 2. Wait for application
        # ----------------------------------------------------
        print("\nStep 2: Waiting for application")
        time.sleep(5)
        print("Application wait completed")

        # ----------------------------------------------------
        # 3. Background application (press HOME)
        # ----------------------------------------------------
        print("\nStep 3: Sending application to background")
        driver.press_keycode(3)  # KEYCODE_HOME
        time.sleep(5)
        print("Application backgrounded successfully")

        # ----------------------------------------------------
        # 4. Bring application to foreground
        # ----------------------------------------------------
        print("\nStep 4: Bringing application to foreground")
        driver.activate_app(APP_PACKAGE)
        time.sleep(5)

        current_package = driver.current_package
        assert current_package == APP_PACKAGE, (
            f"App not in foreground after activate: {current_package}"
        )
        print("Application foregrounded successfully")

        # ----------------------------------------------------
        # 5. Terminate application
        # ----------------------------------------------------
        print("\nStep 5: Terminating application")
        driver.terminate_app(APP_PACKAGE)
        time.sleep(3)
        print("Application terminated successfully")

        # ----------------------------------------------------
        # 6. Relaunch application
        # ----------------------------------------------------
        print("\nStep 6: Relaunching application")
        driver.activate_app(APP_PACKAGE)
        time.sleep(8)

        current_package = driver.current_package
        print(f"Package after relaunch: {current_package}")

        assert current_package == APP_PACKAGE, (
            "Application did not relaunch correctly"
        )
        print("Application relaunch verified")

        print("")
        print("------------------------------------------")
        print("APP LIFECYCLE TEST PASSED")
        print("------------------------------------------")

    finally:
        if driver is not None:
            print("\nEnding Appium session")

            # pCloudy report link (only meaningful if performance data is on)
            try:
                report_link = driver.execute_script("Pcloudy_getReportLink")
                print("")
                print("==================================================")
                print("PCLOUDY LIVE PERFORMANCE REPORT LINK:")
                print(report_link)
                print("==================================================")
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: Could not retrieve report link: {exc}")

            try:
                driver.quit()
                print("Appium session closed successfully")
            except Exception as exc:  # noqa: BLE001
                print(f"Warning while closing Appium session: {exc}")

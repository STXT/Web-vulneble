from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.alert import Alert

def handle_unexpected_alert(driver):
    try:
        alert = Alert(driver)
        print(f"[Alert Detected] Text: {alert.text}")
        alert.accept()
    except NoAlertPresentException:
        pass
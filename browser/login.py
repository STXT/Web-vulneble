# 登录与登录状态监测
# TODO: 适配不同url的登录与检测登录

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def login(driver, url="http://127.0.0.1:2222/login.php", username="admin", password="password", security="Low"):
    driver.get(url)

    # 使用 By.NAME 来定位用户名输入框
    username_field = driver.find_element(By.NAME, "username")
    username_field.send_keys(username)

    # 使用 By.NAME 来定位密码输入框
    password_field = driver.find_element(By.NAME, "password")
    password_field.send_keys(password)

    # 使用 By.NAME 来定位登录按钮
    login_button = driver.find_element(By.NAME, "Login")
    login_button.click()

    # 跳转到安全设置页面
    driver.get("http://127.0.0.1:2222/security.php")
    try:
        # 等待下拉框出现，最多等待10秒
        security_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "security"))
        )
        security_dropdown = Select(security_element)
    except TimeoutException:
        raise RuntimeError("等待安全等级下拉框超时，页面可能未正确加载")
    security_dropdown = Select(driver.find_element(By.NAME, "security"))
    print("security:", security)
    security_dropdown.select_by_visible_text(security) # 根据文本选择

    submit_button = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
    submit_button.click()

    print("login success")

def check_login(driver):
    """
    检查当前页面是否仍然处于登录状态。如果没有登录，执行登录操作。
    """
    from .alert import handle_unexpected_alert
    handle_unexpected_alert(driver)

    # 检查当前页面的 URL 是否是登录页面的 URL
    if "login.php" in driver.current_url:
        print("Login session expired or not logged in, performing login again...")
        login(driver) # 执行登录操作
        print("Re-logged in successfully!")
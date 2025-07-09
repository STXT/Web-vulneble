# 得到一个初始的 Selenium WebDriver 实例
# 这个实例可以用于后续的浏览器操作

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os

def get_driver(headless=True):
    # 创建 ChromeOptions 实例
    options = Options()

    if headless:
        # 如果你不想看到浏览器界面，可以启用无头模式（headless）
        options.add_argument('--headless')

    # 配置 Chrome 浏览器的路径（可以根据需要调整）
    chrome_path = os.environ.get("chrome_path") # 从环境变量中读取
    if chrome_path:
        options.binary_location = chrome_path

    # 创建 WebDriver 服务，自动下载并使用正确的 ChromeDriver 版本
    service = Service(ChromeDriverManager().install())

    # 创建 WebDriver 实例
    driver = webdriver.Chrome(service=service, options=options)

    # 增加页面加载超时时间（单位：秒）
    driver.set_page_load_timeout(30) # 设置为10秒

    # 增加脚本执行超时时间
    driver.set_script_timeout(10)
    return driver
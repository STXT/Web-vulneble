# 导航：递归获取所有链接
# 通用于不同的url

from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

# 递归获取所有链接
def get_all_links(driver, url, visited_links=None, blacklist=None, depth=0, max_depth=2, check_login_func=None):
    if visited_links is None:
        visited_links = set()
    if blacklist is None:
        blacklist = set()

    if depth > max_depth:
        return visited_links
    
    domain = urlparse(url).netloc

    # 先检查是否已处理
    if url in visited_links or url in blacklist:
        return visited_links
    
    try:
        driver.get(url)
        if check_login_func:
            check_login_func(driver)
        driver.get(url)

        # 只有访问成功才加入已访问集合
        visited_links.add(url) # 正确位置

        links = driver.find_elements(By.TAG_NAME, "a")
        link_urls = [link.get_attribute('href') for link in links if link.get_attribute('href')]
        
        for link in link_urls:
            if urlparse(link).netloc == domain:
                if link not in visited_links and link not in blacklist:
                    get_all_links(driver, link, visited_links, blacklist, depth+1, max_depth, check_login_func) # 访问下一层
    
    except TimeoutException:
        # 仅加入黑名单，不污染已访问集合
        blacklist.add(url)
        print(f"Timeout skipped: {url}")

    if depth == 0: # 在最外层将要退出时，打印爬取到的所有连接
        print("Found links:")
        for link in visited_links:
            print(link)

    return visited_links # 仅包含成功访问的URL
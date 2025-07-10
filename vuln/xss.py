from selenium.webdriver.common.by import By
from browser.login import check_login
from utils.misc import generate_random_value
from utils.xss_reflection import check_xss_reflection
import time

# 添加XSS检测功能
def find_xss_inputs(driver, form_inputs, all_urls, check_login_func=check_login):

    xss_inputs_results = []

    for form in form_inputs:
        url = form['url']
        inputs = form['inputs']
        print(f"\n[Scanning Form for XSS] {url}")

        for input_field in inputs:
            input_type = input_field['type']
            input_name = input_field['name']

            if not input_name:
                continue

            if input_type in ['text', 'password', 'email', 'tel', 'url', 'search', 'textarea']:
                target_value = generate_random_value(8)
                # try:
                driver.get(url)
                check_login_func(driver)
                driver.get(url)

                # 填充字段
                for f in inputs:
                    name = f.get('name')
                    ftype = f.get('type')

                    if not name or ftype in ['submit', 'hidden']:
                        continue

                    try:
                        elem = driver.find_element(By.NAME, name)
                        elem.clear()
                        if name == input_name:
                            elem.send_keys(target_value)
                            print(f"{name} fill {target_value}")
                        else:
                            elem.send_keys(generate_random_value(5))
                            print(f"{name} fill random")
                    except:
                        print(f"[Warning] Could not find input field: {name}")
                        continue

                # 提交表单
                submitted = False
                for f in inputs:
                    if f['type'] == 'submit':
                        try:
                            if f.get('name'):
                                submit_button = driver.find_element(By.NAME, f['name'])
                            else:
                                submit_button = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
                            submit_button.click()
                            submitted = True
                            break
                        except:
                            continue

                if not submitted:
                    print(f"[Warning] No submit button found for form at {url}, skipping...")
                    continue

                # 检查 XSS 是否反射在当前页面或其他页面
                # print("checking xss:",target_value) # 这里有时候也会漏找，试试print拖一下时间看还会漏吗
                time.sleep(0.2)
                matched_pages, contexts = check_xss_reflection(driver, target_value, all_urls)
                if matched_pages:
                    print(f"[+] XSS reflected by input '{input_name}' with value '{target_value}' -> found in {matched_pages}")
                    xss_inputs_results.append({
                        "input_name": input_name,
                        "trigger_value": target_value,
                        "reflected_pages": matched_pages,
                        "context": contexts,  # 添加提取的上下文
                        "form": form
                    })
                # # 页面跳转非常多的时候容易出错，正常现象
                # except Exception as e:
                #     print(f"[Error] Exception while testing input '{input_name}': {e}")

    return xss_inputs_results

# 获取所有XSS输入的函数
def get_all_xss_inputs(driver, all_form_inputs, visited_links, check_login_func=check_login, args=None):
    print("\nStarting XSS Detection...")
    xss_results = []
    for inputs in all_form_inputs:
        xss_findings = find_xss_inputs(driver, inputs, visited_links, check_login_func)
        xss_results.extend(xss_findings)

    # # 打印结果
    # print("\n\n=== Scan Results ===")
    # print(f"\nSQL Injection Findings ({len(sql_results)}):")
    # for result in sql_results:
    #     print(result)

    print(f"\nXSS Findings ({len(xss_results)}):")
    for result in xss_results:
        print(result)

    return xss_results
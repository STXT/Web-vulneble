from selenium.webdriver.common.by import By
import time

from utils.sql_log import get_all_sql_statments, clear_sql_log
from utils.misc import generate_random_value
from browser.login import check_login

def find_sql_inputs(driver, form_inputs, args, check_login_func=check_login):

    sql_inputs_results = []

    for form in form_inputs:

        url = form['url']
        inputs = form['inputs']
        print(f"\n[Scanning Form] {url}")
        
        for input_field in inputs:
            input_type = input_field['type']
            input_name = input_field['name']

            if not input_name:
                continue

            if input_type in ['text', 'password', 'email', 'tel', 'url', 'search', 'textarea']:
                target_value = generate_random_value(8)
                # try:
                clear_sql_log(args)
                driver.get(url)
                check_login_func(driver)
                driver.get(url)

                    # 🔽 遍历所有字段：为目标字段填特定值，其它字段填随机值
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
                            elem.send_keys(generate_random_value(5))  # 随机值填其他字段
                            print(f"{name} fill random")
                    except:
                        print(f"[Warning] Could not find input field: {name}")
                        continue

                # 🔽 提交表单
                submitted = False
                for f in inputs:
                    if f['type'] == 'submit':
                        try:
                            if f.get('name'):
                                submit_button = driver.find_element(By.NAME, f['name'])
                            else:
                                # name 不存在时，尝试 fallback：查找第一个 type=submit 的 input
                                submit_button = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
                            submit_button.click()
                            submitted = True
                            break
                        except:
                            continue

                if not submitted:
                    print(f"[Warning] No submit button found for form at {url}, skipping...")
                    continue
                
                # print("checking sql:",target_value)
                time.sleep(0.2)
                matched_sql = get_all_sql_statments(target_value, args)
                if matched_sql:
                    print(f"[+] SQL triggered by input '{input_name}' with value '{target_value}' -> {matched_sql}")
                    sql_inputs_results.append({
                        "input_name": input_name,
                        "trigger_value": target_value,
                        "sql_statements": matched_sql,
                        "form": form
                    })
                # except Exception as e:
                #     print(f"[Error] Exception while testing input '{input_name}': {e}")

    
    return sql_inputs_results

def get_all_sql_inputs(driver, all_form_inputs, args, check_login_func=check_login):

    print("\nStarting SQL Injection Detection...")

    sql_results = []
    for inputs in all_form_inputs:
        sql_findings = find_sql_inputs(driver, inputs, args, check_login_func)
        sql_results.extend(sql_findings)

    return sql_results
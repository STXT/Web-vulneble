# 获取一个url的所有表单输入点  填写所有字段并提交一次  获取一系列url的所有表单输入点

import random
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from .login import check_login
from utils.misc import generate_random_value # 生成随机值的函数

def get_form_inputs(driver, url, check_login_func=check_login):
    # 检查登录状态（确保已登录）
    print("getting form:",url)

    form_data = []

    try:
        # 访问页面
        driver.get(url)
        if check_login_func:
            check_login_func(driver)
        driver.get(url)

    except TimeoutException:
        print(f"Timeout exceeded for {url}, marking as visited and skipping.")
        return form_data  # 如果页面加载超时，返回空数据
    
    # 获取页面中的所有表单
    forms = driver.find_elements(By.TAG_NAME, "form")

    for form in forms:
        form_info = {
            "url": url,  # 当前表单所在的页面 URL
            "inputs": []
            }
        
        # 获取表单中的所有输入元素
        inputs = form.find_elements(By.TAG_NAME, "input")
        for input_element in inputs:
            input_type = input_element.get_attribute("type")
            input_name = input_element.get_attribute("name")
            input_value = input_element.get_attribute("value") or ""
            form_info["inputs"].append({
                "type": input_type,
                "name": input_name,
                "value": input_value
            })

        # 获取 textarea 元素，并统一格式添加
        textareas = form.find_elements(By.TAG_NAME, "textarea")
        for textarea in textareas:
            input_name = textarea.get_attribute("name")
            input_value = textarea.get_attribute("value") or ""
            form_info["inputs"].append({
                "type": "textarea",
                "name": input_name,
                "value": input_value
            })
            # 将表单信息添加到结果列表中
        form_data.append(form_info)

    return form_data


def get_all_form_inputs(driver, urls, check_login_func=check_login):
    """
    获取一系列 URL 的所有表单输入点。
    :param driver: Selenium WebDriver 实例
    :param urls: URL 列表
    :param check_login_func: 检查登录状态的函数
    :return: 包含所有表单输入点的列表
    """
    all_form_inputs = []  # 用于存储所有链接的输入点

    for url in urls:
        form_inputs = get_form_inputs(driver, url, check_login_func)
        if form_inputs:
            all_form_inputs.append(form_inputs)

    # 打印所有表单输入点
    print("=== All form inputs found: ===")
    for inputs in all_form_inputs:
        print(inputs)

    return all_form_inputs

# 先填完所有可填写字段，然后最后统一提交一次
def fill_and_submit_form(driver, form_inputs, generate_random_value=generate_random_value, check_login_func=check_login):
    check_login_func(driver)
    """
    填充并提交表单，针对每个 `type="text"`、`type="password"`、`type="email"`、`type="tel"`、`type="url"`、
    `type="search"` 和 `textarea` 的输入框，填充一个随机值。
    """
    # 对于每个表单，遍历其中的输入字段并填充随机值
    for form in form_inputs:

        # 获取表单的 URL 和输入字段
        url = form['url'] # 获取当前表单所在的页面 URL
        print("filling url:",url)
        driver.get(url) # 切换到当前 URL 页面

        # 获取表单的 URL 和输入字段
        for input_field in form['inputs']:
            input_type = input_field['type']
            input_name = input_field['name']

            # 过滤出与文本相关的字段（text, password, email, tel, url, search, textarea）
            if input_name: # 仅当 name 不为空时才继续
                if input_type in ['text', 'password', 'email', 'tel', 'url', 'search']:
                    random_value = generate_random_value(5) # 生成一个 5 位数字
                    try:
                        input_element = driver.find_element(By.NAME, input_name)
                        input_element.clear() # 清空现有的值
                        input_element.send_keys(random_value) # 输入随机值
                    except:
                        print(f"[Warning] Could not find input field with name: {input_name}")
                
                # 处理 textarea 类型的输入框
                if input_type == 'textarea':
                    random_value = generate_random_value(10) # 生成一个 10 位数字作为 textarea 的值
                    try:
                        textarea_element = driver.find_element(By.NAME, input_name)
                        textarea_element.clear() # 清空现有的值
                        textarea_element.send_keys(random_value) # 输入随机值
                    except:
                        print(f"[Warning] Could not find textarea with name: {input_name}")
        
        # 提交表单（submit button）
        # 在每个 form['inputs'] 中如果有提交按钮（type="submit"），直接点击        
        for input_field in form['inputs']:
            if input_field['type'] == 'submit' and input_field['name']:
                try:
                    submit_button = driver.find_element(By.NAME, input_field['name'])
                    submit_button.click()
                except:
                    print(f"[Warning] Could not find submit button with name: {input_field['name']}")
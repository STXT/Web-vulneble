import time
from selenium.webdriver.common.by import By
from utils.misc import generate_random_value
from utils.sql_log import get_all_sql_statments, clear_sql_log
from browser.login import check_login

def test_sql_payload(driver, url, form, input_name, payload, trigger_value, args=None, check_login_func=check_login):
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
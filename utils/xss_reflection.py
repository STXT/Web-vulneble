# 有关XSS反射漏洞的上下文提取工具
from browser.login import check_login

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

def check_xss_reflection(driver, target_value, urls, payload=None, check_login_func=check_login):
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
                check_login_func(driver)
                driver.get(u)

                if target_value in driver.page_source:
                    reflected_pages.append(u)
                    context = extract_xss_input_context(target_value, driver.page_source, target_value)
                    contexts.append(context)
            except:
                continue

    return reflected_pages, contexts

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
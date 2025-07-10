# 对mysql日志处理的函数

import re

def fix_mysql_file_lines(lines: list):
        """
        综合处理新旧两种日志格式的多行合并函数
        功能优先级：
        1. 处理特殊行（版本声明/空字符/时间戳行）
        2. 处理操作起始行（连接ID + 操作类型）
        3. 处理常规续行
        """
        index = 0
        
        # 匹配旧版时间戳（ISO8601格式：2023-10-05T14:30:00.123Z）
        old_timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z')
        
        # 匹配新版操作行（连接ID + 操作类型）
        operation_pattern = re.compile(r'^\s*(\d+)\s+(\w+)\b')

        while index < len(lines):
            current_line = lines[index].rstrip('\n')  # 保留行尾原始空白
            
            # ===== 第一阶段：处理特殊行 =====
            # 条件优先级最高，遇到这些行直接跳过不处理
            is_special_line = (
                "mysqld, Version:" in current_line or   # 版本声明行
                '\x00' in current_line or               # 包含空字符的损坏行
                old_timestamp_pattern.search(current_line)  # 旧版时间戳行
            )
            
            if is_special_line:
                index += 1
                continue
            
            # ===== 第二阶段：处理操作起始行 =====
            # 检测是否是新的操作起始行（无论是否含时间戳）
            if operation_pattern.search(current_line):
                # 标准化格式：移除行首多余空白（便于后续处理）
                lines[index] = current_line.lstrip()
                index += 1
                continue
            
            # ===== 第三阶段：处理续行 ===== 
            if index > 0:  # 确保不是首行
                # 续行特征：以空白开头 且 不是独立操作行
                is_continuation = (
                    lines[index].startswith((' ', '\t')) and
                    not operation_pattern.search(lines[index])
                )
                
                if is_continuation:
                    # 合并时保留原始缩进中的单个空格（避免破坏SQL格式）
                    merged_line = lines[index-1].rstrip() + ' ' + lines[index].lstrip()
                    lines[index-1] = merged_line
                    lines.pop(index)
                    continue  # 保持index不变继续检查可能的多重续行
            
            # 未触发任何处理条件则移动到下一行
            index += 1

        return lines

def get_all_sql_statments(data_input, args):

    with open(args.sql_log_name, 'r', errors='ignore') as f:
        raw_lines = f.read().splitlines()
    
    # 合并多行（兼容新旧格式）
    merged_lines = fix_mysql_file_lines(raw_lines)
    # print(merged_lines)
    # 双模式解析正则
    old_format_pattern = re.compile(
        r'^\s*([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+Z)?'  # 时间戳
        r'\s*(\d+)?\s*(\w+)?\s*(.*)$'  # 连接ID、操作类型、SQL内容
    )
    new_format_pattern = re.compile(
        r'^\s*(\d{6} \d+:\d+:\d+)?\s*(\d+)\s+(\w+)\s+(.*)$'
    )
    
    sql_list = []
    for line in merged_lines:
        # 尝试匹配新格式
        match = new_format_pattern.match(line)
        if match:
            _, conn_id, op_type, sql = match.groups()
            if op_type in ['Query','Execute']:
                sql_list.append(sql.strip())
            continue
            
        # 尝试匹配旧格式
        match = old_format_pattern.match(line)
        if match:
            _, conn_id, op_type, sql = match.groups()
            if op_type in ['Query', 'Execute']:  # 旧格式可能用不同操作类型
                sql_list.append(sql.strip())
    
    # 后续筛选流程保持不变
    target_sql = [sql for sql in sql_list if data_input in sql]
    return [sql for i, sql in enumerate(target_sql) if i == 0 or sql != target_sql[i-1]]

def clear_sql_log(args):
        '''
            function used to clear logs to speed up
        '''
        with open(args.sql_log_name, 'r+') as f:
            f.truncate(0)
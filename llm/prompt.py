# 读取prompt

def load_prompt(path):
    with open(path, 'r', encoding='utf-8') as file:
        return file.read()
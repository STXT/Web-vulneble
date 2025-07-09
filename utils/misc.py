import random

def generate_random_value(length=5):
    """
    生成一个随机的数字字符串，长度为 `length`。
    默认生成 5 位数字。
    """
    return ''.join(random.choices('0123456789', k=length))
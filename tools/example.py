"""Example tool - показывает как создавать инструменты"""

def hello(name="World"):
    """Приветствует кого-то"""
    return f"Привет, {name}!"

def get_time():
    """Возвращает текущее время"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

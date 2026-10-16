"""Заголовок User-Agent — коротко, для людей: в заявках, в письмах о них и в списке сессий."""
import re

# Порядок важен: Яндекс Браузер, Edge и Opera тоже пишут о себе «Chrome», а Chrome — «Safari»
BROWSER_PATTERN_LIST = [
    ("Яндекс Браузер", r"YaBrowser/"), ("Edge", r"Edg/"), ("Opera", r"OPR/"), ("Firefox", r"Firefox/"),
    ("Chrome", r"Chrome/|CriOS/"), ("Safari", r"Safari/"),
]
OS_PATTERN_LIST = [("Android", r"Android"), ("iOS", r"iPhone|iPad|iPod"), ("Windows", r"Windows"), ("macOS", r"Mac OS X"), ("Linux", r"Linux")]


def describe_user_agent(user_agent: str) -> str:
    """User-Agent коротко, для людей: «Chrome, Android, телефон». Не узнали — пусто."""
    if not user_agent:
        return ""
    browser = next((name for name, pattern in BROWSER_PATTERN_LIST if re.search(pattern, user_agent)), "")
    system = next((name for name, pattern in OS_PATTERN_LIST if re.search(pattern, user_agent)), "")
    if re.search(r"iPad|Tablet", user_agent) or (system == "Android" and "Mobile" not in user_agent):
        device = "планшет"
    elif re.search(r"Mobile|iPhone", user_agent):
        device = "телефон"
    else:
        device = "компьютер"
    return ", ".join(part for part in (browser, system, device) if part)

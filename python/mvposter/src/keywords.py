"""把「动物搞笑」这类主题按语义槽位展开成多个检索关键词。

为什么是「槽位 + 组合」而不是让模型现编：

- 关键词是一个**可枚举的语义空间**（动物 × 情境 × 风格），枚举比现编更全、也更稳定；
- 同一天同参数的结果**可复现**（种子默认取当天日期），日志里能核对「今天到底搜了什么」；
- 不需要任何 API Key。将来要用大模型补齐长尾时，走 ``--keywords-file`` 注入即可，两不冲突。

槽位说明：``generic`` 是泛化短语（优先级最高），后面按「每轮换一个风格/情境」的方式
在动物之间轮转，保证前面的关键词覆盖到不同动物，而不是一只猫占满前十条。
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import NamedTuple


class Topic(NamedTuple):
    """一个语义主题：泛化短语 + 各槽位词表。"""

    display: str                    # 日志里显示的名字
    generic: tuple[str, ...]        # 泛化短语（直接可用的完整检索词）
    animals: tuple[str, ...]        # 动物槽位
    situations: tuple[str, ...]     # 情境 / 行为槽位
    styles: tuple[str, ...]         # 风格 / 情绪槽位
    chinese: tuple[str, ...]        # 中文关键词（--with-chinese 时才用）


TOPICS: dict[str, Topic] = {
    "动物搞笑": Topic(
        display="动物搞笑",
        generic=(
            "funny animals shorts",
            "funny pets moments",
            "funny animal videos",
            "funny animals caught on camera",
            "cute animals funny",
        ),
        animals=(
            "cat", "kitten", "cats", "dog", "puppy", "pets", "baby animals",
            "hamster", "parrot", "monkey", "rabbit", "duck", "goat", "cow",
            "fox", "panda", "squirrel", "otter", "penguin", "seal", "horse",
        ),
        situations=(
            "funny moments", "fail compilation", "caught on camera", "reaction",
            "sneeze", "stealing food", "taking a bath", "playing", "scared",
            "sleepy", "clumsy", "talking",
        ),
        styles=("funny", "hilarious", "cute", "adorable"),
        chinese=("动物搞笑", "萌宠搞笑", "猫咪搞笑日常", "狗狗搞笑视频"),
    ),
}

# 主题别名：用户怎么叫都认（中英混着写也行）
TOPIC_ALIASES = {
    "动物搞笑": "动物搞笑", "动物": "动物搞笑", "搞笑": "动物搞笑", "萌宠": "动物搞笑",
    "animal": "动物搞笑", "animals": "动物搞笑", "funny": "动物搞笑",
    "funny animals": "动物搞笑", "pets": "动物搞笑", "pet": "动物搞笑",
}

# --focus 的别名：聚焦到某一种动物（中英文都认）
FOCUS_ALIASES = {
    "猫": "cat", "猫咪": "cat", "cat": "cat", "cats": "cat",
    "狗": "dog", "狗狗": "dog", "dog": "dog", "dogs": "dog",
    "兔": "rabbit", "兔子": "rabbit", "rabbit": "rabbit",
    "鹦鹉": "parrot", "parrot": "parrot",
    "猴子": "monkey", "monkey": "monkey",
    "熊猫": "panda", "panda": "panda",
    "鸭子": "duck", "duck": "duck",
    "山羊": "goat", "goat": "goat",
    "奶牛": "cow", "cow": "cow",
    "狐狸": "fox", "fox": "fox",
    "松鼠": "squirrel", "squirrel": "squirrel",
    "企鹅": "penguin", "penguin": "penguin",
    "仓鼠": "hamster", "hamster": "hamster",
    "水獭": "otter", "otter": "otter",
    "海豹": "seal", "seal": "seal",
}

DEFAULT_TOPIC = "动物搞笑"
DEFAULT_LIMIT = 12   # 默认生成多少个关键词（12 个 × 50 条约 20 秒）


def default_seed(now: datetime | None = None) -> int:
    """默认种子 = 当天日期（YYYYMMDD）。

    这样「今天搜过的词」当天可复现，第二天又换一批——配合库里的去重，
    每天都能捞到新内容，而不是天天搜同一批。
    """
    return int((now or datetime.now()).strftime("%Y%m%d"))


def resolve_topic(name: str | None) -> Topic:
    """主题名（或别名）-> 主题表；不认识就抛 ValueError（由调用方提示可选值）。"""
    key = (name or DEFAULT_TOPIC).strip()
    resolved = TOPIC_ALIASES.get(key.lower()) or TOPIC_ALIASES.get(key)
    if resolved is None:
        raise ValueError(f"未知主题 {name!r}，可选：{'、'.join(TOPICS)}（别名："
                         + "、".join(sorted(TOPIC_ALIASES)) + "）")
    return TOPICS[resolved]


def resolve_focus(name: str | None) -> str | None:
    """聚焦的动物 -> 英文词（用在关键词里）；不认识就当没给。"""
    if not name:
        return None
    key = name.strip()
    return FOCUS_ALIASES.get(key) or FOCUS_ALIASES.get(key.lower())


def expand(topic: str | None = DEFAULT_TOPIC, focus: str | None = None,
           limit: int = DEFAULT_LIMIT, seed: int | None = None,
           include_chinese: bool = False) -> list[str]:
    """展开成至多 limit 个关键词（同一个 seed 得到同一份列表）。

    生成顺序：聚焦词（给了 --focus 时）-> 泛化短语 -> （可选）中文词
    -> 「风格 × 动物 + shorts」与「动物 + 情境」按轮次交替。

    为什么聚焦词排在泛化短语前面：用户显式说了「聚焦猫」，前几条就该是猫；
    泛化短语（如 ``funny animals shorts``）依然是召回主力，所以紧跟在后面、不会被丢掉。
    """
    table = resolve_topic(topic)
    rng = random.Random(default_seed() if seed is None else seed)
    animals = list(table.animals)
    focus_word = resolve_focus(focus)
    if focus_word:
        # 聚焦某动物时把它排到最前，但**保留**其他动物：只搜一种容易撞车、也容易搜空
        animals = [focus_word] + [word for word in animals if word != focus_word]
    else:
        rng.shuffle(animals)

    keywords: list[str] = []
    seen: set[str] = set()

    def push(keyword: str) -> None:
        if keyword not in seen:
            seen.add(keyword)
            keywords.append(keyword)

    def full() -> bool:
        return len(keywords) >= limit

    if focus_word:
        for style in table.styles:
            push(f"{style} {focus_word} shorts")

    for keyword in table.generic:
        push(keyword)
        if full():
            return keywords[:limit]

    if include_chinese:
        for keyword in table.chinese:
            push(keyword)
            if full():
                return keywords[:limit]

    # 每一轮换一个风格/情境，横着走动物，保证前几条覆盖不同动物
    rounds = max(len(table.styles), len(table.situations))
    for index in range(rounds):
        for animal in animals:
            if index < len(table.styles):
                push(f"{table.styles[index]} {animal} shorts")
            if index < len(table.situations):
                push(f"{animal} {table.situations[index]}")
            if full():
                return keywords[:limit]

    return keywords[:limit]

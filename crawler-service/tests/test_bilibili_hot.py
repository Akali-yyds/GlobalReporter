from news_crawler.spiders.china.bilibili_hot import BilibiliHotSpider


def _entry(*, title, tname, desc="", owner="Example", pubdate=1775206994):
    return {
        "title": title,
        "tname": tname,
        "desc": desc,
        "pubdate": pubdate,
        "owner": {"name": owner},
    }


def test_bilibili_hot_accepts_tech_vertical_signal():
    spider = BilibiliHotSpider()
    entry = _entry(
        title="骁龙8s Gen4 前瞻上手",
        tname="数码",
        desc="芯片和移动平台更新，分析 GPU 与 AI 推理能力。",
        owner="极客湾",
    )

    assert spider._is_meaningful_entry(entry) is True


def test_bilibili_hot_rejects_entertainment_noise():
    spider = BilibiliHotSpider()
    entry = _entry(
        title="新综艺开播，明星阵容公布",
        tname="娱乐",
        desc="粉丝热议嘉宾阵容和舞台表现。",
        owner="娱乐频道",
    )

    assert spider._is_meaningful_entry(entry) is False


def test_bilibili_hot_accepts_current_affairs_signal():
    spider = BilibiliHotSpider()
    entry = _entry(
        title="强硬反制！对原产于美国的所有进口商品再加征50%关税",
        tname="社科·法律·心理",
        desc="围绕关税、贸易和政策展开讨论。",
        owner="观察者网",
    )

    assert spider._is_meaningful_entry(entry) is True

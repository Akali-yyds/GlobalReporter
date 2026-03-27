# China news spiders
from news_crawler.spiders.china.sina import SinaSpider
from news_crawler.spiders.china.tencent import TencentSpider
from news_crawler.spiders.china.zhihu import ZhihuSpider

__all__ = ["SinaSpider", "TencentSpider", "ZhihuSpider"]

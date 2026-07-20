# -*- coding: utf-8 -*-
"""
供应链物流日报爬虫 - 增强版 v2.0
改进点:
  1. DNS修复: 多DNS服务器fallback,解决物流指闻域名解析失败
  2. 反爬虫绕过: User-Agent轮换、随机延迟、请求头伪装、指数退避重试
  3. 智能重试: 针对DNS错误、403、429等异常自动重试
  4. 自动摘要: 关键词分类、关键信息提取(金额/日期/公司)
  5. 内容验证: 检测拦截页、空内容、反爬虫关键词
  6. RSS增强: 使用feedparser替代ET,支持更多RSS格式
"""

import urllib.request
import urllib.error
import urllib.parse
import socket
import ssl
import time
import random
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# ========== 依赖检查 ==========
try:
    import feedparser
except ImportError:
    print("[WARN] feedparser not installed, using fallback RSS parser")
    feedparser = None

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    print("[WARN] beautifulsoup4 not installed, using regex fallback")
    BS4_AVAILABLE = False

try:
    import dns.resolver
    DNSPYTHON_AVAILABLE = True
except ImportError:
    DNSPYTHON_AVAILABLE = False


# ========== RSS配置 ==========
RSS_SOURCES = {
    "Talking Logistics": "https://talkinglogistics.com/feed/",
    "Supply Chain Dive": "https://www.supplychaindive.com/feeds/news/",
    "FreightWaves": "https://www.freightwaves.com/feed",
    "36氪": "https://36kr.com/feed",
    "TechCrunch": "https://techcrunch.com/feed/",
}

# ========== 爬虫配置（国内网站）==========
CRAWL_SOURCES = {
    "罗戈网": {
        "url": "https://www.logclub.com",
        "title_pattern": r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        "link_pattern": r'<a[^>]*href="(/news/\d+)"[^>]*>',
        "base_url": "https://www.logclub.com",
        "retry_count": 3,
        "min_delay": 3.0,
        "max_delay": 6.0,
    },
    "物流指闻": {
        # FIX: 更新为最新域名 headscm.com（旧域名 wuliuzhixun.com 已失效）
        "url": "https://www.headscm.com",
        "title_pattern": r'<h2[^>]*>(.*?)</h2>',
        "link_pattern": r'<a[^>]*href="(/article/\d+)"[^>]*>',
        "base_url": "https://www.headscm.com",
        "retry_count": 5,  # 增加重试次数
        "min_delay": 2.0,
        "max_delay": 4.0,
    },
    "亿邦动力": {
        "url": "https://www.ebrun.com",
        "title_pattern": r'<h4[^>]*>(.*?)</h4>',
        "link_pattern": r'<a[^>]*href="(/202\d+/\d+/\d+/\d+\.shtml)"[^>]*>',
        "base_url": "https://www.ebrun.com",
        "retry_count": 3,
        "min_delay": 3.0,
        "max_delay": 6.0,
    },
}

# ========== 用户代理池（轮换使用）==========
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
]

# ========== 反爬虫拦截关键词 ==========
BLOCK_SIGNALS = [
    "access denied", "captcha", "blocked", "forbidden",
    "请稍后重试", "访问过于频繁", "验证", "cloudflare",
    "安全检查", "人机验证", "您的访问被拒绝",
]

# ========== DNS修复模块 ==========
def resolve_with_fallback(hostname: str) -> Optional[str]:
    """
    多DNS服务器解析，解决 [Errno -2] Name or service not known 问题
    物流指闻等网站可能因DNS解析失败导致无法访问
    """
    # 先尝试系统默认解析
    try:
        ip = socket.gethostbyname(hostname)
        print("  [DNS] %s -> %s (system default)" % (hostname, ip))
        return ip
    except socket.gaierror:
        pass
    
    # 使用备用DNS服务器解析
    if DNSPYTHON_AVAILABLE:
        dns_servers = ["8.8.8.8", "8.8.4.4", "114.114.114.114", "223.5.5.5", "119.29.29.29"]
        for dns_ip in dns_servers:
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [dns_ip]
                answers = resolver.resolve(hostname, "A")
                ip = str(answers[0])
                print("  [DNS] %s -> %s (via %s)" % (hostname, ip, dns_ip))
                return ip
            except Exception:
                continue
    
    print("  [DNS] All DNS servers failed to resolve %s" % hostname)
    return None

def patch_dns_for_url(url: str) -> str:
    """对URL进行DNS预解析，失败时尝试域名变体"""
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return url
    
    # 尝试解析域名
    ip = resolve_with_fallback(hostname)
    if ip:
        return url  # 解析成功，返回原URL
    
    # 解析失败，尝试域名变体（www.前缀切换）
    if hostname.startswith("www."):
        alt_hostname = hostname[4:]
    else:
        alt_hostname = "www." + hostname
    
    ip = resolve_with_fallback(alt_hostname)
    if ip:
        # 构建新URL
        new_netloc = alt_hostname
        if parsed.port:
            new_netloc += ":" + str(parsed.port)
        return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))
    
    return url

# ========== 增强请求模块 ==========
class EnhancedRequest:
    """增强型请求类，集成反反爬虫技术"""
    
    def __init__(self):
        self.last_request_time = 0
        self.request_count = 0
    
    def _get_random_ua(self) -> str:
        """随机选择User-Agent"""
        return random.choice(USER_AGENTS)
    
    def _random_delay(self, min_sec: float, max_sec: float):
        """随机延迟，模拟人类阅读间隔，避免被识别为机器访问"""
        delay = random.uniform(min_sec, max_sec)
        delay += random.gauss(0, 0.3)  # 添加正态分布抖动
        delay = max(0.5, delay)
        time.sleep(delay)
    
    def _build_ssl_context(self):
        """构建SSL上下文，处理证书问题"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    def fetch(self, url: str, source_name: str = "", retry_count: int = 3,
              timeout: int = 15, min_delay: float = 2.0, max_delay: float = 5.0) -> Tuple[Optional[bytes], Optional[str]]:
        """
        智能抓取，带完整重试和反检测逻辑
        Returns: (content_bytes, error_message)
        """
        original_url = url
        
        for attempt in range(retry_count):
            try:
                # 1. 请求间隔控制（避免频率过高被拦截）
                elapsed = time.time() - self.last_request_time
                if elapsed < min_delay:
                    time.sleep(min_delay - elapsed + random.uniform(0, 1))
                
                # 2. DNS修复（针对物流指闻等域名解析失败的网站）
                if attempt > 0 or "headscm" in url or "logclub" in url or "ebrun" in url:
                    url = patch_dns_for_url(original_url)
                
                # 3. 构建请求头（模拟真实浏览器）
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self._get_random_ua(),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Cache-Control": "max-age=0",
                        "Referer": "https://www.google.com/search?q=" + urllib.parse.quote(source_name or "news"),
                    }
                )
                
                # 4. 执行请求
                ssl_context = self._build_ssl_context()
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ssl_context)
                )
                
                print("  请求 %s (尝试 %d/%d)..." % (source_name or url, attempt + 1, retry_count))
                response = opener.open(req, timeout=timeout)
                
                # 5. 检查HTTP状态码
                status = response.getcode()
                if status != 200:
                    print("  HTTP %d, retrying..." % status)
                    continue
                
                content = response.read()
                
                # 6. 验证内容有效性（防止返回空页面或拦截页）
                if len(content) < 100:
                    print("  内容过短(%d bytes),可能为拦截页,重试..." % len(content))
                    continue
                
                # 7. 检查是否包含反爬虫关键词
                content_str = content.decode("utf-8", errors="ignore").lower()
                if any(sig in content_str for sig in BLOCK_SIGNALS):
                    print("  检测到反爬虫拦截,重试...")
                    time.sleep(2 ** attempt + random.uniform(1, 3))  # 指数退避
                    continue
                
                self.last_request_time = time.time()
                self.request_count += 1
                print("  [OK] 成功获取 %d bytes" % len(content))
                return content, None
                
            except urllib.error.HTTPError as e:
                print("  HTTP错误 %d: %s" % (e.code, e.reason))
                if e.code == 403:  # Forbidden
                    time.sleep(2 ** attempt + random.uniform(1, 3))
                elif e.code == 429:  # Too Many Requests
                    time.sleep(5 * (attempt + 1))
                else:
                    time.sleep(2 ** attempt)
                    
            except urllib.error.URLError as e:
                error_msg = str(e.reason)
                print("  URL错误: %s" % error_msg)
                
                # DNS错误特殊处理（针对物流指闻的[Errno -2]）
                if "Name or service not known" in error_msg or "getaddrinfo" in error_msg:
                    print("  [DNS修复] 尝试备用域名...")
                    # 切换www前缀
                    if original_url.startswith("https://www."):
                        original_url = original_url.replace("https://www.", "https://")
                    elif original_url.startswith("https://") and not original_url.startswith("https://www."):
                        original_url = original_url.replace("https://", "https://www.")
                    time.sleep(3)
                else:
                    time.sleep(2 ** attempt)
                    
            except socket.timeout:
                print("  请求超时")
                time.sleep(2 ** attempt + 2)
                
            except Exception as e:
                print("  未知错误: %s" % str(e))
                time.sleep(2 ** attempt)
        
        return None, "所有%d次尝试均失败" % retry_count

# ========== 工具函数 ==========
def clean_html(text):
    """清理HTML标签"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip()
    return text

def fetch_rss(url, source_name=""):
    """解析RSS（增强版，支持feedparser）"""
    fetcher = EnhancedRequest()
    content, error = fetcher.fetch(url, source_name=source_name, retry_count=3, min_delay=1.0, max_delay=2.0)
    
    if error or not content:
        print("RSS失败: %s" % (error or "无内容"))
        return []
    
    # 使用feedparser（如果可用）
    if feedparser:
        try:
            feed = feedparser.parse(content)
            items = []
            for entry in feed.entries[:3]:
                title = clean_html(entry.get("title", ""))
                link = clean_html(entry.get("link", ""))
                if title and link:
                    items.append({"title": title, "link": link})
            return items
        except Exception as e:
            print("feedparser解析失败: %s, 使用fallback" % str(e))
    
    # Fallback: 使用ET解析
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        items = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            title = clean_html(title_elem.text) if title_elem is not None else ""
            link = item.find("link")
            link_text = clean_html(link.text) if link is not None else ""
            if title and link_text:
                items.append({"title": title, "link": link_text})
        return items[:3]
    except Exception as e:
        print("RSS fallback解析失败: %s" % str(e))
        return []

def crawl_website(source_name, config):
    """爬取网站（增强版，带反爬虫和重试）"""
    print("正在爬取: %s" % source_name)
    
    fetcher = EnhancedRequest()
    content, error = fetcher.fetch(
        config["url"],
        source_name=source_name,
        retry_count=config.get("retry_count", 3),
        timeout=15,
        min_delay=config.get("min_delay", 2.0),
        max_delay=config.get("max_delay", 5.0)
    )
    
    if error or not content:
        print("  %s: 失败 - %s" % (source_name, error or "无内容"))
        return []
    
    try:
        html = content.decode("utf-8", errors="ignore")
        
        # 使用BeautifulSoup解析（如果可用）
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")
            # 根据源名选择解析策略
            if source_name == "罗戈网":
                return _parse_logclub(soup, config)
            elif source_name == "物流指闻":
                return _parse_headscm(soup, config)
            elif source_name == "亿邦动力":
                return _parse_ebrun(soup, config)
        
        # Fallback: 使用正则解析
        titles = re.findall(config["title_pattern"], html, re.DOTALL)
        titles = [clean_html(t) for t in titles if clean_html(t)]
        
        links = re.findall(config["link_pattern"], html)
        links = [config["base_url"] + l if not l.startswith("http") else l for l in links]
        
        items = []
        for i in range(min(3, len(titles), len(links))):
            items.append({"title": titles[i], "link": links[i]})
        
        print("  [OK] %s: %d条" % (source_name, len(items)))
        return items
        
    except Exception as e:
        print("  %s: 解析失败 - %s" % (source_name, str(e)))
        return []

def _parse_logclub(soup, config):
    """解析罗戈网（BeautifulSoup）"""
    items = []
    # 尝试多种选择器
    selectors = [".news-item", ".article-item", ".list-item", "article", ".item"]
    for selector in selectors:
        elements = soup.select(selector)[:3]
        for elem in elements:
            title_tag = elem.select_one("h3 a, h2 a, .title a, a")
            if title_tag:
                title = clean_html(title_tag.get_text())
                href = title_tag.get("href", "")
                if href and not href.startswith("http"):
                    href = config["base_url"] + href
                if title and href:
                    items.append({"title": title, "link": href})
        if items:
            break
    print("  [OK] 罗戈网: %d条 (BS4)" % len(items))
    return items

def _parse_headscm(soup, config):
    """解析物流指闻（BeautifulSoup）"""
    items = []
    selectors = [".news-list li", ".article-item", ".fingertip-item", "article", ".item"]
    for selector in selectors:
        elements = soup.select(selector)[:3]
        for elem in elements:
            title_tag = elem.select_one("a")
            if title_tag:
                title = clean_html(title_tag.get_text())
                href = title_tag.get("href", "")
                if href and not href.startswith("http"):
                    href = config["base_url"] + href
                if title and href:
                    items.append({"title": title, "link": href})
        if items:
            break
    print("  [OK] 物流指闻: %d条 (BS4)" % len(items))
    return items

def _parse_ebrun(soup, config):
    """解析亿邦动力（BeautifulSoup）"""
    items = []
    selectors = [".news-item", ".article-item", ".list-item", "article", ".item"]
    for selector in selectors:
        elements = soup.select(selector)[:3]
        for elem in elements:
            title_tag = elem.select_one("h4 a, h3 a, h2 a, .title a, a")
            if title_tag:
                title = clean_html(title_tag.get_text())
                href = title_tag.get("href", "")
                if href and not href.startswith("http"):
                    href = config["base_url"] + href
                if title and href:
                    items.append({"title": title, "link": href})
        if items:
            break
    print("  [OK] 亿邦动力: %d条 (BS4)" % len(items))
    return items

# ========== 自动摘要模块 ==========
class ArticleSummarizer:
    """基于规则+关键词的自动摘要生成器"""
    
    # 行业关键词库
    LOGISTICS_KEYWORDS = [
        "物流", "供应链", "快递", "仓储", "配送", "运输", "冷链",
        "无人车", "无人机", "智能仓", "自动化", "数字化", "AI",
        "顺丰", "京东", "菜鸟", "中通", "圆通", "申通", "韵达",
        "美团", "盒马", "亚马逊", "DHL", "FedEx", "UPS",
    ]
    
    TECH_KEYWORDS = [
        "人工智能", "AI", "大模型", "机器人", "自动驾驶", "FSD",
        "芯片", "半导体", "云计算", "区块链", "物联网", "5G",
        "SpaceX", "星舰", "特斯拉", "英伟达", "NVIDIA", "马斯克",
    ]
    
    ECOMMERCE_KEYWORDS = [
        "电商", "跨境电商", "直播带货", "新零售", "社交电商",
        "Netflix", "Amazon", "Temu", "SHEIN", "TikTok",
    ]
    
    @classmethod
    def categorize(cls, title: str, summary: str = "") -> str:
        """文章分类"""
        text = (title + " " + summary).lower()
        
        scores = {
            "物流头条": sum(1 for k in cls.LOGISTICS_KEYWORDS if k in text),
            "国内科技": sum(1 for k in cls.TECH_KEYWORDS if k in text),
            "国际电商": sum(1 for k in cls.ECOMMERCE_KEYWORDS if k in text),
        }
        
        if max(scores.values()) == 0:
            if any(x in text for x in ["china", "chinese", "中国", "国内", "waic"]):
                return "国内科技"
            return "物流头条"
        
        return max(scores, key=scores.get)
    
    @classmethod
    def extract_key_points(cls, title: str, summary: str = "") -> str:
        """提取关键信息点（金额、日期、公司、数据）"""
        text = title + " " + summary
        
        # 提取金额（支持$、¥、€等）
        money_pattern = r"([\$\¥\€\£]?[\d,]+(?:\.\d+)?\s*(?:百万|千万|亿|万|million|billion|M|B)?)"
        money_matches = re.findall(money_pattern, text)
        
        # 提取日期
        date_pattern = r"(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}|\d{1,2}月\d{1,2}日)"
        date_matches = re.findall(date_pattern, text)
        
        # 提取百分比/增长率
        percent_pattern = r"(增长\d+\.?\d*%|下降\d+\.?\d*%|同比\d+\.?\d*%|环比\d+\.?\d*%)"
        percent_matches = re.findall(percent_pattern, text)
        
        # 提取公司名称
        company_pattern = r"(美团|京东|顺丰|菜鸟|中通|圆通|申通|韵达|盒马|山姆|亚马逊|Netflix|SpaceX|特斯拉|英伟达|36氪|TechCrunch|马斯克)"
        company_matches = list(set(re.findall(company_pattern, text)))
        
        key_points = []
        if company_matches:
            key_points.append("涉及: %s" % ", ".join(company_matches[:3]))
        if money_matches:
            key_points.append("金额: %s" % money_matches[0])
        if percent_matches:
            key_points.append("数据: %s" % percent_matches[0])
        if date_matches:
            key_points.append("时间: %s" % date_matches[0])
        
        return " | ".join(key_points) if key_points else "行业动态"

# ========== 新闻抓取主函数 ==========
def fetch_news():
    """抓取所有新闻"""
    news = []
    
    # 抓取RSS源
    for source, url in RSS_SOURCES.items():
        items = fetch_rss(url, source_name=source)
        for item in items:
            news.append({"source": source, "title": item["title"], "link": item["link"]})
    
    # 抓取国内网站
    for source, config in CRAWL_SOURCES.items():
        items = crawl_website(source, config)
        for item in items:
            news.append({"source": source, "title": item["title"], "link": item["link"]})
    
    return news

# ========== 简报生成（增强版，带自动摘要）==========
def generate_bulletin(news_list):
    """生成简报（增强版，带自动摘要）"""
    lines = [
        " 供应链物流日报 | %s" % datetime.now().strftime("%m月%d日"),
        "=" * 30,
        ""
    ]
    
    if not news_list:
        lines.append(" 未抓取成功")
        lines.append("")
        lines.append(" 更新时间: %s" % datetime.now().strftime("%H:%M"))
        return "\n".join(lines)
    
    # 使用自动摘要引擎分类
    categorized = {}
    for item in news_list:
        cat = ArticleSummarizer.categorize(item["title"])
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(item)
    
    # 物流头条
    if "物流头条" in categorized:
        lines.append(" 物流头条")
        for i, item in enumerate(categorized["物流头条"][:2], 1):
            key_points = ArticleSummarizer.extract_key_points(item["title"])
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("   要点: %s" % key_points)
            lines.append("   %s" % item["link"])
            lines.append("")
    
    # 国内科技
    if "国内科技" in categorized:
        lines.append(" 国内科技")
        for i, item in enumerate(categorized["国内科技"][:2], 1):
            key_points = ArticleSummarizer.extract_key_points(item["title"])
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("   要点: %s" % key_points)
            lines.append("   %s" % item["link"])
            lines.append("")
    
    # 国际电商
    if "国际电商" in categorized:
        lines.append("🛒 国际电商")
        for i, item in enumerate(categorized["国际电商"][:2], 1):
            key_points = ArticleSummarizer.extract_key_points(item["title"])
            lines.append("%d. 【%s】%s" % (i, item["source"], item["title"]))
            lines.append("   要点: %s" % key_points)
            lines.append("   %s" % item["link"])
            lines.append("")
    
    lines.append(" 更新时间: %s" % datetime.now().strftime("%H:%M"))
    
    return "\n".join(lines)

# ========== 推送函数（保持不变）==========
def push_serverchan(title, content):
    """推送到微信"""
    key = os.getenv("SERVERCHAN_KEY", "")
    if not key:
        print("未配置SERVERCHAN_KEY")
        return False
    
    url = "https://sctapi.ftqq.com/%s.send" % key
    data = urllib.parse.urlencode({"title": title, "desp": content}).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as response:
            print(" 推送成功: %s" % title)
            return True
    except Exception as e:
        print(" 推送失败: %s" % str(e))
        return False

# ========== 主函数 ==========
def main():
    """主函数"""
    print("=" * 50)
    print(" 任务开始 | %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    
    news = fetch_news()
    print("\n 总共抓取到 %d 条新闻" % len(news))
    
    bulletin = generate_bulletin(news)
    print("\n" + "=" * 50)
    print(bulletin)
    print("=" * 50)
    
    push_serverchan("供应链物流日报", bulletin)
    
    print("\n" + "=" * 50)
    print(" 全部完成")
    print("=" * 50)

if __name__ == "__main__":
    main()

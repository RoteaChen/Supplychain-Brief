# -*- coding: utf-8 -*-
"""
Supply Chain Logistics Daily Briefing Crawler + Daily Recipe
- Separate push for news and recipes
- Fixed formatting
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
import sys
import traceback
import gzip
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

# Optional dependencies
try:
    import feedparser
    FEEDPARSER_OK = True
except ImportError:
    FEEDPARSER_OK = False

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import dns.resolver
    DNS_OK = True
except ImportError:
    DNS_OK = False

# ========== Weekly Recipes Data ==========
WEEKLY_RECIPES = [
    {
        "day": "周一",
        "breakfast": "燕麦水果碗（无糖燕麦+脱脂牛奶，微波2分钟，放蓝莓和几颗坚果）",
        "lunch": "蒜蓉蒸鱼+杂粮饭（鱼柳铺在金针菇娃娃菜上，淋蒜蓉生抽汁，蒸8-10分钟，配一拳头杂粮饭）",
        "dinner": "菌菇豆腐蛋花汤+凉拌鸡丝（少油炒菌菇番茄加水煮开，下豆腐、蛋液，鸡胸肉煮熟撕碎凉拌）",
    },
    {
        "day": "周二",
        "breakfast": "菠菜鸡蛋全麦饼（菠菜焯水切碎，与鸡蛋液搅匀，刷薄油摊熟，用全麦饼卷起）",
        "lunch": "番茄花菜炒饭（花菜打碎代米饭，炒熟鸡蛋盛出，番茄炒出汁，加虾仁和花菜碎翻炒，混入蛋）",
        "dinner": "黑椒牛柳炒芦笋+糙米饭（牛里脊切条滑炒，下芦笋大火炒，配半拳糙米饭）",
    },
    {
        "day": "周三",
        "breakfast": "水煮蛋2个+蒸红薯（小半个）+圣女果",
        "lunch": "香煎鸡胸+西兰花+糙米饭（鸡胸片用黑胡椒盐腌，少油煎熟，西兰花焯水，一拳头糙米饭）",
        "dinner": "白灼虾+凉拌黄瓜木耳+杂粮饭（虾沸水煮红，黄瓜木耳加醋生抽拌，半拳杂粮饭）",
    },
    {
        "day": "周四",
        "breakfast": "无糖酸奶+燕麦片+坚果碎+蓝莓",
        "lunch": "蒜蓉蒸鱼+杂粮饭（鱼柳搭配芥蓝或娃娃菜，同样蒜蓉蒸制）",
        "dinner": "番茄豆腐汤+蒸南瓜（番茄炒出汤加水，下嫩豆腐和小白菜，配几块蒸南瓜）",
    },
    {
        "day": "周五",
        "breakfast": "全麦吐司1片（抹无糖花生酱）+滑蛋+黄瓜条",
        "lunch": "黑椒牛柳炒芦笋+藜麦饭（做法同周二晚餐，主食换藜麦饭）",
        "dinner": "大拌菜（生菜、紫甘蓝、鸡丝、玉米粒，淋油醋汁）",
    },
    {
        "day": "周六",
        "breakfast": "菠菜鸡蛋全麦饼",
        "lunch": "番茄花菜炒饭（加鸡肉丁）",
        "dinner": "清蒸鳕鱼+炒时蔬+杂粮饭（鳕鱼放姜丝蒸8分钟，蒜蓉炒任意绿叶菜，半拳杂粮饭）",
    },
    {
        "day": "周日",
        "breakfast": "燕麦水果碗",
        "lunch": "牛肉末烧豆腐+凉拌黄瓜+糙米饭（瘦牛肉末少油炒香，加嫩豆腐和少许水炖煮，生抽调味）",
        "dinner": "菌菇豆腐蛋花汤+少量荞麦面（汤底同周一，下少许荞麦面煮熟，面量控制在半拳）",
    },
]

# ========== RSS Sources ==========
RSS_SOURCES = {
    "Talking Logistics": "https://talkinglogistics.com/feed/",
    "Supply Chain Dive": "https://www.supplychaindive.com/feeds/news/",
    "FreightWaves": "https://www.freightwaves.com/feed",
    "36Kr": "https://36kr.com/feed",
    "TechCrunch": "https://techcrunch.com/feed/",
    "Logistics Management": "https://www.logisticsmgmt.com/rss.xml",
    "Supply Chain Brain": "https://www.supplychainbrain.com/rss.xml",
    "Transport Topics": "https://www.ttnews.com/rss.xml",
}

# ========== Crawl Sources ==========
CRAWL_SOURCES = {
    "Ebrun": {
        "url": "https://www.ebrun.com",
        "title_pattern": r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        "link_pattern": r'<a[^>]*href="(/202\d+/\d+/[^"]+\.s?html)"[^>]*>',
        "base_url": "https://www.ebrun.com",
        "retry_count": 3,
        "min_delay": 3.0,
        "max_delay": 6.0,
    },
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
]

BLOCK_SIGNALS = [
    "access denied", "captcha", "blocked", "forbidden",
    "cloudflare", "verification", "too frequent", "login",
]

# ========== DNS Fix ==========
def resolve_with_fallback(hostname: str) -> Optional[str]:
    try:
        ip = socket.gethostbyname(hostname)
        print("  [DNS] %s -> %s (system)" % (hostname, ip))
        return ip
    except socket.gaierror:
        pass
    if DNS_OK:
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
    print("  [DNS] Failed to resolve %s" % hostname)
    return None

def patch_dns_for_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return url
    ip = resolve_with_fallback(hostname)
    if ip:
        return url
    if hostname.startswith("www."):
        alt = hostname[4:]
    else:
        alt = "www." + hostname
    ip = resolve_with_fallback(alt)
    if ip:
        new_netloc = alt
        if parsed.port:
            new_netloc += ":" + str(parsed.port)
        return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))
    return url

# ========== Enhanced Request ==========
class EnhancedRequest:
    def __init__(self):
        self.last_request_time = 0
        self.request_count = 0
    def _get_random_ua(self) -> str:
        return random.choice(USER_AGENTS)
    def _random_delay(self, min_sec: float, max_sec: float):
        delay = random.uniform(min_sec, max_sec)
        delay += random.gauss(0, 0.3)
        delay = max(0.5, delay)
        time.sleep(delay)
    def _decode_content(self, content: bytes, headers) -> bytes:
        encoding = headers.get("Content-Encoding", "").lower()
        if encoding == "gzip":
            try:
                return gzip.decompress(content)
            except Exception:
                return content
        elif encoding == "deflate":
            try:
                import zlib
                return zlib.decompress(content)
            except Exception:
                return content
        return content
    def fetch(self, url: str, source_name: str = "", retry_count: int = 3,
              timeout: int = 15, min_delay: float = 2.0, max_delay: float = 5.0) -> Tuple[Optional[bytes], Optional[str]]:
        original_url = url
        for attempt in range(retry_count):
            try:
                elapsed = time.time() - self.last_request_time
                if elapsed < min_delay:
                    time.sleep(min_delay - elapsed + random.uniform(0, 1))
                if attempt > 0 or "ebrun" in url:
                    url = patch_dns_for_url(original_url)
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self._get_random_ua(),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept-Encoding": "gzip, deflate",
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
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                opener = urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ssl_context)
                )
                print("  Requesting %s (attempt %d/%d)..." % (source_name or url, attempt + 1, retry_count))
                response = opener.open(req, timeout=timeout)
                status = response.getcode()
                if status != 200:
                    print("  HTTP %d, retrying..." % status)
                    continue
                content = response.read()
                content = self._decode_content(content, response.headers)
                if len(content) < 100:
                    print("  Content too short (%d bytes), retrying..." % len(content))
                    continue
                content_str = content.decode("utf-8", errors="ignore").lower()
                if any(sig in content_str for sig in BLOCK_SIGNALS):
                    print("  Anti-crawler detected, retrying...")
                    time.sleep(2 ** attempt + random.uniform(1, 3))
                    continue
                self.last_request_time = time.time()
                self.request_count += 1
                print("  [OK] Fetched %d bytes" % len(content))
                preview = content.decode("utf-8", errors="ignore")[:200].replace("\n", " ")
                print("  [Preview] %s..." % preview)
                return content, None
            except urllib.error.HTTPError as e:
                print("  HTTP error %d: %s" % (e.code, e.reason))
                if e.code == 403:
                    time.sleep(2 ** attempt + random.uniform(1, 3))
                elif e.code == 429:
                    time.sleep(5 * (attempt + 1))
                else:
                    time.sleep(2 ** attempt)
            except urllib.error.URLError as e:
                error_msg = str(e.reason)
                print("  URL error: %s" % error_msg)
                if "Name or service not known" in error_msg or "getaddrinfo" in error_msg:
                    print("  [DNS Fix] Trying backup...")
                    if original_url.startswith("https://www."):
                        original_url = original_url.replace("https://www.", "https://")
                    elif original_url.startswith("https://") and not original_url.startswith("https://www."):
                        original_url = original_url.replace("https://", "https://www.")
                    time.sleep(3)
                else:
                    time.sleep(2 ** attempt)
            except socket.timeout:
                print("  Request timeout")
                time.sleep(2 ** attempt + 2)
            except Exception as e:
                print("  Unknown error: %s" % str(e))
                time.sleep(2 ** attempt)
        return None, "All %d attempts failed" % retry_count

# ========== Utils ==========
def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip()
    return text

def fetch_rss(url, source_name=""):
    fetcher = EnhancedRequest()
    content, error = fetcher.fetch(url, source_name=source_name, retry_count=3, min_delay=1.0, max_delay=2.0)
    if error or not content:
        print("RSS failed: %s" % (error or "no content"))
        return []
    try:
        content_str = content.decode("utf-8", errors="ignore")
    except Exception:
        content_str = str(content)
    if not content_str.strip().startswith(("<?xml", "<rss", "<feed")):
        print("  [Warning] Content does not look like RSS/XML")
        print("  [Content start] %s" % content_str[:100])
    if FEEDPARSER_OK:
        try:
            feed = feedparser.parse(content)
            items = []
            for entry in feed.entries[:5]:
                title = clean_html(entry.get("title", ""))
                link = clean_html(entry.get("link", ""))
                if title and link:
                    items.append({"title": title, "link": link})
            if items:
                print("  [RSS] %s: %d items via feedparser" % (source_name, len(items)))
                return items
        except Exception as e:
            print("feedparser failed: %s, using fallback" % str(e))
    try:
        if content_str.startswith("\ufeff"):
            content_str = content_str[1:]
        root = ET.fromstring(content_str.encode("utf-8"))
        items = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            title = clean_html(title_elem.text) if title_elem is not None else ""
            link = item.find("link")
            link_text = clean_html(link.text) if link is not None else ""
            if not link_text:
                guid = item.find("guid")
                if guid is not None and guid.text:
                    link_text = clean_html(guid.text)
            if title and link_text:
                items.append({"title": title, "link": link_text})
        if not items:
            for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
                title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
                title = clean_html(title_elem.text) if title_elem is not None else ""
                link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                link_text = ""
                if link_elem is not None:
                    link_text = link_elem.get("href", "")
                if title and link_text:
                    items.append({"title": title, "link": link_text})
        if items:
            print("  [RSS] %s: %d items via XML fallback" % (source_name, len(items)))
        return items[:5]
    except Exception as e:
        print("RSS fallback failed: %s" % str(e))
        return []

def crawl_website(source_name, config):
    print("Crawling: %s" % source_name)
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
        print("  %s: Failed - %s" % (source_name, error or "no content"))
        return []
    try:
        html = content.decode("utf-8", errors="ignore")
        print("  [HTML Preview] %s..." % html[:300].replace("\n", " "))
        if BS4_OK:
            soup = BeautifulSoup(html, "html.parser")
            selectors = [".news-item", ".article-item", ".list-item", "article", ".item", ".post", ".entry"]
            for selector in selectors:
                elements = soup.select(selector)[:5]
                items = []
                for elem in elements:
                    title_tag = elem.select_one("h3 a, h2 a, h4 a, .title a, a, h3, h2, h4")
                    if title_tag:
                        title = clean_html(title_tag.get_text())
                        href = title_tag.get("href", "") if title_tag.name == "a" else ""
                        if not href:
                            a_tag = elem.find("a")
                            if a_tag:
                                href = a_tag.get("href", "")
                        if href and not href.startswith("http"):
                            href = config["base_url"] + href
                        if title and href:
                            items.append({"title": title, "link": href})
                if items:
                    print("  [OK] %s: %d items (BS4)" % (source_name, len(items)))
                    return items
        titles = re.findall(config["title_pattern"], html, re.DOTALL | re.IGNORECASE)
        titles = [clean_html(t) for t in titles if clean_html(t)]
        links = re.findall(config["link_pattern"], html, re.IGNORECASE)
        links = [config["base_url"] + l if not l.startswith("http") else l for l in links]
        if not links:
            generic_links = re.findall(r'<a[^>]*href="(/[^"]+)"[^>]*>', html)
            links = [config["base_url"] + l if not l.startswith("http") else l for l in generic_links[:5]]
        items = []
        for i in range(min(5, len(titles), len(links))):
            items.append({"title": titles[i], "link": links[i]})
        if items:
            print("  [OK] %s: %d items (regex)" % (source_name, len(items)))
        else:
            print("  [Warning] %s: No items extracted (titles=%d, links=%d)" % (source_name, len(titles), len(links)))
        return items
    except Exception as e:
        print("  %s: Parse failed - %s" % (source_name, str(e)))
        traceback.print_exc()
        return []

# ========== Recipe Manager ==========
class RecipeManager:
    @classmethod
    def get_state_file(cls) -> str:
        state_dir = os.path.expanduser("~/.supplychain-brief")
        if not os.path.exists(state_dir):
            os.makedirs(state_dir)
        return os.path.join(state_dir, "recipe_state.json")

    @classmethod
    def load_state(cls) -> Dict:
        state_file = cls.get_state_file()
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"week_start": "", "used_indices": []}

    @classmethod
    def save_state(cls, state: Dict):
        state_file = cls.get_state_file()
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception as e:
            print("  [Warning] Failed to save recipe state: %s" % str(e))

    @classmethod
    def get_week_start(cls) -> str:
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.strftime("%Y-%m-%d")

    @classmethod
    def get_today_recipe(cls) -> Optional[Dict]:
        today = datetime.now()
        weekday = today.weekday()
        print("  [Recipe] Today is weekday %d" % weekday)
        current_week = cls.get_week_start()
        state = cls.load_state()
        if state.get("week_start") != current_week:
            state = {"week_start": current_week, "used_indices": []}
            print("  [Recipe] New week started: %s" % current_week)
        used = state.get("used_indices", [])
        available = [i for i in range(len(WEEKLY_RECIPES)) if i not in used]
        if not available:
            print("  [Recipe] All recipes used this week, resetting...")
            used = []
            available = list(range(len(WEEKLY_RECIPES)))
        selected_idx = random.choice(available)
        used.append(selected_idx)
        state["used_indices"] = used
        cls.save_state(state)
        recipe = WEEKLY_RECIPES[selected_idx]
        print("  [Recipe] Selected: %s (used: %s)" % (recipe["day"], used))
        return recipe

    @classmethod
    def format_recipe(cls, recipe: Dict) -> str:
        lines = []
        lines.append("今日减脂食谱 | %s" % recipe["day"])
        lines.append("=" * 30)
        lines.append("")
        lines.append("[早餐] %s" % recipe["breakfast"])
        lines.append("")
        lines.append("[午餐] %s" % recipe["lunch"])
        lines.append("")
        lines.append("[晚餐] %s" % recipe["dinner"])
        lines.append("")
        lines.append("Updated: %s" % datetime.now().strftime("%H:%M"))
        return "\n".join(lines)

# ========== Auto Summary ==========
class ArticleSummarizer:
    LOGISTICS_KEYWORDS = [
        "logistics", "supply chain", "express", "warehouse", "delivery", "transport",
        "unmanned", "drone", "smart warehouse", "automation", "digital", "AI",
        "SF", "JD", "Cainiao", "ZTO", "YTO", "STO", "Yunda",
        "Meituan", "Hema", "Amazon", "DHL", "FedEx", "UPS",
    ]
    TECH_KEYWORDS = [
        "artificial intelligence", "AI", "large model", "robot", "autonomous driving", "FSD",
        "chip", "semiconductor", "cloud computing", "blockchain", "IoT", "5G",
        "SpaceX", "Starship", "Tesla", "NVIDIA", "Musk",
    ]
    ECOMMERCE_KEYWORDS = [
        "e-commerce", "cross-border", "live streaming", "new retail", "social commerce",
        "Netflix", "Amazon", "Temu", "SHEIN", "TikTok",
    ]
    @classmethod
    def categorize(cls, title: str, summary: str = "") -> str:
        text = (title + " " + summary).lower()
        scores = {
            "Logistics Headlines": sum(1 for k in cls.LOGISTICS_KEYWORDS if k in text),
            "Domestic Tech": sum(1 for k in cls.TECH_KEYWORDS if k in text),
            "International E-commerce": sum(1 for k in cls.ECOMMERCE_KEYWORDS if k in text),
        }
        if max(scores.values()) == 0:
            if any(x in text for x in ["china", "chinese", "domestic", "waic"]):
                return "Domestic Tech"
            return "Logistics Headlines"
        return max(scores, key=scores.get)
    @classmethod
    def extract_key_points(cls, title: str, summary: str = "") -> str:
        text = title + " " + summary
        money_pattern = r"([\$\¥\€\£]?[\d,]+(?:\.\d+)?\s*(?:million|billion|M|B)?)"
        money_matches = re.findall(money_pattern, text)
        date_pattern = r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})"
        date_matches = re.findall(date_pattern, text)
        company_pattern = r"(Meituan|JD|SF|Cainiao|ZTO|YTO|STO|Yunda|Hema|Amazon|Netflix|SpaceX|Tesla|NVIDIA|36Kr|TechCrunch|Musk)"
        company_matches = list(set(re.findall(company_pattern, text)))
        key_points = []
        if company_matches:
            key_points.append("Involved: %s" % ", ".join(company_matches[:3]))
        if money_matches:
            key_points.append("Amount: %s" % money_matches[0])
        if date_matches:
            key_points.append("Date: %s" % date_matches[0])
        return " | ".join(key_points) if key_points else "Industry News"

# ========== Main Functions ==========
def fetch_news():
    news = []
    rss_success = 0
    crawl_success = 0
    print("\n=== Fetching RSS Sources ===")
    for source, url in RSS_SOURCES.items():
        print("Fetching RSS: %s" % source)
        items = fetch_rss(url, source_name=source)
        if items:
            rss_success += 1
            for item in items:
                news.append({"source": source, "title": item["title"], "link": item["link"]})
        print("  Total items so far: %d" % len(news))
    print("\n=== Crawling Websites ===")
    for source, config in CRAWL_SOURCES.items():
        items = crawl_website(source, config)
        if items:
            crawl_success += 1
            for item in items:
                news.append({"source": source, "title": item["title"], "link": item["link"]})
        print("  Total items so far: %d" % len(news))
    print("\n=== Summary ===")
    print("RSS sources succeeded: %d/%d" % (rss_success, len(RSS_SOURCES)))
    print("Crawl sources succeeded: %d/%d" % (crawl_success, len(CRAWL_SOURCES)))
    print("Total articles fetched: %d" % len(news))
    return news

def generate_news_bulletin(news_list):
    lines = [
        "Supply Chain Logistics Daily | %s" % datetime.now().strftime("%m/%d"),
        "=" * 30,
        ""
    ]
    if not news_list:
        lines.append("No news fetched - all sources failed or returned empty")
        lines.append("Please check logs for details")
        lines.append("")
    else:
        categorized = {}
        for item in news_list:
            cat = ArticleSummarizer.categorize(item["title"])
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(item)
        if "Logistics Headlines" in categorized:
            lines.append("Logistics Headlines")
            for i, item in enumerate(categorized["Logistics Headlines"][:3], 1):
                key_points = ArticleSummarizer.extract_key_points(item["title"])
                lines.append("%d. [%s] %s" % (i, item["source"], item["title"]))
                lines.append("   Key: %s" % key_points)
                lines.append("   %s" % item["link"])
                lines.append("")
        if "Domestic Tech" in categorized:
            lines.append("Domestic Tech")
            for i, item in enumerate(categorized["Domestic Tech"][:3], 1):
                key_points = ArticleSummarizer.extract_key_points(item["title"])
                lines.append("%d. [%s] %s" % (i, item["source"], item["title"]))
                lines.append("   Key: %s" % key_points)
                lines.append("   %s" % item["link"])
                lines.append("")
        if "International E-commerce" in categorized:
            lines.append("International E-commerce")
            for i, item in enumerate(categorized["International E-commerce"][:3], 1):
                key_points = ArticleSummarizer.extract_key_points(item["title"])
                lines.append("%d. [%s] %s" % (i, item["source"], item["title"]))
                lines.append("   Key: %s" % key_points)
                lines.append("   %s" % item["link"])
                lines.append("")
    lines.append("Updated: %s" % datetime.now().strftime("%H:%M"))
    return "\n".join(lines)

def generate_recipe_bulletin() -> str:
    print("\n=== Generating Recipe ===")
    recipe = RecipeManager.get_today_recipe()
    if recipe:
        return RecipeManager.format_recipe(recipe)
    return "今日无食谱"

def push_serverchan(title, content):
    key = os.getenv("SERVERCHAN_KEY", "")
    if not key:
        print("SERVERCHAN_KEY not set")
        return False
    url = "https://sctapi.ftqq.com/%s.send" % key
    data = urllib.parse.urlencode({"title": title, "desp": content}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as response:
            print("Push OK: %s" % title)
            return True
    except Exception as e:
        print("Push failed: %s" % str(e))
        return False

def main():
    print("=" * 50)
    print("Task started | %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 50)
    print("Dependencies: dnspython=%s, bs4=%s, feedparser=%s" % (DNS_OK, BS4_OK, FEEDPARSER_OK))

    try:
        # 1. Fetch and push news
        news = fetch_news()
        news_bulletin = generate_news_bulletin(news)
        print("\n" + "=" * 50)
        print("NEWS BULLETIN:")
        print(news_bulletin)
        print("=" * 50)
        push_serverchan("Supply Chain Daily Briefing", news_bulletin)

        # 2. Generate and push recipe
        recipe_bulletin = generate_recipe_bulletin()
        print("\n" + "=" * 50)
        print("RECIPE BULLETIN:")
        print(recipe_bulletin)
        print("=" * 50)
        push_serverchan("今日减脂食谱", recipe_bulletin)

    except Exception as e:
        print("\n" + "=" * 50)
        print("FATAL ERROR: %s" % str(e))
        print("=" * 50)
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 50)
    print("All done")
    print("=" * 50)

if __name__ == "__main__":
    main()

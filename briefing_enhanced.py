# -*- coding: utf-8 -*-
"""
Supply Chain Logistics Daily Briefing Crawler - Enhanced
Fixes: DNS resolution, anti-crawler bypass, smart retry, auto summary
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
import xml.etree.ElementTree as ET
from datetime import datetime
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

# ========== RSS Sources ==========
RSS_SOURCES = {
    "Talking Logistics": "https://talkinglogistics.com/feed/",
    "Supply Chain Dive": "https://www.supplychaindive.com/feeds/news/",
    "FreightWaves": "https://www.freightwaves.com/feed",
    "36Kr": "https://36kr.com/feed",
    "TechCrunch": "https://techcrunch.com/feed/",
}

# ========== Crawl Sources (China sites) ==========
CRAWL_SOURCES = {
    "Logclub": {
        "url": "https://www.logclub.com",
        "title_pattern": r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        "link_pattern": r'<a[^>]*href="(/news/\d+)"[^>]*>',
        "base_url": "https://www.logclub.com",
        "retry_count": 3,
        "min_delay": 3.0,
        "max_delay": 6.0,
    },
    "Logistics Zhiwen": {
        "url": "https://www.headscm.com",
        "title_pattern": r'<h2[^>]*>(.*?)</h2>',
        "link_pattern": r'<a[^>]*href="(/article/\d+)"[^>]*>',
        "base_url": "https://www.headscm.com",
        "retry_count": 5,
        "min_delay": 2.0,
        "max_delay": 4.0,
    },
    "Ebrun": {
        "url": "https://www.ebrun.com",
        "title_pattern": r'<h4[^>]*>(.*?)</h4>',
        "link_pattern": r'<a[^>]*href="(/202\d+/\d+/\d+/\d+\.shtml)"[^>]*>',
        "base_url": "https://www.ebrun.com",
        "retry_count": 3,
        "min_delay": 3.0,
        "max_delay": 6.0,
    },
}

# ========== User-Agent Pool ==========
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
    "cloudflare", "verification", "too frequent",
]

# ========== DNS Fix ==========
def resolve_with_fallback(hostname: str) -> Optional[str]:
    """Multi-DNS resolution to fix [Errno -2]"""
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
    """Try DNS pre-resolution and domain variants"""
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
    def fetch(self, url: str, source_name: str = "", retry_count: int = 3,
              timeout: int = 15, min_delay: float = 2.0, max_delay: float = 5.0) -> Tuple[Optional[bytes], Optional[str]]:
        original_url = url
        for attempt in range(retry_count):
            try:
                elapsed = time.time() - self.last_request_time
                if elapsed < min_delay:
                    time.sleep(min_delay - elapsed + random.uniform(0, 1))
                if attempt > 0 or "headscm" in url or "logclub" in url or "ebrun" in url:
                    url = patch_dns_for_url(original_url)
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
    if FEEDPARSER_OK:
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
            print("feedparser failed: %s, using fallback" % str(e))
    try:
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
        if BS4_OK:
            soup = BeautifulSoup(html, "html.parser")
            selectors = [".news-item", ".article-item", ".list-item", "article", ".item"]
            for selector in selectors:
                elements = soup.select(selector)[:3]
                items = []
                for elem in elements:
                    title_tag = elem.select_one("h3 a, h2 a, h4 a, .title a, a")
                    if title_tag:
                        title = clean_html(title_tag.get_text())
                        href = title_tag.get("href", "")
                        if href and not href.startswith("http"):
                            href = config["base_url"] + href
                        if title and href:
                            items.append({"title": title, "link": href})
                if items:
                    print("  [OK] %s: %d items (BS4)" % (source_name, len(items)))
                    return items
        titles = re.findall(config["title_pattern"], html, re.DOTALL)
        titles = [clean_html(t) for t in titles if clean_html(t)]
        links = re.findall(config["link_pattern"], html)
        links = [config["base_url"] + l if not l.startswith("http") else l for l in links]
        items = []
        for i in range(min(3, len(titles), len(links))):
            items.append({"title": titles[i], "link": links[i]})
        print("  [OK] %s: %d items (regex)" % (source_name, len(items)))
        return items
    except Exception as e:
        print("  %s: Parse failed - %s" % (source_name, str(e)))
        return []

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
    @classmethod
    def generate_bullet_summary(cls, articles: List[Dict]) -> str:
        categorized = {}
        for article in articles:
            cat = cls.categorize(article.get("title", ""), article.get("summary", ""))
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(article)
        lines = []
        lines.append("Supply Chain Logistics Daily | %s" % datetime.now().strftime("%Y-%m-%d"))
        lines.append("=" * 40)
        for category, items in categorized.items():
            emoji_map = {"Logistics Headlines": "📰", "Domestic Tech": "🔬", "International E-commerce": "🛒"}
            emoji = emoji_map.get(category, "📌")
            lines.append("
%s %s" % (emoji, category))
            lines.append("-" * 30)
            for i, item in enumerate(items[:5], 1):
                title = item.get("title", "")
                link = item.get("link", "")
                key_points = cls.extract_key_points(title, item.get("summary", ""))
                lines.append("%d. %s" % (i, title))
                lines.append("   Key: %s" % key_points)
                if link:
                    lines.append("   Link: %s" % link)
                lines.append("")
        return "
".join(lines)

# ========== Main Functions ==========
def fetch_news():
    news = []
    for source, url in RSS_SOURCES.items():
        items = fetch_rss(url, source_name=source)
        for item in items:
            news.append({"source": source, "title": item["title"], "link": item["link"]})
    for source, config in CRAWL_SOURCES.items():
        items = crawl_website(source, config)
        for item in items:
            news.append({"source": source, "title": item["title"], "link": item["link"]})
    return news

def generate_bulletin(news_list):
    lines = [
        "Supply Chain Logistics Daily | %s" % datetime.now().strftime("%m/%d"),
        "=" * 30,
        ""
    ]
    if not news_list:
        lines.append("No news fetched")
        lines.append("")
        lines.append("Updated: %s" % datetime.now().strftime("%H:%M"))
        return "
".join(lines)
    categorized = {}
    for item in news_list:
        cat = ArticleSummarizer.categorize(item["title"])
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(item)
    if "Logistics Headlines" in categorized:
        lines.append("Logistics Headlines")
        for i, item in enumerate(categorized["Logistics Headlines"][:2], 1):
            key_points = ArticleSummarizer.extract_key_points(item["title"])
            lines.append("%d. [%s] %s" % (i, item["source"], item["title"]))
            lines.append("   Key: %s" % key_points)
            lines.append("   %s" % item["link"])
            lines.append("")
    if "Domestic Tech" in categorized:
        lines.append("Domestic Tech")
        for i, item in enumerate(categorized["Domestic Tech"][:2], 1):
            key_points = ArticleSummarizer.extract_key_points(item["title"])
            lines.append("%d. [%s] %s" % (i, item["source"], item["title"]))
            lines.append("   Key: %s" % key_points)
            lines.append("   %s" % item["link"])
            lines.append("")
    if "International E-commerce" in categorized:
        lines.append("International E-commerce")
        for i, item in enumerate(categorized["International E-commerce"][:2], 1):
            key_points = ArticleSummarizer.extract_key_points(item["title"])
            lines.append("%d. [%s] %s" % (i, item["source"], item["title"]))
            lines.append("   Key: %s" % key_points)
            lines.append("   %s" % item["link"])
            lines.append("")
    lines.append("Updated: %s" % datetime.now().strftime("%H:%M"))
    return "
".join(lines)

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
    news = fetch_news()
    print("
Total %d articles fetched" % len(news))
    bulletin = generate_bulletin(news)
    print("
" + "=" * 50)
    print(bulletin)
    print("=" * 50)
    push_serverchan("Supply Chain Daily Briefing", bulletin)
    print("
" + "=" * 50)
    print("All done")
    print("=" * 50)

if __name__ == "__main__":
    main()

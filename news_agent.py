#!/usr/bin/env python3
"""Physical AI Daily News Agent
Presidio Ventures 経営層向け Physical AI デイリーニュース配信システム
"""

import os
import sys
import smtplib
import logging
import re
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser
import anthropic
from ddgs import DDGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    # ロボティクス・Physical AI 専門
    "IEEE Spectrum Robotics":       "https://spectrum.ieee.org/feeds/blog/automaton.rss",
    "The Robot Report":             "https://www.therobotreport.com/feed/",
    "Robotics Business Review":     "https://www.roboticsbusinessreview.com/feed/",
    "New Atlas Robotics":           "https://newatlas.com/robotics/rss/",
    "The Verge Robots":             "https://www.theverge.com/rss/robot/index.xml",
    "Automation World":             "https://www.automationworld.com/rss.xml",
    "Control Engineering":          "https://www.controleng.com/rss",
    "IndustryWeek":                 "https://www.industryweek.com/rss/all",
    "Wired Robots":                 "https://www.wired.com/feed/tag/robots/rss",
    # 信頼できる主要メディア（優先）
    "Bloomberg Technology":         "https://feeds.bloomberg.com/technology/news.rss",
    "Bloomberg Business":           "https://feeds.bloomberg.com/businessweek/news.rss",
    "WSJ Tech":                     "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "WSJ Business":                 "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    "Forbes Innovation":            "https://www.forbes.com/innovation/feed/",
    "Forbes AI":                    "https://www.forbes.com/ai/feed/",
    "Nikkei Asia":                  "https://asia.nikkei.com/rss/feed/nar",
    "Financial Times Tech":         "https://www.ft.com/technology?format=rss",
    # 投資・スタートアップ
    "TechCrunch Robotics":          "https://techcrunch.com/tag/robotics/feed/",
    "TechCrunch Funding":           "https://techcrunch.com/category/fundings-exits/feed/",
    "Crunchbase News":              "https://news.crunchbase.com/feed/",
    # テック企業
    "NVIDIA Blog":                  "https://blogs.nvidia.com/feed/",
    "MIT Technology Review":        "https://www.technologyreview.com/feed/",
    "VentureBeat AI":               "https://venturebeat.com/ai/feed/",
    "Ars Technica":                 "https://feeds.arstechnica.com/arstechnica/index",
    # 日本語メディア
    "ロボスタ":                     "https://robosta.net/feed/",
    "マイナビ ロボット":            "https://news.mynavi.jp/rss/techplus/robot/index_rss20.xml",
    "日経クロステック":             "https://xtech.nikkei.com/rss/index.rdf",
    "ITmedia AI+":                  "https://rss.itmedia.co.jp/rss/2.0/ait.xml",
}

SEARCH_QUERIES = [
    "site:bloomberg.com humanoid robot robotics AI investment 2026",
    "site:wsj.com robotics automation Physical AI 2026",
    "site:forbes.com robotics humanoid robot funding 2026",
    "site:asia.nikkei.com robot automation AI manufacturing 2026",
    "humanoid robot funding acquisition partnership news 2026",
    "Physical AI embodied AI startup investment 2026",
    "Figure 1X Agility Apptronik Boston Dynamics robot news 2026",
]


def fetch_rss_articles(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    articles = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                pub = None
                if getattr(entry, "published_parsed", None):
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                if pub and pub < cutoff:
                    continue

                title = entry.get("title", "")
                summary = re.sub(r"<[^>]+>", "", entry.get("summary", entry.get("description", ""))[:600])

                articles.append({
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": summary,
                })
        except Exception as e:
            log.warning(f"フィード取得エラー [{source}]: {e}")

    log.info(f"RSS: {len(articles)} 件取得")
    return articles


def fetch_web_articles() -> list[dict]:
    articles = []
    seen_urls = set()

    try:
        with DDGS() as ddgs:
            for query in SEARCH_QUERIES:
                try:
                    for r in ddgs.text(query, max_results=5):
                        url = r.get("href", "")
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        articles.append({
                            "source": "Web Search",
                            "title": r.get("title", ""),
                            "link": url,
                            "summary": r.get("body", "")[:500],
                        })
                except Exception as e:
                    log.warning(f"検索エラー: {e}")
    except Exception as e:
        log.warning(f"Web検索全体エラー: {e}")

    log.info(f"Web検索: {len(articles)} 件取得")
    return articles


def curate_and_summarize(articles: list[dict]) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    articles_block = "\n\n".join(
        f"[{i+1}] 【{a['source']}】{a['title']}\nURL: {a['link']}\n概要: {a['summary']}"
        for i, a in enumerate(articles)
    )

    today_str = datetime.now(tz=JST).strftime("%Y年%m月%d日")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4500,
        system=(
            "あなたはベンチャーキャピタル・経営層向けに「Physical AI デイリーニュース」を編集する専門家です。"
            "投資・事業開発・技術動向の観点から、経営判断に直結する情報を正確かつ簡潔な日本語でまとめてください。"
        ),
        messages=[{
            "role": "user",
            "content": f"""以下は {today_str} に収集した世界中のニュース記事です。

{articles_block}

【対象分野】以下の分野のみを対象とする：
✅ Physical AI（物理世界で動くAI）
✅ Humanoid Robot（ヒューマノイドロボット）
✅ Robotics（ロボティクス全般）
✅ Embedded AI（組み込みAI・エッジAI）
✅ Automation（産業・物流・医療・農業の自動化）

【除外】
❌ 生成AI（ChatGPT、LLM、画像生成など純粋なソフトウェアAI）
❌ Physical AIと無関係なソフトウェア・クラウド・サービス系ニュース

【優先順位】
1. 💰 投資・資金調達
2. 🤝 M&A・買収・合併・パートナーシップ
3. 🚀 製品発表・技術ブレークスルー
4. 📊 市場動向・規制・業界再編

【重要】合計10件前後のニュースを掲載すること。記事が多い場合は重要度順に選別。

以下の形式で作成してください：

---
# 🤖 Physical AI デイリーニュース｜{today_str}

## 💰 投資・M&A・パートナーシップ
（該当があれば最優先。最大5件）

### 1. [日本語タイトル]
- **メディア**: [ソース名]
- **概要**: [金額・企業名・規模を明記。3文以内]
- **インパクト**: [業界への影響1文]
- 🔗 [URL]

---

## 🚀 技術・製品・事業ニュース
（最大7件）

### 1. [日本語タイトル]
- **メディア**: [ソース名]
- **概要**: [3文以内]
- **インパクト**: [1文]
- 🔗 [URL]

---

## 📊 本日のまとめ
[トレンドと経営層が注目すべき点を4〜5文で総括]

---
*Physical AI News Agent | {today_str} 07:00 JST*"""
        }]
    )

    return response.content[0].text


def to_html(text: str) -> str:
    h = text
    h = re.sub(r"^# (.+)$", r"<h1>\1</h1>", h, flags=re.M)
    h = re.sub(r"^## (.+)$", r"<h2>\1</h2>", h, flags=re.M)
    h = re.sub(r"^### (.+)$", r"<h3>\1</h3>", h, flags=re.M)
    h = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", h)
    h = re.sub(r"---+", "<hr>", h)
    h = re.sub(r"^- (.+)$", r"<li>\1</li>", h, flags=re.M)
    h = h.replace("\n", "<br>\n")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  body{{font-family:'Helvetica Neue',Arial,sans-serif;max-width:760px;margin:0 auto;padding:24px;color:#202124;line-height:1.8}}
  h1{{color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px}}
  h2{{color:#333;margin-top:28px}}
  h3{{color:#1a73e8;margin-top:20px}}
  hr{{border:none;border-top:1px solid #e0e0e0;margin:20px 0}}
  li{{margin:6px 0}}
  a{{color:#1a73e8}}
</style></head><body>{h}</body></html>"""


def send_email(subject: str, html: str, plain: str) -> None:
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("TO_EMAIL", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Physical AI News <{user}>"
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, password)
        s.sendmail(user, to, msg.as_string())
    log.info(f"送信完了 → {to}")


def main() -> None:
    log.info("=== Physical AI News Agent 起動 ===")

    today_jst = datetime.now(tz=JST)
    hours = 78 if today_jst.weekday() == 0 else 24
    log.info(f"取得期間: 過去{hours}時間（{['月','火','水','木','金','土','日'][today_jst.weekday()]}曜日）")

    rss_articles = fetch_rss_articles(hours=hours)
    web_articles = fetch_web_articles()
    articles = rss_articles + web_articles

    if not articles:
        log.error("記事が取得できませんでした")
        sys.exit(1)

    log.info(f"合計: {len(articles)} 件")
    summary = curate_and_summarize(articles)

    today = datetime.now(tz=JST).strftime("%Y年%m月%d日")
    send_email(
        subject=f"⚙️ Physical AI デイリーニュース｜{today}",
        html=to_html(summary),
        plain=summary,
    )
    log.info("=== 完了 ===")


if __name__ == "__main__":
    main()

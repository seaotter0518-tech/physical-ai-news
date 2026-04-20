#!/usr/bin/env python3
"""Physical AI Daily News Agent
住友商事 経営層向け Physical AI デイリーニュース配信システム
"""

import os
import sys
import smtplib
import logging
import re
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import feedparser
import anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    # 英語メディア
    "IEEE Spectrum Robotics":   "https://spectrum.ieee.org/feeds/blog/automaton.rss",
    "The Robot Report":         "https://www.therobotreport.com/feed/",
    "NVIDIA Blog":              "https://blogs.nvidia.com/feed/",
    "MIT Technology Review":    "https://www.technologyreview.com/feed/",
    "TechCrunch Robotics":      "https://techcrunch.com/tag/robotics/feed/",
    "Forbes Innovation":        "https://www.forbes.com/innovation/feed/",
    "VentureBeat AI":           "https://venturebeat.com/ai/feed/",
    "Wired Robots":             "https://www.wired.com/feed/tag/robots/rss",
    "Google DeepMind Blog":     "https://deepmind.google/blog/rss.xml",
    "Meta AI Blog":             "https://ai.meta.com/blog/rss/",
    "Microsoft Research":       "https://www.microsoft.com/en-us/research/feed/",
    "WSJ Tech":                 "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "Bloomberg Technology":     "https://feeds.bloomberg.com/technology/news.rss",
    # 日本語メディア
    "マイナビ ロボット":        "https://news.mynavi.jp/rss/techplus/robot/index_rss20.xml",
    "ITmedia AI+":              "https://rss.itmedia.co.jp/rss/2.0/ait.xml",
    "ロボスタ":                 "https://robosta.net/feed/",
    "日経クロステック":         "https://xtech.nikkei.com/rss/index.rdf",
}


def fetch_articles(hours: int = 24) -> list[dict]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    articles = []

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                pub = None
                if getattr(entry, "published_parsed", None):
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                if pub and pub < cutoff:
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))[:600]
                # HTMLタグ除去
                summary = re.sub(r"<[^>]+>", "", summary)

                articles.append({
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": summary,
                    "published": pub.isoformat() if pub else "",
                })
        except Exception as e:
            log.warning(f"フィード取得エラー [{source}]: {e}")

    log.info(f"{len(articles)} 件の記事を取得")
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
        max_tokens=3000,
        system=(
            "あなたは住友商事の秘書が経営層向けに配信する「Physical AI デイリーニュース」の編集者です。"
            "専門的な内容を正確に、かつ経営判断に役立つ視点で日本語にまとめてください。"
        ),
        messages=[{
            "role": "user",
            "content": f"""以下は {today_str} に収集した世界中のテクノロジーニュースです。

{articles_block}

【指示】
Physical AI（ロボティクス、具現化AI、自律システム、AI搭載の物理デバイス、製造・物流・医療・農業へのAI×ロボット応用）に関連する記事を厳選し、以下の形式で日本語メールを作成してください。

---
# ⚙️ Physical AI デイリーニュース｜{today_str}

## 🔝 本日のトップニュース

### 1. [日本語タイトル]
- **メディア**: [ソース名]
- **要約**: [経営層向けに3〜4文。数字・企業名・影響度を明記]
- **ビジネス示唆**: [住友商事のビジネスへの関連・示唆を1文]
- 🔗 [URL]

（トップニュースは3〜5件、同じ形式で）

---

## 📌 その他の注目動向
- **[タイトル日本語]**（[ソース]）: [1文要約] 🔗 [URL]

（3〜7件）

---

## 📊 本日のまとめ
[業界トレンドと住友商事が注目すべき点を4〜5文で総括]

---
*配信: Physical AI News Agent | {today_str} 07:00 JST*
---"""
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

    articles = fetch_articles(hours=24)
    if not articles:
        log.error("記事が取得できませんでした")
        sys.exit(1)

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

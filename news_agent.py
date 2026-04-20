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
    # ロボティクス・Physical AI 専門
    "IEEE Spectrum Robotics":       "https://spectrum.ieee.org/feeds/blog/automaton.rss",
    "The Robot Report":             "https://www.therobotreport.com/feed/",
    "Robotics Business Review":     "https://www.roboticsbusinessreview.com/feed/",
    "Automation World":             "https://www.automationworld.com/rss.xml",
    "Control Engineering":          "https://www.controleng.com/rss",
    "IndustryWeek":                 "https://www.industryweek.com/rss/all",
    "Wired Robots":                 "https://www.wired.com/feed/tag/robots/rss",
    # 投資・ビジネス（ファンディング・M&A情報）
    "TechCrunch Robotics":          "https://techcrunch.com/tag/robotics/feed/",
    "TechCrunch Funding":           "https://techcrunch.com/category/fundings-exits/feed/",
    "Bloomberg Technology":         "https://feeds.bloomberg.com/technology/news.rss",
    "WSJ Tech":                     "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "Forbes Innovation":            "https://www.forbes.com/innovation/feed/",
    # テック企業（Physical AI関連）
    "NVIDIA Blog":                  "https://blogs.nvidia.com/feed/",
    "MIT Technology Review":        "https://www.technologyreview.com/feed/",
    "VentureBeat AI":               "https://venturebeat.com/ai/feed/",
    # 日本語メディア
    "ロボスタ":                     "https://robosta.net/feed/",
    "マイナビ ロボット":            "https://news.mynavi.jp/rss/techplus/robot/index_rss20.xml",
    "日経クロステック":             "https://xtech.nikkei.com/rss/index.rdf",
    "ITmedia AI+":                  "https://rss.itmedia.co.jp/rss/2.0/ait.xml",
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
        max_tokens=3500,
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

【除外】以下は対象外：
❌ 生成AI（ChatGPT、LLM、画像生成、テキスト生成など純粋なソフトウェアAI）
❌ Physical AIと無関係なソフトウェア・クラウド・サービス系ニュース

【優先順位】以下の順で重要度を判定：
1. 💰 投資・資金調達（ファンディングラウンド、金額、投資家）
2. 🤝 M&A・買収・合併・パートナーシップ
3. 🚀 製品発表・技術ブレークスルー（商業インパクトが大きいもの）
4. 📊 市場動向・規制・業界再編

以下の形式で日本語レポートを作成してください：

---
# 🤖 Physical AI デイリーニュース｜{today_str}

## 💰 投資・M&A・パートナーシップ
（該当ニュースがあれば最優先で掲載。なければこのセクションは省略）

### 1. [日本語タイトル]
- **メディア**: [ソース名]
- **概要**: [何が起きたか。金額・企業名・規模を必ず明記。3文以内]
- **インパクト**: [業界・市場への影響を1文]
- 🔗 [URL]

---

## 🚀 技術・製品ニュース

### 1. [日本語タイトル]
- **メディア**: [ソース名]
- **概要**: [技術的・商業的に何が重要か。3文以内]
- **インパクト**: [なぜ重要かを1文]
- 🔗 [URL]

（各セクション最大5件まで）

---

## 📌 その他の注目動向
- **[タイトル]**（[ソース]）: [1文] 🔗 [URL]

---

## 📊 本日のまとめ
[Physical AI業界全体のトレンドを4〜5文で。投資家・経営層が注目すべき点を中心に]

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

    # 月曜日は週末分（78時間）、火〜金は24時間
    today_jst = datetime.now(tz=JST)
    hours = 78 if today_jst.weekday() == 0 else 24
    log.info(f"取得期間: 過去{hours}時間（{['月','火','水','木','金','土','日'][today_jst.weekday()]}曜日）")

    articles = fetch_articles(hours=hours)
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

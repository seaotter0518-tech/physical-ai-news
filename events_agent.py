#!/usr/bin/env python3
"""San Jose Kids Events Agent
3歳の娘向け サンノゼ周辺 週次イベント情報配信
"""

import os
import sys
import smtplib
import logging
import re
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from duckduckgo_search import DDGS
import anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
PST = timezone(timedelta(hours=-8))


def search_events() -> list[dict]:
    """DuckDuckGoでサンノゼ周辺の子供向けイベントを検索"""
    today_pst = datetime.now(tz=PST)
    week_str = today_pst.strftime("%B %Y")

    queries = [
        f"Bay Area toddler dance music class 3 year old {week_str}",
        f"Bay Area kids swimming pool lesson toddler {week_str}",
        f"Bay Area festival fair family kids outdoor {week_str}",
        f"Bay Area children art craft class toddler {week_str}",
        f"Bay Area kids gardening nature outdoor program {week_str}",
        f"Bay Area public library story time toddler {week_str}",
        f"Silicon Valley toddler educational activities {week_str}",
        f"San Francisco Oakland Palo Alto kids events toddler {week_str}",
        "Children's Discovery Museum San Jose events",
        "Exploratorium San Francisco kids family events",
        "Bay Area kids museum family activities toddler",
        f"Santa Clara Sunnyvale Cupertino kids events {week_str}",
    ]

    results = []
    seen_urls = set()

    with DDGS() as ddgs:
        for query in queries:
            try:
                for r in ddgs.text(query, max_results=5):
                    url = r.get("href", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append({
                        "title": r.get("title", ""),
                        "link": url,
                        "summary": r.get("body", "")[:500],
                    })
            except Exception as e:
                log.warning(f"検索エラー [{query[:40]}]: {e}")

    log.info(f"{len(results)} 件の検索結果を取得")
    return results


def curate_events(results: list[dict]) -> str:
    """Claude APIで3歳向けイベントをキュレーション"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today_pst = datetime.now(tz=PST)
    week_start = today_pst.strftime("%m月%d日")
    next_week = (today_pst + timedelta(days=7)).strftime("%m月%d日")

    results_block = "\n\n".join(
        f"[{i+1}] {r['title']}\nURL: {r['link']}\n内容: {r['summary']}"
        for i, r in enumerate(results)
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        system=(
            "あなたはサンノゼ在住の3歳の女の子を持つ親向けに、"
            "週末・週中の子供向けイベント情報をキュレーションする専門家です。"
            "教育的で楽しく、3歳の子供が楽しめる情報を日本語でまとめてください。"
        ),
        messages=[{
            "role": "user",
            "content": f"""以下は今週のサンノゼ周辺の子供向けイベント検索結果です。

{results_block}

【条件】
- 対象: 3歳の女の子（幼児・トドラー向け）
- 場所: Bay Area全域（San Jose, San Francisco, Oakland, Palo Alto, Santa Clara, Sunnyvale, Cupertino, Fremont, Mountain View など）
- 優先: Educational（学習・体験・創造）かつ楽しいもの
- 特に重視する分野:
  🎵 音楽（Music class、ミュージックタイム）
  💃 ダンス（Dance class、Movement class）
  🏊 プール・水遊び（Swim lesson、Water play）
  🎪 お祭り・フェスティバル（Festival、Fair、Community event）
  🎨 アート・工作（Art class、Craft、Creative workshop）
  🌱 園芸・自然体験（Gardening、Nature program、Outdoor education）
  📚 ストーリータイム・図書館イベント

以下の形式で日本語レポートを作成してください：

---
# 🌟 今週の娘ちゃんイベント情報｜{week_start}〜{next_week}

## 🎯 今週のおすすめイベント

### 1. [イベント名]
- 📍 **場所**: [会場名・住所]
- 📅 **日時**: [日付・時間]
- 💰 **料金**: [無料/金額]
- 🎨 **内容**: [3歳向けに何が体験できるか。2〜3文]
- ✨ **おすすめポイント**: [教育的・楽しい観点から1文]
- 🔗 [URL]

（3〜6件を同様の形式で）

---

## 📌 定期開催プログラム（いつでも行ける！）
- **[プログラム名]**（[場所]）: [内容1文] 🔗 [URL]

（定期プログラムがあれば2〜4件）

---

## 💡 今週のおでかけアドバイス
[天気・混雑・予約の要否など、親目線のアドバイスを2〜3文]

---
*San Jose Kids Events Agent | {today_pst.strftime('%Y年%m月%d日')} 配信*"""
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
  h1{{color:#e91e8c;border-bottom:2px solid #e91e8c;padding-bottom:8px}}
  h2{{color:#333;margin-top:28px}}
  h3{{color:#e91e8c;margin-top:20px}}
  hr{{border:none;border-top:1px solid #e0e0e0;margin:20px 0}}
  li{{margin:6px 0}}
  a{{color:#e91e8c}}
</style></head><body>{h}</body></html>"""


def send_email(subject: str, html: str, plain: str) -> None:
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("TO_EMAIL", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Kids Events San Jose <{user}>"
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, password)
        s.sendmail(user, to, msg.as_string())
    log.info(f"送信完了 → {to}")


def main() -> None:
    log.info("=== San Jose Kids Events Agent 起動 ===")

    results = search_events()
    if not results:
        log.error("イベント情報が取得できませんでした")
        sys.exit(1)

    digest = curate_events(results)

    today_pst = datetime.now(tz=PST)
    subject = f"🌟 今週の娘ちゃんイベント情報｜{today_pst.strftime('%m/%d')}週"
    send_email(subject, to_html(digest), digest)

    log.info("=== 完了 ===")


if __name__ == "__main__":
    main()

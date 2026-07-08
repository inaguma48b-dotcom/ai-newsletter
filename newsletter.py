#!/usr/bin/env python3
"""
AI Weekly Newsletter Generator (無料版)
========================================
Google Gemini API (無料枠) で最新AI情報をリサーチし、
HTML形式のメールマガジンを生成して Gmail SMTP で配信する。

GitHub Actions から週1回自動実行される想定。
ローカル実行も可能: python newsletter.py [--dry-run]

必要な環境変数:
  GEMINI_API_KEY      : Google Gemini APIキー（無料）
  GMAIL_ADDRESS       : 送信元Gmailアドレス
  GMAIL_APP_PASSWORD  : Gmailアプリパスワード(16桁)
  RECIPIENTS          : 宛先(カンマ区切りで複数可)
"""

import os
import re
import sys
import json
import time
import smtplib
import datetime
import urllib.request
import urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path

# ---------------------------------------------------------------
# 設定
# ---------------------------------------------------------------
GEMINI_MODEL = "gemini-2.5-flash"
ARCHIVE_DIR = Path(__file__).parent / "archive"
NEWSLETTER_TITLE = "AI Weekly Insight"
SUBTITLE = "ビジネスと副業に効く、今週のAI情報"

# ---------------------------------------------------------------
# 1. Gemini APIで記事生成（標準ライブラリのみ・依存ゼロ）
# ---------------------------------------------------------------
PROMPT_TEMPLATE = """あなたは日本のビジネスパーソン向けAI情報メールマガジンの編集長です。
本日は{today}です。直近1週間({week_start}〜{today})のAI業界の動向をまとめ、
「明日から仕事や副業に使える」実用情報に絞ったメールマガジン本文を作成してください。

# 執筆方針
- 結論ファースト。各項目は「何が起きた→なぜ重要→どう使えるか」の順
- 専門用語には一言補足を付ける
- ビジネス・副業への活用視点を必ず入れる
- 2026年最新のAIトレンドを反映する

# 必ずこの構造のMarkdownで出力（前置き・後書き不要）

## 今週のハイライト
（3行で今週の要点）

## 📰 トップニュース（3〜4本）
### ニュースタイトル
本文（3〜5文）。**ビジネス活用ポイント:** 一言。

## 💼 ビジネス活用アイデア
今週のトレンドを踏まえた具体的な業務活用アイデアを2つ（各3〜4文）

## 💰 副業・サイドビジネスの視点
AIを使った副業のヒントや市場動向を1〜2つ（各3〜4文）

## 🛠 今週の注目ツール
注目のAIツールを1〜2個。料金・特徴・向いている人を簡潔に。

## 編集後記
2〜3文の軽いまとめ"""


def call_gemini(prompt: str) -> str:
    """Gemini APIをurllib（標準ライブラリ）で呼び出す。"""
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"Gemini APIエラー {e.code}: {body}") from e

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini APIレスポンス解析失敗: {data}") from e


def generate_newsletter() -> str:
    """Gemini APIで記事生成。Markdown本文を返す。"""
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=7)

    print(f"[1/3] Gemini APIで記事生成中... (model={GEMINI_MODEL})")

    prompt = PROMPT_TEMPLATE.format(
        today=today.strftime("%Y年%m月%d日"),
        week_start=week_start.strftime("%Y年%m月%d日"),
    )

    body_md = call_gemini(prompt)

    if len(body_md) < 300:
        raise RuntimeError("生成された本文が短すぎます。APIレスポンスを確認してください。")

    print(f"  生成完了（{len(body_md)}文字）")
    return body_md.strip()


# ---------------------------------------------------------------
# 2. Markdown → HTMLメール変換
# ---------------------------------------------------------------
def md_to_html(md: str) -> str:
    html_lines = []
    for line in md.splitlines():
        line = line.rstrip()
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        line = re.sub(
            r"(https?://[^\s<>\)]+)",
            r'<a href="\1" style="color:#7c3aed;">\1</a>',
            line,
        )
        if line.startswith("### "):
            html_lines.append(
                f'<h3 style="margin:20px 0 8px;font-size:16px;color:#1f2937;">{line[4:]}</h3>')
        elif line.startswith("## "):
            html_lines.append(
                f'<h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;'
                f'background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;'
                f'border-radius:6px;">{line[3:]}</h2>')
        elif line.startswith("- "):
            html_lines.append(
                f'<p style="margin:4px 0 4px 16px;">・{line[2:]}</p>')
        elif line == "":
            html_lines.append("")
        else:
            html_lines.append(
                f'<p style="margin:8px 0;line-height:1.8;">{line}</p>')
    return "\n".join(html_lines)


def build_html_email(body_md: str, issue_no: int, date_str: str) -> str:
    body_html = md_to_html(body_md)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Hiragino Sans','Yu Gothic',Meiryo,sans-serif;color:#111827;">
  <div style="max-width:640px;margin:0 auto;padding:24px 16px;">
    <div style="background:linear-gradient(135deg,#1e1b4b,#7c3aed);border-radius:12px 12px 0 0;padding:32px 24px;text-align:center;">
      <div style="font-size:26px;font-weight:bold;color:#fff;letter-spacing:1px;">🔦 {NEWSLETTER_TITLE}</div>
      <div style="font-size:13px;color:#c4b5fd;margin-top:8px;">{SUBTITLE}</div>
      <div style="font-size:12px;color:#a78bfa;margin-top:4px;">Vol.{issue_no} | {date_str}</div>
    </div>
    <div style="background:#ffffff;border-radius:0 0 12px 12px;padding:24px;font-size:14px;">
      {body_html}
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:32px 0 16px;">
      <p style="font-size:11px;color:#9ca3af;text-align:center;">
        本メールはGemini AIによる自動生成です。<br>
        重要な意思決定の際は出典元をご確認ください。
      </p>
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------
# 3. メール送信 & アーカイブ
# ---------------------------------------------------------------
def get_issue_number() -> int:
    ARCHIVE_DIR.mkdir(exist_ok=True)
    return len(list(ARCHIVE_DIR.glob("*.html"))) + 1


def send_email(html: str, subject: str, recipients: list):
    gmail_addr = os.environ["GMAIL_ADDRESS"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]

    print(f"[3/3] メール送信中... ({len(recipients)}件)")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_addr, gmail_pass)
        for to_addr in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = f"{NEWSLETTER_TITLE} <{gmail_addr}>"
            msg["To"] = to_addr
            msg.attach(MIMEText(html, "html", "utf-8"))
            server.sendmail(gmail_addr, to_addr, msg.as_string())
            print(f"  ✓ {to_addr}")


def main():
    dry_run = "--dry-run" in sys.argv
    today = datetime.date.today()
    date_str = today.strftime("%Y年%m月%d日")
    issue_no = get_issue_number()

    body_md = generate_newsletter()

    print("[2/3] HTMLメール組版中...")
    html = build_html_email(body_md, issue_no, date_str)

    stamp = today.strftime("%Y-%m-%d")
    (ARCHIVE_DIR / f"{stamp}_vol{issue_no}.md").write_text(body_md, encoding="utf-8")
    (ARCHIVE_DIR / f"{stamp}_vol{issue_no}.html").write_text(html, encoding="utf-8")
    print(f"  アーカイブ保存: archive/{stamp}_vol{issue_no}.html")

    if dry_run:
        print("--dry-run のため送信はスキップしました。archive/ を確認してください。")
        return

    recipients = [a.strip() for a in os.environ["RECIPIENTS"].split(",") if a.strip()]
    subject = f"【{NEWSLETTER_TITLE} Vol.{issue_no}】{date_str} 今週のAIビジネス情報"
    send_email(html, subject, recipients)
    print("完了 🎉")


if __name__ == "__main__":
    main()

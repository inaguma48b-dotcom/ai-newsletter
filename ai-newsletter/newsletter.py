#!/usr/bin/env python3
"""
AI Weekly Newsletter Generator
==============================
Claude API (Web検索ツール付き) で最新AI情報をディープリサーチし、
HTML形式のメールマガジンを生成して Gmail SMTP で配信する。

GitHub Actions から週1回自動実行される想定。
ローカル実行も可能: python newsletter.py [--dry-run]

必要な環境変数:
  ANTHROPIC_API_KEY   : Claude APIキー
  GMAIL_ADDRESS       : 送信元Gmailアドレス
  GMAIL_APP_PASSWORD  : Gmailアプリパスワード(16桁)
  RECIPIENTS          : 宛先(カンマ区切りで複数可)
"""

import os
import re
import sys
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path

import anthropic

# ---------------------------------------------------------------
# 設定
# ---------------------------------------------------------------
MODEL = "claude-sonnet-4-6"        # コスパ重視。品質優先なら claude-opus-4-8
MAX_SEARCHES = 12                  # 週次リサーチの検索回数上限(コスト管理)
MAX_TOKENS = 8000
ARCHIVE_DIR = Path(__file__).parent / "archive"

NEWSLETTER_TITLE = "AI Weekly Insight"
SUBTITLE = "ビジネスと副業に効く、今週のAI情報"

# ---------------------------------------------------------------
# 1. Claude APIでディープリサーチ + 記事生成
# ---------------------------------------------------------------
SYSTEM_PROMPT = """あなたは日本のビジネスパーソン向けAI情報メールマガジンの編集長です。
Web検索を駆使して、直近1週間のAI関連情報を徹底的にリサーチし、
「明日から仕事や副業に使える」実用情報に絞ってまとめてください。

# リサーチ方針
- 直近7日以内のニュースを優先(古い情報は除外)
- 一次情報(公式ブログ・公式発表)を優先
- 日本国内の動向と海外の重要ニュースをバランスよく
- 検索は英語・日本語の両方で行う

# 執筆方針
- 結論ファースト。各項目は「何が起きた→なぜ重要→どう使えるか」の順
- 事実厳守。検索で確認できた情報のみ記載し、推測は「〜と見られる」と明示
- 専門用語には一言補足を付ける
- 各ニュースに出典URLを必ず記載

# 出力フォーマット(必ずこの構造のMarkdownで出力)
## 今週のハイライト
(3行で今週の要点)

## 📰 トップニュース(3〜4本)
### ニュースタイトル
本文(3〜5文)。**ビジネス活用ポイント:** 一言。
出典: URL

## 💼 ビジネス活用アイデア
今週のニュースを踏まえた具体的な業務活用アイデアを2つ(各3〜4文)

## 💰 副業・サイドビジネスの視点
AIを使った副業のヒントや市場動向を1〜2つ(各3〜4文)

## 🛠 今週の注目ツール
新登場または大型アップデートのAIツールを1〜2個。料金・特徴・向いている人を簡潔に。
出典: URL

## 編集後記
2〜3文の軽いまとめ

Markdown以外の前置き・後書きは一切不要です。"""

USER_PROMPT = """本日は{today}です。直近1週間({week_start}〜{today})のAI業界の動向を
Web検索でディープリサーチし、メールマガジン本文を作成してください。

最低限カバーすべき調査観点:
1. 主要AI企業(OpenAI, Anthropic, Google, Meta, Microsoft等)の新発表
2. 日本国内のAIビジネス・規制・導入事例のニュース
3. 中小企業や個人が使える新しいAIツール・機能
4. AI副業・フリーランス市場の動向

複数回検索して情報を集めてから執筆してください。"""


def generate_newsletter() -> str:
    """Claude APIでリサーチ&記事生成。Markdown本文を返す。"""
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を自動参照

    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=7)

    print(f"[1/3] Claude APIでディープリサーチ中... (model={MODEL}, max {MAX_SEARCHES} searches)")

    messages = [{
        "role": "user",
        "content": USER_PROMPT.format(
            today=today.strftime("%Y年%m月%d日"),
            week_start=week_start.strftime("%Y年%m月%d日"),
        ),
    }]

    # pause_turn(長時間ターンの一時停止)に対応するためループで継続
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_SEARCHES,
                "user_location": {
                    "type": "approximate",
                    "country": "JP",
                    "timezone": "Asia/Tokyo",
                },
            }],
        )
        if response.stop_reason == "pause_turn":
            print("  ... リサーチ継続中 (pause_turn)")
            messages.append({"role": "assistant", "content": response.content})
            continue
        break

    # テキストブロックを結合
    body_md = "\n".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    searches = getattr(response.usage, "server_tool_use", None)
    if searches:
        print(f"  検索回数: {searches.web_search_requests}")
    print(f"  入力トークン: {response.usage.input_tokens} / 出力: {response.usage.output_tokens}")

    if len(body_md) < 500:
        raise RuntimeError("生成された本文が短すぎます。API応答を確認してください。")
    return body_md


# ---------------------------------------------------------------
# 2. Markdown → HTMLメール変換(依存ライブラリなしの軽量変換)
# ---------------------------------------------------------------
def md_to_html(md: str) -> str:
    """メール向けの簡易Markdown→HTML変換。"""
    html_lines = []
    for line in md.splitlines():
        line = line.rstrip()
        # インライン装飾
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
        本メールはClaude APIによる自動リサーチで生成されています。<br>
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
    """archive内のファイル数から号数を自動採番。"""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    return len(list(ARCHIVE_DIR.glob("*.html"))) + 1


def send_email(html: str, subject: str, recipients: list[str]):
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

    # アーカイブ保存(GitHub Pagesでの公開にも流用可能)
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

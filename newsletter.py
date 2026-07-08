#!/usr/bin/env python3
"""
AI Weekly Newsletter Generator (固定テンプレート版)
====================================================
AIなしで固定テンプレートのメールマガジンを Gmail SMTP で配信する。
仕組みの動作確認用。中身は後でAIに差し替え可能。

必要な環境変数:
  GMAIL_ADDRESS       : 送信元Gmailアドレス
  GMAIL_APP_PASSWORD  : Gmailアプリパスワード(16桁)
  RECIPIENTS          : 宛先(カンマ区切りで複数可)
"""

import os
import sys
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path

# ---------------------------------------------------------------
# 設定
# ---------------------------------------------------------------
ARCHIVE_DIR = Path(__file__).parent / "archive"
NEWSLETTER_TITLE = "AI Weekly Insight"
SUBTITLE = "ビジネスと副業に効く、今週のAI情報"

# ---------------------------------------------------------------
# 1. 固定テンプレート本文
# ---------------------------------------------------------------
def generate_body(date_str: str, issue_no: int) -> str:
    return f"""
    <h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;
    background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;
    border-radius:6px;">今週のハイライト</h2>
    <p style="margin:8px 0;line-height:1.8;">
      今週もAI業界は急速に進化しています。ビジネスや副業に役立つ情報をお届けします。
      このメールマガジンは毎週月曜日に自動配信されます。
    </p>

    <h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;
    background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;
    border-radius:6px;">　 トップニュース</h2>

    <h3 style="margin:20px 0 8px;font-size:16px;color:#1f2937;">AIツールの業務活用が加速</h3>
    <p style="margin:8px 0;line-height:1.8;">
      ChatGPT・Claude・Geminiなどの生成AIが、企業の日常業務に組み込まれるケースが増えています。
      特に文書作成・メール返信・データ分析の分野で導入が進んでいます。
      <strong>ビジネス活用ポイント:</strong> まず1つの繰り返し作業をAIに任せることから始めましょう。
    </p>

    <h3 style="margin:20px 0 8px;font-size:16px;color:#1f2937;">画像生成AIの精度が向上</h3>
    <p style="margin:8px 0;line-height:1.8;">
      Midjourney・Stable Diffusionなどの画像生成AIが、より高精度な画像を生成できるようになりました。
      バナー・SNS画像・LP素材などを低コストで作成できます。
      <strong>ビジネス活用ポイント:</strong> デザイナーへの外注コストを削減できる可能性があります。
    </p>

    <h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;
    background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;
    border-radius:6px;">　 ビジネス活用アイデア</h2>
    <p style="margin:8px 0;line-height:1.8;">
      <strong>① 議事録の自動化:</strong>
      会議の録音をWhisperなどの音声認識AIでテキスト化し、
      ChatGPTで要点をまとめる仕組みを作ると、議事録作成時間を大幅に削減できます。
    </p>
    <p style="margin:8px 0;line-height:1.8;">
      <strong>② メール返信テンプレートのAI化:</strong>
      よく来る問い合わせメールへの返信をAIに下書きさせ、
      確認・送信するだけのフローにすると対応時間が半減します。
    </p>

    <h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;
    background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;
    border-radius:6px;">　 副業・サイドビジネスの視点</h2>
    <p style="margin:8px 0;line-height:1.8;">
      <strong>AIを使ったLP制作の需要増加:</strong>
      中小企業のランディングページ制作をAIツールで効率化し、
      低価格・短納期で受注するフリーランサーが増えています。
      Claude・ChatGPTでコピーを生成し、制作コストを大幅に削減できます。
    </p>

    <h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;
    background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;
    border-radius:6px;">　 今週の注目ツール</h2>
    <p style="margin:8px 0;line-height:1.8;">
      <strong>Perplexity AI:</strong>
      Web検索と回答生成を組み合わせたAI検索エンジン。
      無料プランあり。最新情報のリサーチに最適で、情報収集の時間を大幅に短縮できます。
    </p>

    <h2 style="margin:28px 0 12px;padding:8px 12px;font-size:18px;
    background:linear-gradient(90deg,#7c3aed,#ec4899);color:#fff;
    border-radius:6px;">編集後記</h2>
    <p style="margin:8px 0;line-height:1.8;">
      Vol.{issue_no}をお届けしました。{date_str}現在の情報をもとに構成しています。
      来週もAI最新情報をお届けします。引き続きよろしくお願いいたします。
    </p>
    """


# ---------------------------------------------------------------
# 2. HTMLメール組版
# ---------------------------------------------------------------
def build_html_email(body_html: str, issue_no: int, date_str: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:'Hiragino Sans','Yu Gothic',Meiryo,sans-serif;color:#111827;">
  <div style="max-width:640px;margin:0 auto;padding:24px 16px;">
    <div style="background:linear-gradient(135deg,#1e1b4b,#7c3aed);border-radius:12px 12px 0 0;padding:32px 24px;text-align:center;">
      <div style="font-size:26px;font-weight:bold;color:#fff;letter-spacing:1px;">　 {NEWSLETTER_TITLE}</div>
      <div style="font-size:13px;color:#c4b5fd;margin-top:8px;">{SUBTITLE}</div>
      <div style="font-size:12px;color:#a78bfa;margin-top:4px;">Vol.{issue_no} | {date_str}</div>
    </div>
    <div style="background:#ffffff;border-radius:0 0 12px 12px;padding:24px;font-size:14px;">
      {body_html}
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:32px 0 16px;">
      <p style="font-size:11px;color:#9ca3af;text-align:center;">
        本メールは自動配信されています。<br>
        毎週月曜日にお届けします。
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

    print(f"[2/2] メール送信中... ({len(recipients)}件)")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_addr, gmail_pass)
        for to_addr in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = f"{NEWSLETTER_TITLE} <{gmail_addr}>"
            msg["To"] = to_addr
            msg.attach(MIMEText(html, "html", "utf-8"))
            server.sendmail(gmail_addr, to_addr, msg.as_string())
            print(f"  ? {to_addr}")


def main():
    dry_run = "--dry-run" in sys.argv
    today = datetime.date.today()
    date_str = today.strftime("%Y年%m月%d日")
    issue_no = get_issue_number()

    print(f"[1/2] HTMLメール組版中... (Vol.{issue_no})")
    body_html = generate_body(date_str, issue_no)
    html = build_html_email(body_html, issue_no, date_str)

    stamp = today.strftime("%Y-%m-%d")
    (ARCHIVE_DIR / f"{stamp}_vol{issue_no}.html").write_text(html, encoding="utf-8")
    print(f"  アーカイブ保存: archive/{stamp}_vol{issue_no}.html")

    if dry_run:
        print("--dry-run のため送信はスキップしました。")
        return

    recipients = [a.strip() for a in os.environ["RECIPIENTS"].split(",") if a.strip()]
    subject = f"【{NEWSLETTER_TITLE} Vol.{issue_no}】{date_str} 今週のAIビジネス情報"
    send_email(html, subject, recipients)
    print("完了 　")


if __name__ == "__main__":
    main()

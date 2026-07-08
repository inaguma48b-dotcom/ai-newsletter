#!/usr/bin/env python3
"""
AI Weekly Newsletter ? content.md読み込み版
content.mdを編集してGitHubにコミットするだけでメルマガの中身が変わる。
"""

import os
import sys
import re
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path

ARCHIVE_DIR = Path(__file__).parent / "archive"
CONTENT_FILE = Path(__file__).parent / "content.md"
NEWSLETTER_TITLE = "AI Weekly Insight"
SUBTITLE = "ビジネス×AI ? 今週の厳選情報"

# ---------------------------------------------------------------
# 1. content.md を読み込んでHTML変換
# ---------------------------------------------------------------
def md_to_html(md: str) -> str:
    """Markdownを高品質なビジネス向けHTMLに変換する。"""

    # コメントを除去
    md = re.sub(r'<!--.*?-->', '', md, flags=re.DOTALL)

    # H1(タイトル行)を除去
    md = re.sub(r'^#\s+.+\n?', '', md, flags=re.MULTILINE)

    html_lines = []
    in_list = False

    for line in md.splitlines():
        line = line.rstrip()

        # インライン装飾
        line = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#1e1b4b;">\1</strong>', line)
        line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
        line = re.sub(
            r'(https?://[^\s<>\)]+)',
            r'<a href="\1" style="color:#7c3aed;text-decoration:none;border-bottom:1px solid #c4b5fd;">\1</a>',
            line,
        )

        if line.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            text = line[3:]
            # アイコンを取り出してセクションヘッダーを装飾
            html_lines.append(f'''
<table width="100%" cellpadding="0" cellspacing="0" style="margin:32px 0 16px;">
  <tr>
    <td style="background:linear-gradient(90deg,#1e1b4b,#7c3aed);
               padding:10px 18px;border-radius:6px 0 0 6px;">
      <span style="font-size:17px;font-weight:700;color:#ffffff;
                   letter-spacing:0.5px;">{text}</span>
    </td>
    <td style="background:linear-gradient(90deg,#7c3aed,#ec4899);
               width:6px;border-radius:0 6px 6px 0;"></td>
  </tr>
</table>''')

        elif line.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            text = line[4:]
            html_lines.append(f'''
<div style="margin:20px 0 6px;padding-left:12px;
            border-left:3px solid #7c3aed;">
  <span style="font-size:15px;font-weight:700;color:#1e1b4b;">{text}</span>
</div>''')

        elif line.startswith('- '):
            if not in_list:
                html_lines.append('<ul style="margin:8px 0;padding-left:0;list-style:none;">')
                in_list = True
            text = line[2:]
            html_lines.append(
                f'<li style="padding:4px 0 4px 20px;position:relative;">'
                f'<span style="position:absolute;left:0;color:#7c3aed;">?</span>{text}</li>')

        elif line == '':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('')

        else:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(
                f'<p style="margin:8px 0;line-height:1.9;color:#374151;font-size:14px;">{line}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


def load_content() -> str:
    if not CONTENT_FILE.exists():
        raise FileNotFoundError(f"content.md が見つかりません: {CONTENT_FILE}")
    return CONTENT_FILE.read_text(encoding='utf-8')


# ---------------------------------------------------------------
# 2. HTMLメール組版（ビジネス向けデザイン）
# ---------------------------------------------------------------
def build_html_email(body_html: str, issue_no: int, date_str: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f0f0f5;
             font-family:'Hiragino Sans','Yu Gothic',Meiryo,sans-serif;">

  <!-- ヘッダー -->
  <div style="max-width:620px;margin:0 auto;">
    <div style="background:#0f0c29;
                background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#24243e 100%);
                padding:0;">

      <!-- ロゴバー -->
      <div style="padding:28px 32px 0;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <div style="font-size:11px;color:#a78bfa;letter-spacing:3px;
                          text-transform:uppercase;margin-bottom:6px;">Weekly Business Intelligence</div>
              <div style="font-size:28px;font-weight:800;color:#ffffff;
                          letter-spacing:-0.5px;line-height:1.1;">
                　 {NEWSLETTER_TITLE}
              </div>
              <div style="font-size:13px;color:#c4b5fd;margin-top:6px;
                          font-weight:400;letter-spacing:0.5px;">{SUBTITLE}</div>
            </td>
            <td style="text-align:right;vertical-align:top;">
              <div style="display:inline-block;background:rgba(124,58,237,0.3);
                          border:1px solid rgba(196,181,253,0.3);
                          border-radius:6px;padding:8px 14px;text-align:center;">
                <div style="font-size:10px;color:#a78bfa;letter-spacing:1px;">VOL.</div>
                <div style="font-size:22px;font-weight:800;color:#ffffff;line-height:1;">{issue_no}</div>
              </div>
            </td>
          </tr>
        </table>
      </div>

      <!-- 日付バー -->
      <div style="margin-top:20px;padding:10px 32px;
                  background:rgba(0,0,0,0.2);
                  border-top:1px solid rgba(196,181,253,0.15);">
        <span style="font-size:12px;color:#a78bfa;">　 {date_str} 配信</span>
        <span style="font-size:12px;color:#6d28d9;margin:0 8px;">|</span>
        <span style="font-size:12px;color:#a78bfa;">毎週月曜日発行</span>
      </div>
    </div>

    <!-- 本文 -->
    <div style="background:#ffffff;padding:28px 32px 8px;">
      {body_html}
    </div>

    <!-- フッター -->
    <div style="background:#1e1b4b;padding:20px 32px;border-radius:0 0 0 0;">
      <div style="border-top:1px solid rgba(196,181,253,0.2);padding-top:16px;">
        <p style="font-size:11px;color:#6d5fa6;margin:0;line-height:1.8;text-align:center;">
          本メールは自動配信システムにより送信されています。<br>
          AI Weekly Insight ? ビジネスパーソンのためのAI情報メールマガジン
        </p>
      </div>
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
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"].strip()

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

    print(f"[1/2] content.md を読み込んで組版中... (Vol.{issue_no})")
    md = load_content()
    body_html = md_to_html(md)
    html = build_html_email(body_html, issue_no, date_str)

    stamp = today.strftime("%Y-%m-%d")
    (ARCHIVE_DIR / f"{stamp}_vol{issue_no}.html").write_text(html, encoding="utf-8")
    print(f"  アーカイブ保存: archive/{stamp}_vol{issue_no}.html")

    if dry_run:
        print("--dry-run のため送信はスキップしました。")
        return

    recipients = [a.strip() for a in os.environ["RECIPIENTS"].split(",") if a.strip()]
    subject = f"【AI Weekly Insight Vol.{issue_no}】{date_str} 今週のAIビジネス情報"
    send_email(html, subject, recipients)
    print("完了 　")


if __name__ == "__main__":
    main()

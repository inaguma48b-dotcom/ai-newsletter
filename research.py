#!/usr/bin/env python3
"""
AI Weekly Insight ― 情報取得の自動化スクリプト（Gemini無料枠版）

① 無料のRSSフィード（APIキー不要）から直近1週間のAI関連ニュースを収集
② Gemini API（無料枠）で取捨選択・要約させ、content.md を書き出す

Gemini APIの「Google検索グラウンディング」は無料枠では使えないため、
ニュースの取得はRSS側で行い、Geminiには「編集」だけをさせる構成にしている。

  python research.py            # content.md を上書き
  python research.py --dry-run  # 標準出力に表示するだけ
  python research.py --feeds-only  # 収集した記事一覧だけ表示（API不使用）
"""

import os
import re
import sys
import time
import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

CONTENT_FILE = Path(__file__).parent / "content.md"
# コーチングアプリ(mentora)と同じエイリアス。常に最新のFlash系を指すため、
# Googleが個別バージョンを提供終了しても壊れない。
# (gemini-2.5-flash / 2.5-flash-lite は新規ユーザーには提供終了済み＝404になる)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
JST = datetime.timezone(datetime.timedelta(hours=9))
API_TIMEOUT_MS = 180_000  # 無人実行で無限に待たないよう上限を設ける

DAYS = 7            # 何日前までのニュースを対象にするか
MAX_ARTICLES = 70   # プロンプトに載せる記事数の上限
MIN_ARTICLES = 15   # これを下回ったら収集失敗とみなす
UA = "Mozilla/5.0 (compatible; ai-newsletter/1.0)"

ATOM = "{http://www.w3.org/2005/Atom}"

# 説明文がしっかり入っている一次ソース
DIRECT_FEEDS = [
    ("ITmedia AI+", "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("Publickey", "https://www.publickey1.jp/atom.xml"),
]

# 網羅性を補うGoogleニュース検索（when:7d で直近1週間に限定）
NEWS_QUERIES = [
    "生成AI ビジネス 活用",
    "AI 導入 企業 事例",
    "OpenAI OR Anthropic OR Gemini 発表",
    "AI 規制 OR ガイドライン OR 法律",
    "AI ツール 新機能 リリース",
    "AI 副業 OR 個人 活用",
]

# (正式な見出し, 判定に使うキーワード)
# モデルは絵文字を落としたり異体字セレクタ付き(🛠️)で返したりと揺れるため、
# キーワードで判定して正式な見出しに書き戻す（弾かずに直す）。
SECTIONS = [
    ("## 今週のハイライト", "ハイライト"),
    ("## 📰 トップニュース", "トップニュース"),
    ("## 💼 ビジネス活用アイデア", "活用アイデア"),
    ("## 💰 副業・サイドビジネスの視点", "副業"),
    ("## 🛠 今週の注目ツール", "注目ツール"),
    ("## 編集後記", "編集後記"),
]
REQUIRED_SECTIONS = [s for s, _ in SECTIONS]


# ---------------------------------------------------------------
# 1. RSS収集
# ---------------------------------------------------------------
def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read()


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def parse_date(raw: str):
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        pass
    try:
        return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_feed(source: str, data: bytes) -> list:
    """RSS2.0とAtomの両方から (source, title, url, summary, published) を取り出す。"""
    root = ET.fromstring(data)
    articles = []

    for item in root.findall(".//item"):          # RSS 2.0
        articles.append({
            "source": source,
            "title": strip_tags(item.findtext("title", "")),
            "url": (item.findtext("link", "") or "").strip(),
            "summary": strip_tags(item.findtext("description", "")),
            "published": parse_date(item.findtext("pubDate", "")),
        })

    for entry in root.findall(f".//{ATOM}entry"):  # Atom
        link = entry.find(f"{ATOM}link")
        articles.append({
            "source": source,
            "title": strip_tags(entry.findtext(f"{ATOM}title", "")),
            "url": (link.get("href") if link is not None else "") or "",
            "summary": strip_tags(
                entry.findtext(f"{ATOM}summary", "") or entry.findtext(f"{ATOM}content", "")
            ),
            "published": parse_date(
                entry.findtext(f"{ATOM}updated", "") or entry.findtext(f"{ATOM}published", "")
            ),
        })

    return articles


def normalize_title(title: str) -> str:
    # Googleニュースの見出しは末尾に " - 媒体名" が付くので落としてから比較する
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    return re.sub(r"[\s　'\"“”‘’|｜\[\]【】()（）]", "", title).lower()


def collect_articles(now: datetime.datetime) -> list:
    cutoff = now - datetime.timedelta(days=DAYS)
    sources = list(DIRECT_FEEDS)
    for q in NEWS_QUERIES:
        url = (
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(f"{q} when:{DAYS}d")
            + "&hl=ja&gl=JP&ceid=JP:ja"
        )
        sources.append((f"Googleニュース({q})", url))

    collected, seen = [], set()
    for name, url in sources:
        try:
            articles = parse_feed(name, fetch(url))
        except Exception as e:
            print(f"  ! {name} の取得に失敗（スキップ）: {type(e).__name__}")
            continue

        kept = 0
        for a in articles:
            if not a["title"] or not a["url"]:
                continue
            # タイムゾーン情報が無い記事は取りこぼさないようUTC扱いにする
            pub = a["published"]
            if pub is not None:
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=datetime.timezone.utc)
                if pub < cutoff:
                    continue
                a["published"] = pub

            key = normalize_title(a["title"])
            if not key or key in seen:
                continue
            seen.add(key)
            collected.append(a)
            kept += 1
        print(f"  {name}: {kept}件")

    # 新しい順。日付不明は末尾に回す
    collected.sort(key=lambda a: a["published"] or datetime.datetime.min.replace(
        tzinfo=datetime.timezone.utc), reverse=True)
    return collected[:MAX_ARTICLES]


def format_articles(articles: list) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        date = a["published"].astimezone(JST).strftime("%m/%d") if a["published"] else "日付不明"
        lines.append(f"[{i}] ({date}) {a['title']}")
        if a["summary"]:
            lines.append(f"    概要: {a['summary'][:250]}")
        lines.append(f"    URL: {a['url']}")
    return "\n".join(lines)


# ---------------------------------------------------------------
# 2. Gemini で編集
# ---------------------------------------------------------------
SYSTEM_INSTRUCTION = """あなたは日本のビジネスパーソン向けAIメールマガジン「AI Weekly Insight」の編集者です。
読者は「AIに詳しくないが仕事で使いたいビジネスパーソン」。専門用語には短い補足を付けてください。

最重要ルール:
渡された記事一覧に書かれている内容だけを根拠に執筆してください。
一覧に無い数字・日付・企業名・製品名を絶対に補わないでください。
見出しから読み取れない詳細を推測で書くことは、事実の捏造として厳禁です。
情報が薄い記事は無理に扱わず、内容の濃い記事を選んでください。"""


def build_prompt(articles: list, today: datetime.date) -> str:
    start = today - datetime.timedelta(days=DAYS)
    period = f"{start.strftime('%Y年%m月%d日')}〜{today.strftime('%Y年%m月%d日')}"

    return f"""今日は {today.strftime('%Y年%m月%d日')} です。
以下は {period} に配信されたAI関連ニュースの一覧です（RSSから自動収集）。

――――――――――――――――――――
{format_articles(articles)}
――――――――――――――――――――

この中からビジネスパーソンにとって重要な話題を選び、今週号の本文を書いてください。

## 選定の方針
- 芸能・不祥事・炎上などビジネスに関係しない話題は除外する
- 広告・プレスリリース色が強すぎるものは避ける
- 「トップニュース」は内容の濃いものを3〜5本選ぶ
- 各ニュースは「何が起きたか」に加え「読者は明日から何をすべきか」まで書く
- 全体で日本語2,000〜3,000字程度

## 出力フォーマット（厳守）
最終的な本文だけを `<newsletter>` タグで囲んで出力してください。

<newsletter>
## 今週のハイライト

（今週全体を2〜3文で要約する導入文）

## 📰 トップニュース

### （1本目のニュース見出し）

（3〜5文の本文。記事一覧に書かれた事実の範囲で書く）
**ビジネス活用ポイント:** （読者が取るべき具体的な行動を1〜2文で）

### （2本目のニュース見出し）

（同上。3〜5本まで続ける）

## 💼 ビジネス活用アイデア

**① （アイデアの見出し）**
（3〜4文の説明）

**② （アイデアの見出し）**
（3〜4文の説明）

## 💰 副業・サイドビジネスの視点

**（見出し）**
（4〜6文。今週のニュースと結びついた具体的な切り口）

## 🛠 今週の注目ツール

**（ツール名・提供元）**
（3〜4文。どんな人に向いているかを明記）

## 編集後記

（3〜4文。今週を振り返る編集者の一言）
</newsletter>

## フォーマット上の制約（重要）
このMarkdownは自前の簡易パーサでHTMLメールに変換されます。必ず守ってください。
- 使ってよい記法は `## 見出し`、`### 見出し`、`- 箇条書き`、`**太字**`、本文の段落のみ
- `# `（H1）、表、コードブロック、水平線 `---`、引用 `>`、番号付きリスト `1.` は使わない
- **URLは一切書かない**（収集元URLはリダイレクト形式で読者には使えないため）。
  出典に触れるときは「ITmedia によると」のように媒体名だけを書く
- 見出しに番号や記号を付けない
- `<newsletter>` タグの外に説明や感想を書かない"""


def generate(prompt: str) -> str:
    from google import genai
    from google.genai import types

    # GEMINI_API_KEY を環境変数から読む
    client = genai.Client(http_options=types.HttpOptions(timeout=API_TIMEOUT_MS))
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
        # 思考トークンも上限に含まれるため多めに確保する
        max_output_tokens=16000,
    )

    last_error = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=prompt, config=config
            )
        except Exception as e:  # レート制限・一時的な障害
            last_error = e
            wait = 20 * (attempt + 1)
            print(f"  ! API呼び出し失敗（{type(e).__name__}）。{wait}秒後に再試行します")
            time.sleep(wait)
            continue

        text = response.text
        if text:
            return text

        reason = None
        if getattr(response, "candidates", None):
            reason = getattr(response.candidates[0], "finish_reason", None)
        last_error = RuntimeError(f"空のレスポンス (finish_reason={reason})")
        print(f"  ! {last_error}。再試行します")
        time.sleep(10)

    raise RuntimeError(f"Gemini APIの呼び出しに3回失敗しました: {last_error}")


# ---------------------------------------------------------------
# 3. 抽出と検証
# ---------------------------------------------------------------
def normalize_headings(body: str) -> str:
    """`## 見出し` をキーワードで判定し、絵文字込みの正式な表記に揃える。"""
    lines = []
    for line in body.splitlines():
        if line.startswith("## "):
            for canonical, keyword in SECTIONS:
                if keyword in line:
                    line = canonical
                    break
        lines.append(line)
    return "\n".join(lines)


def extract_newsletter(raw: str) -> str:
    match = re.search(r"<newsletter>(.*?)</newsletter>", raw, flags=re.DOTALL)
    if not match:
        raise RuntimeError("<newsletter> タグが見つかりません。モデルの出力:\n" + raw[:2000])

    body = normalize_headings(match.group(1).strip())

    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    if missing:
        found = [l for l in body.splitlines() if l.startswith("## ")]
        raise RuntimeError(
            "必須セクションが欠けています: " + ", ".join(missing)
            + "\n実際の見出し: " + ", ".join(found)
        )

    if len(body) < 800:
        raise RuntimeError(f"本文が短すぎます（{len(body)}文字）。生成に失敗した可能性があります。")

    if re.search(r"^\s*```", body, flags=re.MULTILINE):
        raise RuntimeError("コードブロックが含まれています。")
    if re.search(r"^\s*\|", body, flags=re.MULTILINE):
        raise RuntimeError("表が含まれています。")

    # 簡易パーサがリンク記法を解釈しないため、URLだけの形に直す
    body = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", r"\1 \2", body)

    return body + "\n"


# ---------------------------------------------------------------
def main():
    dry_run = "--dry-run" in sys.argv
    feeds_only = "--feeds-only" in sys.argv

    now = datetime.datetime.now(JST)
    today = now.date()

    print(f"[1/3] 直近{DAYS}日間のAIニュースをRSSから収集中... ({today})")
    articles = collect_articles(now)
    print(f"  → 重複除去後 {len(articles)}件")

    if feeds_only:
        print("\n" + format_articles(articles))
        return

    if len(articles) < MIN_ARTICLES:
        sys.exit(f"収集できた記事が{len(articles)}件しかありません（最低{MIN_ARTICLES}件必要）。中止します。")

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY が設定されていません。")

    print(f"[2/3] {MODEL} で記事を選定・執筆中...")
    raw = generate(build_prompt(articles, today))
    body = extract_newsletter(raw)

    if dry_run:
        print("[3/3] --dry-run のため content.md は更新しません。\n")
        print(body)
        return

    CONTENT_FILE.write_text(body, encoding="utf-8")
    print(f"[3/3] content.md を更新しました ({len(body)}文字)")


if __name__ == "__main__":
    main()

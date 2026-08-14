# 🔦 AI Weekly Insight — 全自動AIメールマガジンシステム

無料のRSSフィードから最新AI情報を集め、Gemini API(無料枠)で編集して、ビジネス・副業向けメールマガジンを**毎週月曜7時に全自動配信**するシステム。GitHub Actionsで動くため、自宅PCの電源が入っていなくても動作する。

**ランニングコストは実質0円**(Gemini無料枠 + GitHub Actions無料枠 + Gmail)。

## 仕組み

```
GitHub Actions (毎週月曜 07:00 JST)
   │
   ├─ ① research.py   : 無料RSS(ITmedia AI+ / TechCrunch AI / Googleニュース等)から
   │                    直近1週間のAI記事を収集 → 重複除去
   │                    → Gemini(無料枠)が取捨選択・執筆 → content.md を自動生成
   ├─ ② newsletter.py : content.md → HTMLメールに組版(紫グラデ・ペンライト風デザイン)
   ├─ ③ newsletter.py : Gmail SMTP で購読者に一斉送信
   └─ ④ content.md とバックナンバーを archive/ にコミット(GitHub Pages公開にも流用可)
```

### なぜRSSで集めるのか

Gemini APIの「Google検索グラウンディング」は**無料枠では使えない**(有料プランの課金設定が必要)。
そのため**情報の取得はRSS(無料・APIキー不要)が担当し、Geminiは「編集者」に徹する**構成にしている。
検索グラウンディングを使わないぶん、Geminiには収集済み記事の範囲でしか書かせない制約を課しており、
これは**事実の捏造を防ぐ効果**もある。

| ファイル | 役割 |
|---|---|
| `research.py` | AI情報の取得。RSS収集 → Geminiで執筆 → `content.md` を書き出す |
| `content.md` | その週の本文(自動生成。手で書き換えても配信できる) |
| `newsletter.py` | `content.md` の組版・送信・アーカイブ |

リサーチに失敗した場合はワークフローがそこで停止し、**メールは送信されない**(古い内容の誤配信を防ぐため)。

## セットアップ手順(初回のみ・約15分)

### 1. GitHubリポジトリ作成

1. GitHubで新規リポジトリを作成(**Private推奨**)
2. このフォルダの中身をすべてpush

```bash
cd ai-newsletter
git init
git add .
git commit -m "初期コミット"
git remote add origin https://github.com/<ユーザー名>/ai-newsletter.git
git push -u origin main
```

### 2. Gemini APIキー取得(無料)

1. https://aistudio.google.com/apikey にGoogleアカウントでログイン
2. 「APIキーを作成」で発行(**クレジットカード登録不要**)

コーチングアプリ(mentora)で既にGemini APIキーを使っている場合は、**同じキーを使い回せる**。
無料枠は1分あたり・1日あたりのリクエスト数で制限されるが、本システムは**週1回1リクエスト**しか
使わないため、他アプリと共用しても枯渇しない。

#### モデルについて(重要)

既定は `gemini-flash-latest`(mentoraと同じ)。**Gemini 2.0系・2.5系は新規ユーザーには提供終了**
しており、`gemini-2.5-flash` を指定すると404エラーになる:

```
404 NOT_FOUND: This model models/gemini-2.5-flash is no longer available to new users.
```

`gemini-flash-latest` は常に現行のFlash系を指すエイリアスなので、Googleが個別バージョンを
廃止しても壊れない。バージョンを固定したい場合は `GEMINI_MODEL` に `gemini-3.5-flash` などを指定する
(利用可能なモデルは `python -c "from google import genai; [print(m.name) for m in genai.Client().models.list()]"` で確認できる)。

### 3. Gmailアプリパスワード発行

1. Googleアカウントで**2段階認証を有効化**(必須)
2. https://myaccount.google.com/apppasswords でアプリパスワード(16桁)を発行

### 4. GitHub Secrets登録

リポジトリの `Settings → Secrets and variables → Actions → New repository secret` で以下4つを登録:

| Secret名 | 値 |
|---|---|
| `GEMINI_API_KEY` | AI Studioで発行したキー(`AIza...`) |
| `GMAIL_ADDRESS` | 送信元Gmailアドレス |
| `GMAIL_APP_PASSWORD` | 16桁のアプリパスワード(スペースなし) |
| `RECIPIENTS` | 宛先。複数はカンマ区切り `a@x.com,b@y.com` |

### 5. テスト実行

リポジトリの `Actions → Weekly AI Newsletter → Run workflow` で手動実行。
数分後にメールが届けば成功。以後は毎週月曜7時に自動実行される。

## ローカルでのテスト(送信せず生成のみ)

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=AIza...        # Windows PowerShell は $env:GEMINI_API_KEY="AIza..."

# ① RSS収集だけ試す(APIキー不要・料金ゼロ。何本集まったか確認できる)
python research.py --feeds-only

# ② 収集+執筆を試す(content.md は上書きせず標準出力に表示)
python research.py --dry-run

# ③ 収集+執筆して content.md を更新
python research.py

# ④ 組版だけ試す(メールは送らない)
python newsletter.py --dry-run
# → archive/ に .html が生成されるのでブラウザで確認
```

RSS収集は9フィードを順に取りに行くため**1〜2分ほどかかる**(APIの遅さではない)。

手動実行時に `Run workflow` の **「リサーチを飛ばす」** にチェックを入れると、
リサーチをスキップして現在の `content.md` をそのまま配信できる(組版・送信のテスト用)。

## ランニングコスト目安

- RSS収集: **0円**(APIキー不要)
- Gemini API: 無料枠内。**週1回1リクエスト**のみなので上限に当たらない
- GitHub Actions: Privateリポジトリでも無料枠(月2,000分)で余裕
- Gmail: 無料(1日500通まで)
- **合計: 0円**

無料枠のため、送信した内容がGoogleのモデル改善に利用される可能性がある
(有料枠では利用されない)。本システムが送るのは公開ニュースの見出しのみなので実害はないが、
機密情報を扱う用途に流用する場合は注意すること。

## カスタマイズポイント

| 変更したい内容 | 場所 |
|---|---|
| 配信曜日・時刻 | `.github/workflows/weekly-newsletter.yml` の `cron`(UTC表記に注意) |
| 情報源を追加・変更 | `research.py` の `DIRECT_FEEDS`(RSSのURL)と `NEWS_QUERIES`(検索語) |
| 収集する期間・件数 | `research.py` の `DAYS` / `MAX_ARTICLES` |
| モデル | `research.py` の `MODEL`、または環境変数 `GEMINI_MODEL` |
| 情報の鮮度 | `research.py` の `DAYS`(既定7日) |
| 紙面構成 | `research.py` の `build_prompt()` の「出力フォーマット」と `REQUIRED_SECTIONS` |
| 執筆トーン | `research.py` の `SYSTEM_INSTRUCTION` |
| デザイン | `newsletter.py` の `build_html_email()` のインラインCSS |

紙面構成を変えるときは、`build_prompt()` の見出しと `REQUIRED_SECTIONS` の
両方を揃えること(不一致だと生成物が検証で弾かれる)。

### 品質を上げたい場合

RSSの見出しと概要文(100〜250字)だけを根拠に書かせているため、記事本文まで読ませる方式に比べると
**1本あたりの掘り下げは浅くなる**。これは捏造を防ぐための意図的な制約でもある。

改善したい場合:
- 情報の濃い一次ソースのRSSを `DIRECT_FEEDS` に追加する(最も効果的・無料)
- Googleニュースは見出しのみで概要が薄いため、`NEWS_QUERIES` を絞って一次ソースを増やす
- Gemini側で課金を有効にすると検索グラウンディングが使えるようになる(有料)

## 発展アイデア

- `archive/` をGitHub Pagesで公開 → ホームページに「バックナンバー」コーナーを追加
- 購読者が増えたら `RECIPIENTS` をGoogleスプレッドシート連携や配信サービス(Resend等)に移行
- BCC一斉送信ではなく1通ずつ送る現方式は、Gmail無料枠(1日500通)の範囲で十分動作

## 注意事項

- Gmail無料アカウントの送信上限は**1日500通**。それを超える規模になったら配信専用サービスへの移行を推奨
- 商用メルマガとして配信する場合は特定電子メール法(オプトイン・配信解除導線の明記)への対応が必要

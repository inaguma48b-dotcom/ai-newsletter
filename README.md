# 🔦 AI Weekly Insight — 全自動AIメールマガジンシステム

Claude API(Web検索ツール)で最新AI情報をディープリサーチし、ビジネス・副業向けメールマガジンを**毎週月曜7時に全自動配信**するシステム。GitHub Actionsで動くため、自宅PCの電源が入っていなくても動作する。

## 仕組み

```
GitHub Actions (毎週月曜 07:00 JST)
   │
   ├─ ① Claude API + Web検索 → 直近1週間のAI情報をディープリサーチ
   ├─ ② Markdown → HTMLメールに組版(紫グラデ・ペンライト風デザイン)
   ├─ ③ Gmail SMTP で購読者に一斉送信
   └─ ④ バックナンバーを archive/ にコミット(GitHub Pages公開にも流用可)
```

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

### 2. Anthropic APIキー取得

1. https://console.anthropic.com にログイン
2. Settings → API Keys → Create Key
3. **管理画面でWeb検索が有効になっていることを確認**(Settings → Privacy / Features)

### 3. Gmailアプリパスワード発行

1. Googleアカウントで**2段階認証を有効化**(必須)
2. https://myaccount.google.com/apppasswords でアプリパスワード(16桁)を発行

### 4. GitHub Secrets登録

リポジトリの `Settings → Secrets and variables → Actions → New repository secret` で以下4つを登録:

| Secret名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `GMAIL_ADDRESS` | 送信元Gmailアドレス |
| `GMAIL_APP_PASSWORD` | 16桁のアプリパスワード(スペースなし) |
| `RECIPIENTS` | 宛先。複数はカンマ区切り `a@x.com,b@y.com` |

### 5. テスト実行

リポジトリの `Actions → Weekly AI Newsletter → Run workflow` で手動実行。
数分後にメールが届けば成功。以後は毎週月曜7時に自動実行される。

## ローカルでのテスト(送信せず生成のみ)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python newsletter.py --dry-run
# → archive/ に .html が生成されるのでブラウザで確認
```

## ランニングコスト目安

- Web検索: $10 / 1,000回 → 週12回 × 4週 ≒ **月$0.5前後**
- トークン(Sonnet 4.6): 週1回のリサーチで **月$1〜2程度**
- GitHub Actions: Privateリポジトリでも無料枠(月2,000分)で余裕
- **合計: 月200〜400円程度**

## カスタマイズポイント

| 変更したい内容 | 場所 |
|---|---|
| 配信曜日・時刻 | `.github/workflows/weekly-newsletter.yml` の `cron`(UTC表記に注意) |
| リサーチの深さ | `newsletter.py` の `MAX_SEARCHES`(増やすと詳しく・高コスト) |
| モデル | `MODEL = "claude-opus-4-8"` に変えると品質重視 |
| 紙面構成 | `SYSTEM_PROMPT` の出力フォーマット部分 |
| デザイン | `build_html_email()` のインラインCSS |

## 発展アイデア

- `archive/` をGitHub Pagesで公開 → ホームページに「バックナンバー」コーナーを追加
- 購読者が増えたら `RECIPIENTS` をGoogleスプレッドシート連携や配信サービス(Resend等)に移行
- BCC一斉送信ではなく1通ずつ送る現方式は、Gmail無料枠(1日500通)の範囲で十分動作

## 注意事項

- Gmail無料アカウントの送信上限は**1日500通**。それを超える規模になったら配信専用サービスへの移行を推奨
- 商用メルマガとして配信する場合は特定電子メール法(オプトイン・配信解除導線の明記)への対応が必要

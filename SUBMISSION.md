# 申請用メモ（Anthropic プラグインディレクトリ）

申請は作者が手で行う。このファイルは、申請フォームに入れる内容と事前の確認事項をまとめたもの。

- 申請先：https://claude.ai/directory/manage （手順：https://claude.com/docs/plugins/submit#submit-a-plugin）
- 必要なもの：claude.ai の有料プラン（Pro / Max / Ultra は自分のアカウントから。Team / Enterprise は Owner か Directory 権限）、プラグインを含む GitHub リポジトリ

## 基本情報

| 項目 | 内容 |
|---|---|
| プラグイン名（ID） | `my-ai-title` |
| 表示名 | My AI Title（AI肩書き診断） |
| リポジトリ | https://github.com/KazumiHARADA/my-ai-title |
| マーケットプレイス | `kharada`（このリポジトリ自体。`claude plugin marketplace add KazumiHARADA/my-ai-title`） |
| インストール | `claude plugin install my-ai-title@kharada` |
| バージョン | `.claude-plugin/plugin.json` の `version` |
| ライセンス | コード：MIT。キャラクター画像：別ライセンス（`skills/my-ai-title/assets/characters/LICENSE`） |
| 作者 | KazumiHARADA（https://github.com/KazumiHARADA） |
| カテゴリ（案） | Productivity / Fun |
| キーワード | diagnosis, card, sns, productivity, japanese |

## 説明文

**短い説明（英語）**
Reads your local Claude Code session logs, scores how you work with AI on six axes, and renders a shareable trading-card style PNG with your AI title.

**短い説明（日本語）**
Claude Code のログから、AIの使い方を6つの軸で診断し、SNSに投稿できるトレーディングカード風の画像をつくります。

**詳しい説明（英語）**
Ask "Make my AI title card" and the plugin reads your local Claude Code logs, computes metrics with local scripts, has Claude score six axes (context design, delegation, verification, autonomy design, intervention efficiency, systematization) from redacted excerpts, and picks one of 8 types and 32 abilities. The result is a 1200×675 card in Japanese or English. Cards never show numbers, working hours, or work details. Logs are only read locally; redacted excerpts are read by Claude for scoring and nothing is sent to any other service.

## スクリーンショット

- `docs/images/sample-ja.png`（日本語版、1200×675）
- `docs/images/sample-en.png`（英語版・レア、1200×675）

どちらも合成したスコアから作ったもの（実際のログは使っていない）。

## データの扱い（審査向けの要約）

- ネットワークアクセス：なし（スクリプトは標準ライブラリのみ、外部 URL を開かない。ブラウザはネットワーク系の機能を切ったヘッドレスモードで、ローカルの HTML を撮影するだけ）
- 外部送信：なし。採点のための秘匿化した抜粋は、ユーザー自身の Claude Code セッション内で Claude が読む
- 保存：カード画像（カレントディレクトリ、上書き前に確認）と、前回の6軸スコア（`~/.claude/my-ai-title/history.json`）
- 詳細：README の「データの扱い」

## 申請前のチェック

- [ ] `claude plugin validate . --strict` が通る
- [ ] `claude plugin validate . --strict --profile directory` が通る（アイコンが必要。下記）
- [ ] `python3 -m unittest discover -s tests` が通る
- [ ] アイコンを用意する：512〜2048px の正方形 PNG を `.claude-plugin/icon.png` に置く（SVG・WebP は不可、2MB 未満）。**ディレクトリのアイコンになるのは、最初に保存・申請したときの1回だけ**なので、申請前に確定させる
- [ ] キャラクター画像のライセンス文面（`skills/my-ai-title/assets/characters/LICENSE`）を最終確認する
- [ ] リポジトリに実ログ・秘密情報・個人のパスが含まれていないことを確認する
- [ ] 名前・ロゴ・見た目に「Claude」や Claude のロゴ、Claude Code の画面を思わせる要素を使っていない
- [ ] main に push 済み。GitHub からインストールして動くことを確認した

"""Redaction applied to every excerpt before the AI host reads it.

When unsure, redact. Order matters: whole structures (code, secrets, URLs,
paths) go first, then word-level rules.

Placeholders: [CODE] [LOG] [SECRET] [EMAIL] [URL] [PATH] [HOST] [NAME] [ID] [NUM]
"""
from __future__ import annotations

import re
from typing import Iterable, Optional


# Placeholders are held as private-use characters while redacting so that later
# word-level rules do not touch them, then rendered as [NAME] etc. at the end.
_NAMES = ("CODE", "LOG", "SECRET", "EMAIL", "URL", "PATH", "HOST", "NAME", "ID", "NUM")
_PH = {n: chr(0xE000 + i) for i, n in enumerate(_NAMES)}
_PH_BACK = {v: "[" + k + "]" for k, v in _PH.items()}
CODE, LOG, SECRET, EMAIL, URL, PATH, HOST, NAME, ID, NUM = (_PH[n] for n in _NAMES)

_CODE_BLOCK_RE = re.compile(r"```.*?(?:```|$)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_XMLISH_BLOCK_RE = re.compile(r"<(pasted_content|file|document|code)[^>]*>.*?(?:</\1>|$)", re.DOTALL | re.IGNORECASE)

_SECRET_RES = [
    re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_\-]{12,}"),                 # OpenAI/Anthropic/Stripe style
    re.compile(r"\b(gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.DOTALL),
    re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|auth|bearer|パスワード|トークン)"
               r"(\s*[:=：]\s*|\s+)[\"']?[^\s\"'、。]{4,}"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),                              # long hex
    re.compile(r"\b(?=[A-Za-z0-9+/_\-]*\d)(?=[A-Za-z0-9+/_\-]*[A-Za-z])[A-Za-z0-9+/_\-]{32,}={0,2}"),  # long base64-ish
]
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"\b(?:https?|ftp|ssh|git|wss?|file)://[^\s<>\"'）)」]+|\bwww\.[^\s<>\"'）)」]+", re.IGNORECASE)
_PATH_RES = [
    re.compile(r"(?:~|[\w.\-]+)?(?:/[^\s/:*?\"<>|、。「」（）()]+){2,}/?"),   # unix paths (2+ segments)
    re.compile(r"[A-Za-z]:\\[^\s:*?\"<>|、。]+"),                        # windows paths
    re.compile(r"\b[\w.\-]+/[\w.\-/]+\.\w{1,6}\b"),                    # relative path with extension
    re.compile(r"\b[\w\-]+\.(?:py|rb|js|jsx|ts|tsx|go|rs|java|kt|swift|c|cc|cpp|h|hpp|cs|php|vue|svelte"
               r"|css|scss|html|json|ya?ml|toml|ini|env|md|sql|sh|lock|xml|csv|txt|log)\b", re.IGNORECASE),
]
_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b")
_HOST_RE = re.compile(r"\b(?:[A-Za-z0-9\-]+\.)+(?:com|net|org|io|ai|dev|app|co|jp|cloud|local|internal|so|me|us|uk|de|xyz|tech|info|biz)\b(?::\d+)?", re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<![\w])@[A-Za-z0-9_\-]{2,}")
_TICKET_RE = re.compile(r"(?<![\w])(#\d+|[A-Z][A-Z0-9]+-\d+)\b")
_NUM_RE = re.compile(r"\d{4,}")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[_\-.'][A-Za-z0-9]+)*")
_CJK_RE = re.compile(r"[぀-ヿ一-鿿가-힯]")

# Common English and everyday software words that are never names. Everything
# capitalized that is not here is treated as a possible proper noun.
_COMMON = set("""
a about above after again against all almost also always am an and any anything are around as ask at away back
bad be because been before being below best better between both but by can cannot change check clear could
data day did do does doing done down during each else end enough even every everything example fast few file
files find first fix for from full get give go going good got great had has have having he her here him his
how i if in instead into is it its just keep kind know last later least left less let like little look lot
make many maybe me might more most much must my need needs never new next no not nothing now of off ok okay
old on once one only open or other our out over own part please put quite rather read really right run same
say see seem set she should show side simple since small so some something still stop such sure take than
thank thanks that the their them then there these they thing things think this those though through time to
too try turn two under until up us use used using very want was way we well were what when where which while
who why will with without work would write yes yet you your yeah hi hello sorry also again first second third
add added adding api app apply bug bugs build branch call case cache ci cli click code command commit component
config console copy create css database debug default delete deploy design diff doc docs edit error errors
feature field fixed form function handle header html image import input install issue item json key layout
line link list load log logic login logout merge message method mode model module name page param path plan
plugin pr prod production pull push query readme refactor release remove rename request response result
return review route rule save schema screen script search server service session setting settings setup skill
spec sql staging state status step style table task test tests text title token tool type ui update url user
users value version view web window yaml review reviewed tested passing failing works working broken lint
agent agents prompt prompts output inputs outputs note notes card cards chart image images png svg markdown
readme local remote main master dev development frontend backend endpoint client token tokens auth parallel
python ruby javascript typescript react node rails go rust java swift kotlin docker git github npm yarn pip
rate limit limits limiting bump docs doc migration migrate rollback retry timeout queue job jobs worker event
events hook hooks cron schedule report summary done finished complete completed implement implemented
investigate investigated found looks look checked created updated fixed bumped added removed moved
""".split())


# --- Japanese proper nouns --------------------------------------------------------
_KATA = "ァ-ヺー"
_KANJI = "一-龯々〆ヶ"
# People: a name right before an honorific. Generic nouns that take 様/さん are kept.
_HONORIFIC_RE = re.compile(
    r"(?<![A-Za-z" + _KATA + _KANJI + r"])"
    r"([A-Za-z][A-Za-z0-9_\-]*|[" + _KATA + r"]{2,10}|[" + _KANJI + r"]{1,4})"
    r"(\s?)(さん|様|さま|氏|くん|君|ちゃん|殿)")
_HONORIFIC_KEEP = {"客", "お客", "皆", "皆々", "各位", "担当者", "担当", "利用者", "先方", "顧客", "管理者", "代理店",
                   "会員", "患者", "店員", "社員", "受講者", "参加者", "候補者", "相手", "先生", "御社", "貴社",
                   "利用者様", "ユーザー", "オペレーター", "お母", "お父", "奥", "旦那", "王", "神"}
# Companies: legal-form prefix, or a kanji/katakana stem plus a company-like suffix.
_COMPANY_RE = re.compile(
    r"(株式会社|有限会社|合同会社|一般社団法人|公益社団法人|一般財団法人|医療法人|学校法人)\s?[" + _KATA + _KANJI + r"A-Za-z0-9・]{1,15}"
    r"|[" + _KATA + _KANJI + r"]{1,12}(株式会社|製薬|銀行|商事|工業|電機|建設|不動産|証券|保険|ホールディングス"
    r"|製作所|薬品|物産|興業|電力|鉄道|信用金庫)")
# Addresses: prefecture followed by place names.
_ADDRESS_RE = re.compile(
    r"(北海道|東京都|京都府|大阪府|[" + _KANJI + r"]{2,3}県)"
    r"(?:[" + _KANJI + _KATA + r"0-9０-９\-－]|[ \u3000](?=[" + _KANJI + r"0-9０-９])){0,24}")
_KATA_RUN_RE = re.compile(r"[" + _KATA + r"・]{2,}")
# Common katakana words (loanwords). A katakana run is kept only if it can be
# split entirely into these; anything else (product, shop, person names) is masked.
_KATA_COMMON = set("""
アイコン アカウント アクション アクセス アップ アップデート アップロード アドレス アバター アプリ アプリケーション
アラート アルゴリズム アンケート イベント イメージ インストール インターフェース インデックス インポート ウィザード
ウィンドウ エージェント エクスポート エラー エリア エンジン エンジニア エントリ エンド オプション オフ オン オペレーター
オリジナル カウント カスタム カタカナ カテゴリ カテゴリー カード カバー カラム カレンダー キャッシュ キャラクター キャンセル
キュー キー キーワード クエリ クライアント クラス クラウド クリック クリア グループ ケース ゲスト コード コール コマンド
コミット コメント コンソール コンテキスト コンテナ コンテンツ コンポーネント コントローラー コピー コスト ゴール サーバー
サービス サイクル サイズ サイト サブ サポート サンプル シート システム シナリオ シフト ショート ジョブ スキーマ スキル
スクリプト スクリーンショット スクショ スクロール スケジュール スコア ステータス ステップ ストレージ スタイル スペース
スペック スレッド セッション セット センター ソース ソート ソフト タイトル タイプ タイマー タイミング タグ タスク タブ
ダイヤル ダイヤルパッド チーム チェック チケット チャット チャネル チャンネル ツール テーブル テキスト テスト デザイン
デバッグ デフォルト デプロイ データ データベース デモ トーク トークン トップ トピック トラブル トリガー ドキュメント
ドメイン ドラフト ナビ ネット ネットワーク ノート ハンドラ バー バグ バックアップ バックエンド バッジ バッチ バージョン
バリデーション パス パスワード パターン パッケージ パネル パフォーマンス パラメータ パーサー パース ビルド ビュー ビューア
ビューアー ファイル フィルタ フィルター フィールド フォーム フォルダ フォーマット フォロー フック フラグ フレーム
フロー フロント フロントエンド ブラウザ ブランチ ブロック プッシュ プラン プラグイン プレビュー プログラム プロジェクト
プロセス プロダクト プロパティ プロンプト ページ ヘッダー ベース ペイン ペース ベル ボタン ポート ポリシー マイグレーション
マージ マスター マップ マニュアル メール メイン メッセージ メニュー メモ メモリ メモリー メンバー メソッド モード モジュール
モデル モニター ユーザー ユニット ライブラリ ライン ラベル ランキング リアルタイム リクエスト リスト リセット リソース
リップシンク リトライ リポジトリ リマインド リモート リリース リンク リード ルート ルール レイアウト レコード レスポンス
レビュー レベル レポート ロール ロールプレイ ロープレ ローカル ロード ログ ログイン ロジック ロビー ワーク ワークフロー
アウト イン オート オートコール テンプレート トラッキング ステージング プロダクション ジャンル ナンバー オーダー
カスタマー サマリー サマリ チャート グラフ スライド コンテ アイデア アイディア ポイント メリット デメリット リスク
スタート ストップ ゴール ハイライト シンプル ミス ルーチン バランス ペア ベスト ルーム ホーム ヘルプ サイン サインイン
アリ ナシ カート ショップ ストア セール ニュース クーポン プレゼン ミーティング パソコン スマホ スマートフォン
タブレット ダッシュボード ログアウト サインアップ エディタ エディター ターミナル シェル ゲーム ストーリー キャンペーン
マーケティング セールス ビジネス メトリクス ダウンロード ハッシュ ハッシュタグ プロフィール アイテム グラフィック
ポップアップ モーダル トースト ドロップダウン チェックボックス ラジオ テキストボックス スピナー リロード キャプチャ
""".split())


# Short English function words. Capitalized in the middle of a sentence, they are
# almost always a name that happens to be spelled like one (e.g. a person "Or").
_FUNCTION_WORDS = set("a an and as at be by do for go he if in is it me my no of on or so the to up us we".split())


def _kata_ok(word: str) -> bool:
    w = word.replace("・", "")
    ok = [True] + [False] * len(w)
    for i in range(len(w)):
        if ok[i]:
            for j in range(i + 2, min(len(w), i + 14) + 1):
                if w[i:j] in _KATA_COMMON:
                    ok[j] = True
    return ok[len(w)]


def _japanese(t: str) -> str:
    t = _COMPANY_RE.sub(NAME, t)
    t = _ADDRESS_RE.sub(NAME, t)
    t = _HONORIFIC_RE.sub(lambda m: m.group(0) if m.group(1) in _HONORIFIC_KEEP
                          else NAME + m.group(2) + m.group(3), t)
    return _KATA_RUN_RE.sub(lambda m: m.group(0) if _kata_ok(m.group(0)) else NAME, t)


def _sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip(" \t\"'(")
    return not before or before[-1] in ".!?\n:。！？"


def _tokenwise(text: str, cjk_context: bool, terms_lower: set) -> str:
    out = []
    last = 0
    for m in _WORD_RE.finditer(text):
        word = m.group(0)
        start = m.start()
        out.append(text[last:start])
        last = m.end()
        low = word.lower()
        if low in terms_lower:
            out.append(NAME)
        elif re.search(r"[_\-.]", word) or (re.search(r"\d", word) and re.search(r"[A-Za-z]", word)):
            out.append(ID)
        elif re.search(r"[a-z][A-Z]", word) or (len(word) > 1 and word.isupper() and low not in _COMMON):
            out.append(ID if re.search(r"[a-z][A-Z]", word) else NAME)
        elif word[0].isupper() and word[1:].islower() and low in _FUNCTION_WORDS \
                and not _sentence_start(text, start):
            out.append(NAME)
        elif word[0].isupper() and low not in _COMMON and word != "I" \
                and not (_sentence_start(text, start) and re.fullmatch(r"[A-Z][a-z]+(ed|ing|ly)", word)):
            out.append(NAME)
        elif cjk_context and len(word) >= 3 and low not in _COMMON:
            out.append(NAME)
        else:
            out.append(word)
    out.append(text[last:])
    return "".join(out)


def _logish(line: str) -> bool:
    s = line.strip()
    if len(s) < 25:
        return False
    sym = sum(1 for c in s if not c.isalnum() and not c.isspace() and not _CJK_RE.match(c))
    return sym / len(s) > 0.25 or bool(re.match(r"^\s*(at |File \"|Traceback|\w+Error:|\[\d{2}:\d{2}|\d{4}-\d{2}-\d{2}[ T]\d{2}:)", line))


def redact(text: str, terms: Optional[Iterable[str]] = None, limit: Optional[int] = None) -> str:
    t = text.replace("**", "")   # bold markers would split names and addresses
    t = _CODE_BLOCK_RE.sub(" " + CODE + " ", t)
    t = _XMLISH_BLOCK_RE.sub(" " + CODE + " ", t)
    for rx in _SECRET_RES:
        t = rx.sub(SECRET, t)
    t = _EMAIL_RE.sub(EMAIL, t)
    t = _URL_RE.sub(URL, t)
    for rx in _PATH_RES:
        t = rx.sub(PATH, t)
    t = _IP_RE.sub(HOST, t)
    t = _HOST_RE.sub(HOST, t)
    t = _INLINE_CODE_RE.sub(CODE, t)
    t = "\n".join(LOG if _logish(line) else line for line in t.split("\n"))
    t = _MENTION_RE.sub(NAME, t)
    t = _TICKET_RE.sub(ID, t)
    # Everyday words (e.g. "test" from a branch name) are not identifying.
    terms_lower = {x.lower() for x in (terms or ()) if x} - _COMMON
    # Multi-word / non-Latin terms (e.g. Japanese project names) first.
    for term in sorted(terms_lower, key=len, reverse=True):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", term):
            t = re.sub(re.escape(term), NAME, t, flags=re.IGNORECASE)
    t = _japanese(t)
    t = _tokenwise(t, bool(_CJK_RE.search(t)), terms_lower)
    t = _NUM_RE.sub(NUM, t)
    t = re.sub("([" + CODE + LOG + r"])(\s*[" + CODE + LOG + r"])+", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if limit and len(t) > limit:
        t = t[:limit].rstrip() + "…"
    return "".join(_PH_BACK.get(c, c) for c in t)

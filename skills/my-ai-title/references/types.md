# タイプ定義（types.md）

## カードの構成

| 要素 | 決まり方 |
|---|---|
| 称号（二つ名＋役職） | 役職はタイプで固定、二つ名は選ばれた技名に対応する（例：沈黙の狙撃手） |
| キャラクター | タイプごとに固定 |
| セリフ | 選ばれた技名（二つ名）ごとに固定 |
| 技名と根拠 | タイプ内の複数パターンから、本人のログに最も強く出ている特徴で選ぶ |
| クセと根拠 | 本人のいちばん低い軸から選ぶ |
| レーダーチャート | 6軸のスコア |
| レア | タイプの軸が5点、タイプ別の実績、最低データ量の3条件 |

## 根拠の文を書くときのルール

- カードはSNSで公開される前提で書く。回数・割合・時間・時間帯などの具体的な数字は一切出さない。
- 数字の代わりに、本人の行動の描写と程度の言葉（「よく」「つい」「ほぼ毎回」「たいてい」）で表す。「自分のことだ」と思える具体的な場面を描くことを優先する。
- 働いている時間帯や、席を外している時間が読み取れる表現は使わない。
- クセは、同僚が見て「わかる」と笑える程度の自虐にとどめる。上司や採用担当が見て、仕事の品質や勤務態度を心配するような書き方はしない。
- 業務内容・コード・社名・ファイル名・プロジェクト名など、具体的な作業内容は一切書かない。
- 文の型はこのファイルのものを使う。言い回しを少し整えるのは可、意味を変えるのは不可。
- 条件の判定には extract.py が計算した数値を使う（数値はカードに出さない）。Claude の定性判断が必要な条件には（判定）と記した。
- 出力言語が日本語以外の場合は、技名・セリフ・クセの名前の固定訳（英語版で追加予定）を使い、根拠の文は同じ意味で訳す。

## 技名の選び方

1. そのタイプの技名パターンのうち、条件を満たすものを列挙する。
2. 各パターンの指標が、条件のしきい値をどれだけ上回っているか（倍率）を比べ、最も大きいものを選ぶ（倍率は内部の判定にだけ使い、カードには出さない）。
3. どれも満たさない場合は、各タイプの先頭のパターンを使う。
4. 英語表記は「The ＋英語の二つ名＋役職の英語名」（例：The Silent Sniper）。英語は自然な英語の言い回しを優先し、ハイフンでつないだ造語は避ける。カードではタイトルの下に表示する。
5. 選ばれた技名の二つ名と、タイプの役職名（「型」を除いた名前）をつなげて称号にする。二つ名はすべて「漢字＋の」の形で揃える。カードでは右側のタイトルに「二つ名の役職」を一行で表示する（例：怠惰の錬金術師）。長い場合は文字サイズを自動で縮める。

## クセの選び方

1. 6軸のうち最も低い軸を選ぶ。ただし、そのタイプを決めた軸は除く。同点なら、クセのパターンの条件をより大きく上回っている方。
2. その軸のクセのパターンから、条件のしきい値を最も大きく上回っているものを選ぶ。
3. 全軸が4以上の場合は、タイプ固有の「余裕のクセ」を使う。

---

## commander：司令塔型（Commander）

- 判定：委任と自律化が上位2軸
- テーマカラー：#2563EB　キャラクター：ヘッドセットのペンギン
- 共通セリフ（予備）：「あとは任せた」
- 余裕のクセ：AIが優秀すぎて、自分の仕事が見つからない

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 放牧 | 悠然の | Unhurried | 泰然自若の | Imperturbable | 「慌てなくていい、もう回ってる」 | 「もう全部、回ってる」 | 人が止めずに完走した自律実行が多い | AIを放っておいても、たいてい最後まで走りきる。牧場主の風格 |
| 分身の術 | 影分身の | Shadow Clone | 無限分身の | Infinite Clone | 「人手？いくらでも増やせるけど」 | 「人手は、無限にいる」 | 並列で動かしたエージェント数が多い | 気づけばAIを何体も同時に動かしている。本人は1人 |
| 丸ごと委任 | 全権の | Sovereign | 絶対権限の | All-Powerful | 「全部、承認」 | 「ハンコは、もう要らない」 | 指示1回あたりの変更範囲が広い | ひとこと頼むと、プロジェクトがまるごと動き出す |
| 一言委任 | 一声の | Laconic | 鶴の一声の | Final Word | 「…頼む」 | 「ん」 | 短い指示で大きな範囲を任せている | 指示は短いのに、任せる範囲は広い。信頼の厚さが違う |

- レア実績：人が途中で止めずに完走した自律実行が10回以上

## appraiser：鑑定士型（Appraiser）

- 判定：検証が最上位
- テーマカラー：#7C3AED　キャラクター：ルーペのキツネ
- 共通セリフ（予備）：「…本当に？」
- 余裕のクセ：信じるまでに時間がかかる

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 疑いの眼 | 懐疑の | Skeptical | 絶対懐疑の | Utterly Skeptical | 「その「できました」、根拠は？」 | 「私が見るまで、何も完了していない」 | AIの完了報告のあとに追加確認を頼む割合が高い | AIの「完了しました」を、まず疑ってかかる |
| 目視の鬼 | 千里眼の | Clairvoyant | 万里眼の | All-Seeing | 「画面、見せてもらえる？」 | 「見なくても分かる。ズレてる」 | 画面のスクリーンショットや動作確認をさせる回数が多い | 動いた、では信じない。画面を見せてもらうまでが確認 |
| テスト至上主義 | 鉄壁の | Ironclad | 金剛不壊の | Indestructible | 「テストが通るまでは信じない」 | 「バグのほうから逃げていく」 | テスト実行の回数が多い | 何かを変えたら、とりあえずテスト。もはや呼吸 |
| あら探し名人 | 慧眼の | Keen-Eyed | 神眼の | Infallible | 「ほら、ここ。ズレてる」 | 「直す前から、ここだと思ってた」 | AIの誤りを指摘し、それが正しかった回数が多い（判定） | AIの小さな間違いを、なぜかすぐ見つける |
| 多重チェック | 多重結界の | Thorough | 無限結界の | Infinite Barrier | 「確かめ方は一つじゃない」 | 「確かめ方は、あと100通りある」 | 検証手段の種類が多い | 確かめ方を何通りも持っていて、場面で使い分ける |

- レア実績：AIが完了と言った後に人が問題を見つけたタスクがほとんどない（目安5%以下）、かつ検証手段を3種類以上使っている

## architect：建築家型（Architect）

- 判定：文脈設計が最上位
- テーマカラー：#0E8A8A　キャラクター：設計図を広げるビーバー
- 共通セリフ（予備）：「まず全体像から話そう」
- 余裕のクセ：段取りが完璧すぎて、着手が遅く見える

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 段取り八分 | 先見の | Visionary | 未来視の | Prescient | 「まず全体像から話そう」 | 「その質問、3日後に来ると思ってた」 | 着手前に計画を立てさせる割合が高い | いきなり作らせない。まず計画を出させてから |
| 前提共有 | 叡智の | Sage | 大叡智の | Grand Sage | 「それ、前にメモしておいた」 | 「それ、半年前に書いておいた」 | プロジェクトの前提メモをよく更新している | プロジェクトの前提をこまめに書き残していて、AIが迷わない |
| 伝達完了 | 明晰の | Lucid | 明鏡止水の | Serene | 「ゴールはここ。以上」 | 「説明は、もういらない」 | 情報不足による手戻りがないタスクが続いている（判定） | 伝え漏れがほとんどない。AIが聞き返す必要がない |
| 調査から入る | 探求の | Inquiring | 真理探究の | Truth-Seeking | 「原因は、まだ決めつけない」 | 「原因の原因まで、見に行く」 | 原因を決めつけず、症状を渡して調べさせるタスクが多い（判定） | 原因を決めつけない。まずAIに調べさせてから考える |

- レア実績：情報不足による手戻りなしで終わったタスクが15件連続

## alchemist：錬金術師型（Alchemist）

- 判定：仕組み化が最上位
- テーマカラー：#D1306B　キャラクター：フラスコを掲げるカエル
- 共通セリフ（予備）：「これ、3回目だよね？」
- 余裕のクセ：仕組みを作るのが楽しくて、本題を忘れる

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 二度手間アレルギー | 怠惰の | Lazy | 究極怠惰の | Supremely Lazy | 「働くのは、仕組みのほう」 | 「今日も一行も書いてない」 | 繰り返された指示が、仕組み化のあと出なくなった | 同じことを何度か頼んだら、すぐ仕組みにしてしまう |
| 道具箱 | 百器の | Resourceful | 千器の | Infinitely Resourceful | 「その作業、道具あるよ」 | 「道具がない作業、ある？」 | 自作の再利用できる仕組みの呼び出しが多い | 自分で作った道具を、毎日のように使いこなしている |
| 自動錬成 | 永久機関の | Perpetual | 真・永久機関の | Truly Perpetual | 「勝手に回るようにしといた」 | 「止め方、忘れちゃった」 | 自動で動く仕掛けがよく発動している | 本人が何もしなくても、仕掛けが勝手に働いている |
| 量産体制 | 量産の | Prolific | 大量錬成の | Mass Transmutation | 「また一つ、作っちゃった」 | 「寝てる間に10個できてた」 | 新しく作った仕組みが多く、かつ使われている | 新しい仕組みを次々に生み出して、ちゃんと使っている |

- レア実績：自作の再利用できる仕組みを月20回以上使っている

## sniper：狙撃手型（Sniper）

- 判定：介入効率が最上位
- テーマカラー：#3F7D20　キャラクター：スコープを覗くフクロウ
- 共通セリフ（予備）：「…指示は一度しか言わない」
- 余裕のクセ：仕様が3行しかないチケット

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 一撃必中 | 百発百中の | Bullseye | 千発千中の | Unerring | 「当然でしょ」 | 「外し方を知らない」 | 指示2回以内で終わるタスクが多い | たいてい1〜2回の指示で片づく。AIが質問する隙がない |
| 精密射撃 | 精密の | Precision | 神業の | Godhand | 「あと1ミリ、右」 | 「0.1ミリ、右」 | 依頼に完了条件をつけている割合が高い（判定） | 依頼にはほぼ毎回ゴールが書いてある。AIは迷子になれない |
| 早撃ち | 閃光の | Flash | 光速の | Lightspeed | 「もう終わったけど？」 | 「頼まれる前に、終わってた」 | タスク完了までの時間が短い | 頼んでから終わるまでが、とにかく速い |
| 無言の圧 | 沈黙の | Silent | 絶対沈黙の | Utterly Silent | 「…指示は一度しか言わない」 | 「……」 | 短い指示で通している | 指示は短いのに、ちゃんと通る。AIが空気を読んでいる |

- レア実績：指示2回以内、手直しなしで完了したタスクが10件以上

## partner：相棒型（Partner）

- 判定：対話を重ねて進めるスタイル（1タスクあたりの往復が多く、かつ成果が採用されている）
- テーマカラー：#E07B0A　キャラクター：吹き出しの柴犬
- 共通セリフ（予備）：「ちょっと聞いてほしいんだけど」
- 余裕のクセ：「結論から言うと」と言われること

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 無限壁打ち | 千夜一夜の | Thousand Nights | 万夜一夜の | Endless Nights | 「ちょっと聞いてほしいんだけど」 | 「まだ話の途中なんだけど」 | 1セッションの往復数が多い | 話し始めると止まらない。壁打ちが長いほど答えが良くなる |
| 比較検討 | 審美眼の | Discerning | 至高審美の | Supremely Discerning | 「AとB、どっちがいいと思う？」 | 「AもBも違う。Cだ」 | 複数の案を比べてから決めたセッションが多い（判定） | 一案では決めない。いくつか並べてから選ぶ |
| 逆質問 | 問いかけの | Inquisitive | 問答無双の | Socratic | 「先に質問していいよ」 | 「質問が終わる頃には、答えも出てる」 | AIに質問させてから始めたタスクが多い（判定） | 始める前に、AIに質問させて考えを整理する |
| ひとり会議 | 独白の | Soliloquy | 開眼の | Awakened | 「…あ、話してたら分かった」 | 「話す前から、分かってた」 | 説明しているうちに自分で答えに気づく場面が多い（判定） | AIに説明しているうちに、自分で答えに気づいている |

- レア実績：壁打ちで複数の案を比べてから決めたセッションが10件以上

## explorer：冒険者型（Explorer）

- 判定：全体がまだ伸び始め（平均3未満）
- テーマカラー：#A8741A　キャラクター：リュックとコンパスのタヌキ
- 共通セリフ（予備）：「とりあえずやってみよう」
- 余裕のクセ：（全軸4以上なら別タイプになるため使わない）

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 好奇心 | 好奇の | Curious | 無限好奇の | Boundlessly Curious | 「これもAIでいけるかな？」 | 「AIでいけないもの、まだ見つからない」 | AIを使った作業の種類が多い | あれもこれも、とりあえずAIに頼んでみている |
| 急成長 | 新星の | Rising Star | 超新星の | Supernova | 「先月の自分とは違う」 | 「先週の自分にも、もう勝てる」 | 前回から伸びた軸がある | 前回より{axis}がぐっと伸びた。今いちばん伸びている |
| 皆勤賞 | 不断の | Tireless | 不撓不屈の | Indomitable | 「今日もやるか」 | 「やめる理由が、見つからない」 | 利用が途切れず続いている | AIと組まない日のほうが珍しい |
| 初挑戦 | 開拓の | Pioneering | 大開拓の | Trailblazing | 「まだ誰も試してない使い方」 | 「地図にない道しか歩かない」 | 新しい使い方を試した数が多い | 新しい使い方を見つけると、すぐ試している |

- レア実績：前回から2点以上伸びた軸がある

## conductor：指揮者型（Conductor）

- 判定：全軸が4以上
- テーマカラー：#B8323A　キャラクター：タクトを振るライオン
- 共通セリフ（予備）：「全員、持ち場につけ」
- 余裕のクセ：AIの使い方を聞かれて、昼休みが消える

| 技名 | 二つ名 | 英語 | レア二つ名 | レア英語 | セリフ | レアセリフ | 条件 | 根拠の文 |
|---|---|---|---|---|---|---|---|---|
| 全軍指揮 | 万軍の | Legion | 百万軍の | Million-Strong | 「全員、持ち場につけ」 | 「全軍、好きに動け。それで勝てる」 | 並列実行が多く、かつ手直しが少ない | AIを何体も同時に動かして、しかも後から直すことがほぼない |
| 適材適所 | 采配の | Strategist | 神采配の | Masterstroke | 「ここは任せる。ここは私が」 | 「もう、全員の役割が見えている」 | タスクの性質で任せ方を変えている（判定） | 任せるところと自分で握るところの見極めが的確 |
| 死角なし | 完全無欠の | Flawless | 唯一無二の | One-and-Only | 「特に、言うことはない」 | 「比べる相手が、いない」 | 全軸が4以上 | 6つの力がどれも高い。死角が見当たらない |

- レア実績：全軸4以上で、かつ他タイプのレア実績を2つ以上満たしている

---

## クセのパターン（軸ごと）

| 軸 | クセの名前 | 条件 | 根拠の文 |
|---|---|---|---|
| 文脈設計 | 後出しの「あ、あと」 | 補足による手戻りが多い（判定） | 頼んだあとで「あ、あと」と付け足しがち |
| 文脈設計 | 前提の口伝 | 同じ前提の説明を繰り返している | 同じ前提を、毎回口で説明し直している |
| 委任力 | 細かすぎる指示 | 指示1回あたりの作業量が小さい | 一歩ずつ指示しがち。AIはもっと走れるのに |
| 委任力 | 抱え込み | AIに任せず自分で直した変更が多い | AIが書いたものを、つい自分で書き直してしまう |
| 検証力 | 信じやすい | 確認なしで採用し、後から直したものが多い | AIの「できました」を、つい信じてしまう |
| 検証力 | 最後は自分の目 | AIの完了後に人が見つけた問題が多い | 最後はやっぱり自分の目で探している |
| 自律化設計 | 放置できない | 自律実行中に割り込んだ回数が多い | AIの作業中、つい様子を見に行ってしまう |
| 自律化設計 | 途中下車 | 自律実行を途中で止めた回数が多い | 走り出したAIを、途中で止めたくなる |
| 介入効率 | 長期戦 | 1タスクあたりの往復が多い | 一つのタスクで、AIとの往復が長くなりがち |
| 介入効率 | 方向転換 | 途中で方針を変えたタスクが多い（判定） | 作りながら、行き先が変わりがち |
| 仕組み化 | 毎回手書き | 似た指示の繰り返しが多い | 似たようなお願いを、毎回手で書いている |
| 仕組み化 | 眠れる道具 | 作ったのに使っていない仕組みが多い | 作った道具が、引き出しで眠っている |

## レアの共通条件

レア版では、二つ名が「レア二つ名」に、セリフが「レアセリフ」に格上げされる（例：沈黙の狙撃手「…指示は一度しか言わない」→ 絶対沈黙の狙撃手「……」）。実績の説明はカードに出さない。

次の3つをすべて満たすとレア版になる。

1. そのタイプを決めた軸が5点（冒険者型は除く。指揮者型は全軸4以上）
2. タイプごとのレア実績を満たす
3. 対象期間のセッションが20以上

しきい値は仮置き。実際の分布を見て、全体のおよそ10人に1人がレアになるよう調整する。

---

## ID・カード番号・英語版（English）

英語版カードと画像ファイル名に使う。技名のIDは画像ファイル名 `{type}_{ID}.png` に使う。カード番号（No.）はこの表の上からの順番。英語の文は自然な英語を優先し、意味を変えない範囲で言い回しを整えている。

### タイプ

| type | 役職 | Role | 余裕のクセ（英語） |
|---|---|---|---|
| commander | 司令塔 | Commander | The AI is so capable there's no work left to do |
| appraiser | 鑑定士 | Appraiser | Takes a while to trust anything |
| architect | 建築家 | Architect | The prep is so thorough it looks like a slow start |
| alchemist | 錬金術師 | Alchemist | Building tools is so fun the real task gets forgotten |
| sniper | 狙撃手 | Sniper | Tickets with three-line specs |
| partner | 相棒 | Partner | Being told "get to the point" |
| explorer | 冒険者 | Explorer | (not used) |
| conductor | 指揮者 | Conductor | Asked how to use AI so often that lunch disappears |

### 技名

| type | ID | 技名 | Name | Quote | Rare quote | Evidence |
|---|---|---|---|---|---|---|
| commander | pasture | 放牧 | Free Range | No need to rush. It's already running. | It's all running already. | Leave the AI alone and it usually runs all the way to the end. A true rancher. |
| commander | clone | 分身の術 | Shadow Clones | Need more hands? I can make more. | I have endless hands. | Always has several AIs running at once. Still just one person. |
| commander | fullpower | 丸ごと委任 | Full Delegation | Approved. All of it. | Signatures? Not needed anymore. | One request, and the whole project starts moving. |
| commander | onevoice | 一言委任 | Word of Command | …Handle it. | Mm. | Short instructions, wide scope. That's how deep the trust goes. |
| appraiser | doubt | 疑いの眼 | Eye of Doubt | "Done," you say. Proof? | Nothing is done until I've seen it. | Meets every "all done" from the AI with healthy suspicion. |
| appraiser | farsight | 目視の鬼 | Seeing Is Believing | Can you show me the screen? | I don't need to look. It's off. | "It works" isn't enough. The check ends when the screen is shown. |
| appraiser | ironwall | テスト至上主義 | Tests Above All | I don't believe it until the tests pass. | Bugs run away on their own. | Change anything, run the tests. It's basically breathing. |
| appraiser | keeneye | あら探し名人 | Bug Hunter | See? Right here. It's off. | I knew it was here before we fixed it. | Somehow spots the AI's small mistakes right away. |
| appraiser | multicheck | 多重チェック | Layered Checks | There's more than one way to check. | There are a hundred more ways to check. | Has many ways to verify, and picks the right one for each situation. |
| architect | foresight | 段取り八分 | Plan First | Let's start with the big picture. | I knew you'd ask that three days from now. | Never jumps straight to building. A plan comes first. |
| architect | sage | 前提共有 | Shared Context | I already wrote that down. | I wrote that down six months ago. | Keeps the project's background written down, so the AI never gets lost. |
| architect | lucid | 伝達完了 | Crystal Clear | The goal is here. That's all. | No more explanation needed. | Hardly anything gets left out. The AI never has to ask back. |
| architect | inquiry | 調査から入る | Investigate First | Let's not decide the cause yet. | Let's find the cause of the cause. | Never jumps to conclusions. Lets the AI investigate first, then thinks. |
| alchemist | sloth | 二度手間アレルギー | Allergic to Repeats | The system does the work. | Haven't written a single line today. | Ask for the same thing a few times, and it soon becomes a tool. |
| alchemist | hundredtools | 道具箱 | Toolbox | There's a tool for that. | Is there any job without a tool? | Uses homemade tools almost every day. |
| alchemist | perpetual | 自動錬成 | Auto Transmutation | I set it up to run on its own. | I forgot how to stop it. | Even when no one touches anything, the setup keeps working. |
| alchemist | massproduce | 量産体制 | Mass Production | Oops, made another one. | Ten more appeared overnight. | Keeps creating new tools, and actually uses them. |
| sniper | bullseye | 一撃必中 | One Shot, One Hit | Obviously. | I don't know how to miss. | Most things are done in one or two instructions. No room for the AI to ask. |
| sniper | precision | 精密射撃 | Precision Shot | One millimeter to the right. | A tenth of a millimeter to the right. | Almost every request comes with a clear goal. The AI can't get lost. |
| sniper | flash | 早撃ち | Quick Draw | Already done. Why? | It was done before you asked. | From request to done, simply fast. |
| sniper | silence | 無言の圧 | Silent Pressure | …I only say it once. | …… | Short instructions that land anyway. The AI reads the room. |
| partner | endless | 無限壁打ち | Endless Sparring | Hey, can I run something by you? | I'm not done talking yet. | Once the talk starts, it keeps going. The longer the back-and-forth, the better the answer. |
| partner | connoisseur | 比較検討 | Weighing Options | A or B, what do you think? | Neither A nor B. It's C. | Never settles on one idea. Lines up a few, then chooses. |
| partner | asking | 逆質問 | Questions First | Go ahead, ask me first. | By the time the questions end, the answer is there. | Before starting, lets the AI ask questions to sort out the thinking. |
| partner | monologue | ひとり会議 | Thinking Out Loud | …Oh, saying it out loud helped. | I knew before I said it. | Explaining things to the AI often turns up the answer midway. |
| explorer | curious | 好奇心 | Curiosity | Could AI handle this too? | Still haven't found anything AI can't do. | Hands all kinds of things to the AI, just to see. |
| explorer | risingstar | 急成長 | Growth Spurt | Not the same as last month. | Already beating last week's self. | {axis} has jumped since last time. Growing fastest right now. |
| explorer | tireless | 皆勤賞 | Perfect Attendance | Let's do this again today. | Can't find a reason to stop. | A day without teaming up with the AI is the rare one. |
| explorer | pioneer | 初挑戦 | First Try | A way of using it no one has tried yet. | I only walk roads that aren't on the map. | Finds a new way to use AI and tries it right away. |
| conductor | legion | 全軍指揮 | Command of Legions | Everyone, take your positions. | All units, move freely. We win anyway. | Runs many AIs at once, and hardly ever has to fix anything afterward. |
| conductor | strategist | 適材適所 | Right Task, Right Hands | This part's yours. This part's mine. | I already see everyone's role. | Knows exactly what to delegate and what to keep. |
| conductor | flawless | 死角なし | No Blind Spots | Nothing in particular to add. | There's no one to compare with. | All six strengths are high. No weak spot in sight. |

### 軸

| axis | 軸 | Axis |
|---|---|---|
| context | 文脈設計 | Context Design |
| delegation | 委任力 | Delegation |
| verification | 検証力 | Verification |
| autonomy | 自律化設計 | Autonomy Design |
| efficiency | 介入効率 | Intervention Efficiency |
| systems | 仕組み化 | Systematization |

### クセ

| axis | ID | クセの名前 | Name | Evidence |
|---|---|---|---|---|
| context | afterthought | 後出しの「あ、あと」 | "Oh, and one more thing" | Tends to tack on "oh, and also…" after asking. |
| context | oral | 前提の口伝 | Oral Tradition | Explains the same background out loud, every single time. |
| delegation | micromanage | 細かすぎる指示 | Baby Steps | Gives instructions one step at a time. The AI could run much further. |
| delegation | hoarder | 抱え込み | Can't Let Go | Ends up rewriting by hand what the AI wrote. |
| verification | gullible | 信じやすい | Trusting Soul | Tends to take the AI's "done!" at face value. |
| verification | lasteye | 最後は自分の目 | Final Inspection | In the end, still hunting for problems by eye. |
| autonomy | hover | 放置できない | Can't Look Away | While the AI works, keeps peeking in to see how it's going. |
| autonomy | stopper | 途中下車 | Emergency Brake | Once the AI gets going, the urge to stop it kicks in. |
| efficiency | marathon | 長期戦 | The Long Game | A single task tends to turn into a long back-and-forth. |
| efficiency | uturn | 方向転換 | Change of Course | The destination tends to shift mid-build. |
| systems | handwritten | 毎回手書き | Handwritten Every Time | Writes similar requests by hand, every time. |
| systems | sleeping | 眠れる道具 | Sleeping Tools | The tools that got built are asleep in a drawer. |

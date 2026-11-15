# Tomato-hime 64 — サラダの国のトマト姫 C64 移植ビルダー

ハドソンの PC-9801 版アドベンチャー「サラダの国のトマト姫」(1984) を、**Commodore 64 で遊べる形に変換するツール**です。
(An English summary follows below.)

## 大事なこと

**このリポジトリにはゲームのデータ(絵・単語表・日本語の文章など)は含まれていません。**
例外として、`lang/` に英語・スペイン語の**非公式ファン翻訳**(ゲームの文章を訳したもの)が入っています。元の日本語文は含まず、各文のハッシュ値で対応づけています。
自分で持っている PC-9801 版のディスクイメージ(D88)から、手元のパソコン上で C64 用ディスク(D64)を組み立てます。
ゲームの著作権はハドソン(現・コナミデジタルエンタテインメント)にあります。

## C64 版の特徴

- 全シナリオ(154 シーン)をそのまま変換。文章は元のカタカナ表記
- コマンドはファミコン版のような選択式(移動・ミル・アゲル…/名詞は場面ごとに自動生成)
- 絵は元の線画・塗りデータを C64 上で実際に描画(描いていく様子が見えます)
- 画面上部に絵、下部に文章とコマンド
- セーブ/ロード(任意のディスクに `TOMATOSAV` を保存)、最初からやり直し
- D64 2 枚組(1541 ドライブ)。カナ表示には 8×8 ドットの美咲フォントを使用
- オリジナル BGM(SID 3 音、場面に応じて 5 曲)。システム メニューで音量 6 段階
- 日本語版のほか、英語版・スペイン語版も作れます(`--lang en` / `--lang es`)

## 必要なもの

- Python 3.8 以降(標準ライブラリのみ、追加インストール不要)
- PC-9801 版「サラダの国のトマト姫」のディスクイメージ(D88 形式)
  - ハドソンのオリジナル版(5 インチ 2DD、自己起動ディスク)を推奨
  - N88-BASIC の 2HD ディスクにファイルを移したコピー版(SARADAP0〜P4)でも、同じ結果になります

ビルダーはゲームデータのチェックサムでディスクを確認します。違うディスクでも警告を出して続行しますが、正しく動かない可能性があります。

| 版 | 確認するデータ | CRC32 |
|---|---|---|
| 2DD オリジナル | 地域 B / C / D / A(論理トラック 3–13 / 14–19 / 20–27 / 28–38) | 616c4fb8 / 4df9a0ae / 3a107e6c / bfe3fc6a |
| 2HD コピー | SARADAP0 / P1 / P2 / P3 / P4 | ca1acb16 / ff3f6465 / 75a17343 / da67b1cb / 9490b213 |

## 使い方

```
python3 build.py サラダの国のトマト姫.d88
```

`tomato_c64_1.d64` と `tomato_c64_2.d64` ができます。出力名は第 2 引数で変えられます(例: `python3 build.py game.d88 out/tomato_`)。

英語版・スペイン語版:

```
python3 build.py サラダの国のトマト姫.d88 --lang en
python3 build.py サラダの国のトマト姫.d88 --lang es
```

それぞれ `tomato_c64_en_1.d64` / `tomato_c64_es_1.d64` などができます。翻訳版では英字に C64 本体の文字 ROM を使い(起動時に ROM から写します)、スペイン語のアクセント文字は自作の 8×8 グリフです。

C64(または VICE)でディスク 1 から起動します。

```
LOAD"*",8,1
RUN
```

### 操作

| キー / ジョイスティック(ポート 2) | 動作 |
|---|---|
| ← → (カーソルキー / ジョイスティック左右) | 項目を選ぶ |
| RETURN / スペース / ファイア | 決定 |
| X / ← キー | 戻る・取り消し |

メニュー右端の「システム」からセーブ・ロード・ハジメカラ(最初から)を選べます。
ディスクの交換が必要になると画面で指示が出ます。

## 仕組み(概要)

- `tools/source.py` … D88 を読み、N88-BASIC(86) の FAT からゲームファイルを取り出す
- `tools/sym.py`, `tools/convert.py` … 元の 8086 コード(各シーンの処理)を記号実行して、条件分岐・フラグ操作・文章表示のルールに変換
- `tools/encode.py` … ルールを C64 エンジン用のバイトコードに変換
- `src/engine.asm` … C64 エンジン(メニュー、スクリプト VM、ディスク読み込み、セーブ/ロード、ラスター割り込みによる絵と文字の分割表示)
- `src/vecrender.asm` … 元の絵データ(移動・線・塗り)を C64 上で描画するルーチン
- `tools/asm6502.py`, `tools/d64.py` … 自作の 6502 アセンブラと D64 作成ツール

技術的な詳細は [docs/TECHNICAL.md](docs/TECHNICAL.md) を参照してください。

## ライセンス

- このリポジトリのコード: MIT License([LICENSE](LICENSE))
- `fonts/misaki_gothic_2nd.bdf`: 美咲フォント © Num Kadoma(門真なむ)。フリーソフトウェアとして配布されています。詳細は [fonts/README.md](fonts/README.md) と公式サイト <https://littlelimit.net/misaki.htm> を参照してください。
- `lang/en.json`, `lang/es.json`: 非公式のファン翻訳。原文の著作権はハドソン/コナミデジタルエンタテインメントにあります。権利者から求めがあれば削除します。
- 音楽(`tools/music.py`)はこの移植のためのオリジナル曲です(MIT)。
- 「サラダの国のトマト姫」の著作権はハドソン/コナミデジタルエンタテインメントに帰属します。本ツールは非公式のもので、権利者とは無関係です。

---

## English summary

A converter that turns your own copy of Hudson's PC-9801 adventure *Salad no Kuni no Tomato-hime* (1984, known in the West
through the NES remake *Princess Tomato in the Salad Kingdom*) into a two-disk Commodore 64 version.

- **No game data is included in this repository.** You need a PC-9801 disk image (D88): the original Hudson 2DD disk, or the 2HD N88-BASIC copy. Everything is extracted locally.
- Full scenario (154 scenes), original Japanese katakana text, plus unofficial English and Spanish fan translations (`--lang en`, `--lang es`).
- Original SID background music (5 tunes), volume control in the System menu.
- NES-style command menus instead of a typed parser.
- The original vector pictures (moves, lines, flood fills) are rendered on the C64 itself.
- Save/load to any disk, restart, 1541 two-disk set. 8x8 Misaki font for kana.

Usage: `python3 build.py your_image.d88 [--lang ja|en|es]` (Python 3.8+, standard library only), then `LOAD"*",8,1` / `RUN` from disk 1.
Both the original Hudson 2DD disk and the 2HD N88-BASIC copy are accepted.
Controls: left/right to choose, RETURN/space/fire to confirm, X or ← to go back.

Code and music: MIT. Font: Misaki Gothic by Num Kadoma (free software); the translated builds copy Latin letters from the C64's own character ROM at start-up.
The translations in `lang/` are unofficial fan translations of the game text (the Japanese originals are not included; strings are matched by hash) and will be removed on request of the rights holder.
The game itself is © Hudson Soft / Konami; this is an unofficial fan project.

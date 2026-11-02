# 空耳アワーデータベース

[空耳アワーアップデート](https://www7a.biglobe.ne.jp/~soramimiupdate/) に掲載された全作品（1992年4月〜2023年3月）を収集したデータベースです。

## 生成物（`data/`）

| ファイル | 内容 |
| --- | --- |
| `works.csv` / `works.json` | 全作品。1行1作品 |
| `soramimi.sqlite` | SQLite 版。`works` / `specials` / `work_specials` / `artists` の4テーブル |
| `awards.json` | 空耳アワードのグランプリ受賞作（特番ページの本文から手動で抽出） |
| `overrides.json` | 表ではなく本文にだけ賞品が書かれている作品の評価の補正（理由つき） |
| `unmatched_reruns.json` | 特番で紹介されたが元作品に紐付けられなかった行 |
| `build_report.txt` | 賞品総数表との突き合わせ結果 |
| `fc2_compare.txt` | 副データソース（下記）と本データとの照合結果 |
| `artist_aliases.json` | 表記ゆれのグループごとの `artist_key`（別名表） |
| `artist_apple.json` | Apple Music の照会結果 |
| `artist_corrections.json` / `artist_corrected.json` | 誤記や略称を正しい名前で再照会するための指定とその結果 |
| `artist_overrides.json` | `artist_key` を手動で指定する行（理由つき） |
| `fc2_works.json` | 副データソースの全行。リポジトリには含めない（`.gitignore` 済み、下記の手順で生成） |

### 作品のカラム

| カラム | 内容 |
| --- | --- |
| `date` | 放送日。特番で初披露された作品は特番の放送日 |
| `artist` / `title` / `lyric` / `soramimi` | アーティスト名 / 曲名 / 原詞 / 空耳 |
| `artist_key` | 表記ゆれを統一したアーティスト名（下記） |
| `rating` | 評価なし / 手ぬぐい / ミミかき / Tシャツ / ジャンパー のいずれか。複数賞品のときは高い方 |
| `rating_other` | サイトの評価欄が上記5つのいずれでもない場合、その原文（複数賞品・限定手ぬぐい・ギリギリ・物品など） |
| `specials` | 紹介された空耳特番の名前（CSV では `|` 区切り）。1992年の「あなたにも音楽を」邦楽回と、ユーミン特番内の「空ユミ」コーナーも特番として扱う |
| `award` | 「空耳アワード」でグランプリを受賞した作品はその特番名 |
| `rating_raw` / `src` | サイトの評価欄の原文 / 取得元ページ |
| `rating_source` | `site`（元サイトの表）か `fc2`（元サイトの表に評価がなく副データソースから補完） |
| `rating_fc2` / `fc2_no` | 副データソースでの評価と行番号。両ソースの食い違いを確認できる |

## 副データソース

[空耳アワー詳細データ分類一覧表](http://soranari001.web.fc2.com/soramimi_data_classification.html)（3494 作品）を `scripts/parse_fc2.py` で取り込み、
放送日と空耳の類似度で 1 対 1 に照合しています（3474 件が一致）。照合できなかった行は放送日が 1 週ずれているか、
片方にしかない作品（1992 年の邦楽回、ユーミン特番の空ユミ作品など）です。

- 元サイトの表に評価欄がない作品（特番ページのゲスト投稿作品など）と、1992 年の評価欄に原詞が入っている表の作品、計 24 件は副データソースの評価で補完しました（`rating_source = fc2`）。
- 両ソースで評価が食い違う作品が 8 件あります。元サイトは表と本文の記述が一致しているため元サイトの値を採用し、副データソースの値は `rating_fc2` に残しています。

## `artist_key` を決める手順

1. `scripts/artist_groups.py` が、英語名または日本語名を正規化した値でサイトの表記をグループにまとめます（1531 グループ）。
2. `scripts/apple_lookup.py` が、グループごとに Apple Music（日本）のアーティスト名を照会します。
3. `scripts/apple_corrections.py` が、誤記や略称のグループを正しい名前で再照会します（The Crash → The Clash、CCR → Creedence Clearwater Revival など）。
4. `scripts/artist_aliases.py` が、次の優先順で `artist_key` を決めます。
   1. `artist_overrides.json` の手動指定
   2. Apple Music のカタカナ表記
   3. Apple Music にカタカナ表記がなければ、Apple Music の英字表記（Led Zeppelin など）
   4. Apple Music で見つからなければ、サイトの日本語表記

別名と略称は同じ `artist_key` にまとめます（The Artist Formerly Known As Prince → プリンス、Rhapsody → Rhapsody of Fire など）。
feat. やコラボ名義はまとめず、別の `artist_key` にします。

## 再生成

副データソースのデータはリポジトリに含めていないので、最初に次の手順で取得します。
取得しない場合、`build.py` は副データソースによる評価の補完を行わず、一部の作品の評価が欠けます。

```sh
mkdir -p cache/raw/fc2 data
curl -sS -o cache/raw/fc2/soramimi_data_classification.html \
  http://soranari001.web.fc2.com/soramimi_data_classification.html
python3 scripts/parse_fc2.py   # data/fc2_works.json を生成
```

取得済みなら再取得は不要です。続けて次を実行します。

```sh
scripts/fetch.sh <URL>   # ページを cache/ に保存（取得済みなら再取得しない）
scripts/convert.sh       # cache/raw → cache/utf8（文字コード変換）
python3 scripts/artist_groups.py      # アーティスト表記をグループ化
python3 scripts/apple_lookup.py       # Apple Music を照会（結果は cache/apple/ に保存し、中断後は続きから再開）
python3 scripts/apple_corrections.py  # 誤記や略称を再照会
python3 scripts/artist_aliases.py     # data/artist_aliases.json を生成
python3 scripts/build.py # data/ を生成し、賞品総数表と突き合わせる
```

`data/artist_apple.json` と `data/artist_corrected.json` がリポジトリにあるので、`artist_key` の再計算だけなら `artist_aliases.py` からで足ります。

`cache/` は `.gitignore` 済みです。サイトへのアクセスは初回取得時のみで、以後はキャッシュを使います。
取得対象は `past.htm` から辿れる年別ページ、`special.htm` の特番ページ、およびトップページからのみリンクされている
2021〜2023年の特番ページです。

## 突き合わせ結果

サイトの「賞品総数表」（手ぬぐい 2266 / ミミかき 452 / Tシャツ 660 / ジャンパー 59）との差は `data/build_report.txt` を参照。
Tシャツは総数表の 660 に対して本データは 707、副データソースは 705 で、2 つの独立した集計がほぼ一致しています。
年別ページの「発行された賞品総数」を合計しても 685 になるため、総数表の 660 の方が実際より少ないと判断しています。

ジャンパーは [過去のジャンパー作品](https://www7a.biglobe.ne.jp/~soramimiupdate/jumper.htm) の 59 作品と 1 件ずつ照合済みです。
2015/10/30 の「ジャケット」はジャンパーとして数え、表に評価欄がない 2 作品は `overrides.json` で補正しています。
同ページで 2022/9/10 とされている 2 作品は、'21サマーコレクション（2021/9/10 放送）の作品として扱っています。

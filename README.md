# colabgame

Google Colaboratory の中で **pygame・pyxel・turtle** のゲームを、キーボードやマウスを使ってリアルタイムに遊べるようにするライブラリです。

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR_NAME/colabgame/blob/main/examples/demo.ipynb)

## 使い方

Colab のセルで次を実行します。

```python
!pip install -q git+https://github.com/blackcaty1224/colabgame.git
import colabgame
```

あとは、ゲームのコードの1行目に `%%game` と書いて実行するだけです。

```python
%%game
import pygame
pygame.init()
screen = pygame.display.set_mode((640, 480))
clock = pygame.time.Clock()
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    screen.fill((30, 30, 50))
    pygame.display.flip()
    clock.tick(60)
```

出力欄にゲーム画面が出ます。画面を一度クリックすると、キーボード操作が効くようになります。

### オプション

| 書き方 | 意味 |
|---|---|
| `%%game turtle` | ライブラリを指定する（ふつうは import から自動判定） |
| `%%game --height 700` | 表示エリアの高さを変える |
| `%%game --assets player.png,sounds` | 一緒に読み込むファイルやフォルダを指定する |
| `%%game --window` | 別のタブで開くリンクも表示する |
| `%%game --show-code` | ブラウザ用に書き換えたコードを表示する |
| `%game_file mygame.py` | `.py` ファイルを実行する（上のオプションも使えます） |

コードの中に `"player.png"` のようにファイル名が書かれていて、そのファイルが Colab 上に実在すれば、`--assets` を書かなくても自動で一緒に読み込まれます。

Python から直接呼ぶこともできます。

```python
colabgame.play(code_string)          # 文字列のコードを実行
colabgame.play_file("mygame.py")     # ファイルを実行
print(colabgame.transform(code))     # 書き換え後のコードを確認
```

## しくみ

Colab の Python は Google のサーバーで動いていて、画面もキーボードもつながっていません。そこで colabgame は、ゲームを **ブラウザの中で動く形（WebAssembly）に変換して**、出力欄の中で動かします。ゲームはあなたのパソコンのブラウザで動くので、遅延なく 60fps で遊べます。

| ライブラリ | ブラウザで動かす方法 |
|---|---|
| pygame | [pygbag](https://github.com/pygame-web/pygbag) でビルド |
| pyxel | pyxel 公式の Web 出力（`pyxel package` → `pyxel app2html`） |
| turtle | [Pyodide](https://pyodide.org/) と、このライブラリに入っている canvas 版 turtle |

ブラウザの中の Python は、ときどき処理をブラウザに返さないと画面が更新されません。普通に書いた `while` ループのゲームはそれをしないので、colabgame はコードを自動で書き換えて、ループの中に「1フレーム待つ」処理を入れます（`time.sleep()` も同じように置き換えます）。

ビルドしたファイルは Colab の中の小さな Web サーバーから配信され、Colab のポート転送機能で出力欄に表示されます。

## できないこと・注意点

- 実行中のゲームは Colab のサーバー側の変数や GPU には触れません（ブラウザの中で動いているため）。
- 自動の書き換えは、よくある書き方（トップレベルの `while` ループ、`main()` 関数、クラスの `run()` メソッドなど）を想定しています。凝った書き方で画面が固まるときは、ループの中に `await asyncio.sleep(0)` を自分で書いて、`asyncio.run(main())` で起動してください。そうしたコードは書き換えずにそのまま使われます。
- pygame: 初回は pygbag のインストールとビルドに1分ほどかかります。ブラウザの仕様で、音を出すために最初に画面のクリックが必要です。`pygame.event.wait()` のように入力を止まって待つ命令は使えません。
- pyxel: `pyxel.run()` を使うゲームに対応しています。`pyxel.flip()` を使うループはブラウザ版の pyxel では使えません。
- turtle: 本物の turtle の主な命令（移動、ペン、塗りつぶし、文字、スタンプ、キーとマウスの入力、`ontimer`、画像のシェイプなど）に対応しています。`undo()`、`radians()`、`getcanvas()` など一部は未対応です。
- tkinter・pyglet・arcade・Ursina など、デスクトップのウィンドウに依存するライブラリは動きません。

## 新しいライブラリに対応させるには

`colabgame/backends/` に、`DEFAULT_HEIGHT`・`transform(code)`・`build(code, workdir, copy_assets)` を持つモジュールを追加し、`backends/__init__.py` の `BUILDERS` と `detect.py` の `BACKENDS` に名前を登録します。

## テスト

```bash
pip install pygame
python tests/test_asyncify.py
```

## ライセンス

MIT

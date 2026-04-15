# PDF OCR Prototype

PDF を画像化し、`owocr` と Chrome Screen AI を使って OCR を実行し、テキストおよび Markdown 形式で結果を保存するアプリのサンプルです。`Streamlit` ベースの画面から、ローカル PDF の選択またはアップロードを行えます。

## 使用方法

要: Docker Engine

```bash
docker compose build
docker compose up
```

起動後、ブラウザで `http://localhost:8501` を開いて PDF を選択し、`Start OCR` を実行してください。

OCR の入力 PDF は `data/input`、途中生成物は `data/work`、出力される `.txt` と `.md` は `data/output` に保存されます。

## 権利者表記

このプロジェクトは OCR 処理に `owocr` を利用しています。

- 名称: `owocr`
- 作者: AuroraWright
- リポジトリ: https://github.com/AuroraWright/owocr
- ライセンス: GPL-3.0

`owocr` は原著作者により提供される独立したオープンソースソフトウェアです。`owocr` 自体の著作権およびライセンス条件は権利者に帰属します。詳細は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) と [LICENSE](LICENSE) を参照してください。

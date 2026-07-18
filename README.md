# オントロジー実装デモ（料理・食材・アレルゲン）

OWL 2 オントロジーを Python で構築し、**推論器による知識の自動導出**と **SPARQL による照会**を体験する最小デモです。題材は「料理・食材・アレルゲン」で、次のような推論が動きます。

- 親子丼は鶏肉（肉類）を含む → **肉料理（MeatDish）に自動分類**
- 親子丼は醤油を含み、醤油は小麦を含む → **親子丼は小麦アレルゲンを含む**（プロパティチェーン推論）

## 2026年時点の最新動向（このデモの背景）

- **RDF 1.2 が勧告候補（Candidate Recommendation）に到達**（2026年4月）。トリプル自体に出典や確信度を注釈できる「トリプルターム」（旧 RDF-star）が標準化の目玉です。[W3C ニュース](https://www.w3.org/news/2026/w3c-invites-implementations-of-rdf-1-2-concepts-and-abstract-data-model-and-rdf-1-2-semantics/)
- **SPARQL 1.2 は Working Draft 段階**（[Query Language](https://www.w3.org/TR/sparql12-query/) 2026年4月版、[Update](https://www.w3.org/TR/sparql12-update/) 2026年6月版など）。
- **LLM × オントロジー**が研究・実務の中心トピックに。LLM でオントロジー構築を加速する方向（[survey](https://www.sciencedirect.com/science/article/pii/S1570826825000022)、[LLMs4KGOE ワークショップ @ESWC 2026](https://koncordantlab.github.io/LLM4KGOE-ESWC/)）と、逆にオントロジーで LLM をグラウンディングしてハルシネーションを抑える方向（[神経記号アーキテクチャ](https://arxiv.org/html/2604.00555v2)）の両輪で進んでいます。
- Python 実装の定番は [Owlready2](https://owlready2.readthedocs.io/en/latest/)（0.51、HermiT/Pellet 推論器同梱）と [rdflib](https://rdflib.readthedocs.io/)（7.x）。本デモもこの 2 つ＋ [owlrl](https://pypi.org/project/owlrl/) を使います。

> 注: rdflib 7.6 は RDF 1.2 のトリプルターム構文（`<<( s p o )>>`）を未サポートのため、`rdf12_annotation_demo.py` では RDF 1.2 の書き方を提示しつつ、現行ツールで動く等価表現（RDF 1.1 reification）で実演しています。

## 構成

```
ontology-demo/
├── src/
│   ├── build_ontology.py        # ① オントロジー構築 (Owlready2) → OWL/Turtle 出力
│   ├── run_reasoner.py          # ② HermiT 推論器で自動分類・プロパティ値導出 (要 Java)
│   ├── query_sparql.py          # ③ SPARQL クエリ + OWL 2 RL 推論 (owlrl, Java 不要)
│   └── rdf12_annotation_demo.py # ④ RDF 1.2 トリプルターム（ステートメント注釈）の紹介
├── output/                      # 生成物 (.owl / .ttl) — スクリプトが再生成
└── requirements.txt
```

## セットアップ

```bash
git clone https://github.com/bitpackman/ontology-demo.git
cd ontology-demo
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

- Python 3.9+ を想定（開発環境: 3.11 / Raspberry Pi OS）
- ②の HermiT 推論器のみ **Java 実行環境が必要**です（OpenJDK 17 で動作確認）。Java なしでも③の owlrl で同等の推論デモが動きます。

## 実行

```bash
.venv/bin/python src/build_ontology.py        # ① オントロジーを構築
.venv/bin/python src/run_reasoner.py          # ② HermiT で推論
.venv/bin/python src/query_sparql.py          # ③ SPARQL + OWL 2 RL
.venv/bin/python src/rdf12_annotation_demo.py # ④ RDF 1.2 注釈デモ
```

②の出力例（推論前後の比較）:

```
=== 推論前（明示的に書いた知識のみ） ===
  親子丼            型: [Dish]  アレルゲン: [なし]
  ...
=== 推論後（HermiT が導出した知識を含む） ===
  親子丼            型: [GlutenDish, MeatDish]  アレルゲン: [卵, 大豆, 小麦(グルテン)]
  天ぷらそば          型: [GlutenDish, SeafoodDish]  アレルゲン: [えび・かに, そば, 大豆, 小麦(グルテン)]
```

## このデモで学べる OWL 2 / SPARQL の機能

| 機能 | 使用箇所 |
|---|---|
| クラス階層・Disjoint 宣言 | `Meat ⊑ Ingredient`、肉/魚介/野菜/穀物は互いに素 |
| 定義クラス（必要十分条件） | `MeatDish ≡ Dish ⊓ ∃hasIngredient.Meat` → 個体の自動分類 |
| hasValue 制約 | `GlutenDish ≡ Dish ⊓ ∋hasAllergen.gluten` |
| プロパティチェーン | `hasIngredient ∘ containsAllergen ⊑ hasAllergen` |
| 逆プロパティ / Functional データプロパティ | `ingredientOf`、`calories` |
| 多言語ラベル | `rdfs:label`（ja / en） |
| タブロー法推論 vs ルールベース推論 | HermiT（②）と OWL 2 RL / owlrl（③）の比較 |
| SPARQL 1.1 プロパティパス・集計 | `hasIngredient/containsAllergen`、`GROUP_CONCAT`、`COUNT` |
| ステートメント注釈（RDF 1.2 の方向性） | ④ 出典・確信度をトリプルに付与 |

## ライセンス

[MIT License](LICENSE)

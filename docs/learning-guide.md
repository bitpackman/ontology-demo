# オントロジー体系的学習ガイド

このリポジトリのデモを教材として、オントロジー技術を基礎から実務まで段階的に学ぶためのガイドです。各ステージに「目標 / このリポジトリでの対応 / 主要リソース / 到達チェック」を示します。

```
Stage 1        Stage 2       Stage 3          Stage 4       Stage 5         Stage 6        Stage 7
RDF/トリプル → SPARQL   →   RDFS/OWL 2   →   推論      →   設計方法論   →  実務運用    →  LLM 連携
(データモデル)  (問い合わせ)   (語彙と公理)     (知識の導出)   (どう作るか)    (SHACL/DB)     (2026 トレンド)
```

前提知識: プログラミング基礎（Python が読める程度）。集合と述語論理の初歩があると Stage 3 以降が楽になります。

---

## Stage 1: RDF — トリプルでデータを表す

**目標**: 「主語・述語・目的語」のトリプルモデルと IRI・リテラル・ブランクノードを理解し、Turtle 形式を読み書きできる。

**このリポジトリで**: `src/build_ontology.py` を実行し、生成された `output/cuisine.ttl` を開いて読む。`cuisine:oyakodon cuisine:hasIngredient cuisine:chicken .` のような行がすべてトリプルです。

**主要リソース**:
- [RDF 1.1 Primer (W3C)](https://www.w3.org/TR/rdf11-primer/) — 入門の定番
- [RDF 1.2 Concepts (W3C, 2026年勧告候補)](https://www.w3.org/TR/rdf12-concepts/) — トリプルターム（言明への注釈）が新要素。`src/rdf12_annotation_demo.py` 参照
- [Turtle 仕様](https://www.w3.org/TR/turtle/)

**到達チェック**: `cuisine.ttl` に自分の好きな料理を Turtle で 1 品追記し、`usecase/allergen_checker.py` の判定に反映されることを確認できる。

---

## Stage 2: SPARQL — グラフに問い合わせる

**目標**: SELECT / FILTER / OPTIONAL / GROUP BY / プロパティパスを使ったクエリが書ける。

**このリポジトリで**: `src/query_sparql.py` の 5 つのクエリを読み、改造する。特にクエリ 2 のプロパティパス `cuisine:hasIngredient/cuisine:containsAllergen` は「推論なしで 2 ホップ辿る」重要テクニック。

**主要リソース**:
- [SPARQL 1.1 Query Language (W3C 勧告)](https://www.w3.org/TR/sparql11-query/)
- [SPARQL 1.2 Query (Working Draft)](https://www.w3.org/TR/sparql12-query/) — 次期仕様の動向
- 実データでの練習: [Wikidata Query Service](https://query.wikidata.org/)（例が豊富）

**到達チェック**: 「カロリーが 300kcal 以下で大豆を含まない料理」を返すクエリを自力で書ける。

---

## Stage 3: RDFS / OWL 2 — 語彙と公理でスキーマを定義する

**目標**: クラス階層・プロパティの定義域/値域・存在制約 (someValuesFrom)・hasValue・プロパティチェーン・Disjoint を理解し、「必要十分条件による定義クラス」が書ける。開世界仮説 (OWA) と閉世界仮説 (CWA) の違いを説明できる。

**このリポジトリで**: `src/build_ontology.py` を読む。`MeatDish ≡ Dish ⊓ ∃hasIngredient.Meat` が定義クラスの例。Owlready2 の Python 記法と、出力された OWL (RDF/XML・Turtle) を対応付けて読むと理解が深まります。

**主要リソース**:
- [OWL 2 Primer (W3C)](https://www.w3.org/TR/owl2-primer/) — 最重要文書
- [Protégé](https://protege.stanford.edu/) + [Pizza Tutorial](https://www.michaeldebellis.com/post/new-protege-pizza-tutorial) — GUI で公理を組む古典的演習
- 書籍: *Semantic Web for the Working Ontologist* (Allemang & Hendler & Gandon)

**到達チェック**: 「デザート ≡ 料理 ⊓ 糖類を含む」のような定義クラスを追加し、推論器に分類させられる。OWA のせいで「ベジタリアン料理」の定義が単純には書けない理由を説明できる。

---

## Stage 4: 推論 — 書いていない知識を導出する

**目標**: タブロー法推論器 (HermiT/Pellet) とルールベース推論 (OWL 2 RL) の違い、OWL 2 プロファイル (EL/QL/RL) の使い分けを理解する。

**このリポジトリで**: 同じ推論を 2 方式で実行して比較する。
- `src/run_reasoner.py` — HermiT（タブロー法・OWL DL 完全・要 Java）
- `src/query_sparql.py` — owlrl（ルールベース・OWL 2 RL・純 Python。199→601 トリプルに閉包が拡大）

親子丼が MeatDish に分類され、プロパティチェーンで hasAllergen が導出される過程を両方で確認する。

**主要リソース**:
- [OWL 2 Profiles (W3C)](https://www.w3.org/TR/owl2-profiles/) — EL(巨大医療オントロジー向け) / QL(DB問い合わせ向け) / RL(ルールエンジン向け)
- 記述論理の教科書: *An Introduction to Description Logic* (Baader ら)
- 推論器: [HermiT](http://www.hermit-reasoner.com/), [ELK](https://github.com/liveontologies/elk-reasoner)（EL 特化・高速）

**到達チェック**: 「なぜ野菜炒め(豚入り)は MeatDish と推論されるのか」を公理とルールの適用列で説明できる。

---

## Stage 5: オントロジー設計方法論 — 良いオントロジーの作り方

**目標**: 要求定義から検証までの設計プロセスを回せる。既存オントロジーを再利用できる。

**学ぶこと**:
1. **コンピテンシー質問 (CQ)** — 「このオントロジーが答えるべき質問」を先に列挙する（例: 本リポジトリの CQ は「ある料理はどのアレルゲンを含むか」「肉を使わない料理はどれか」）
2. **既存語彙の再利用** — ゼロから作らない。[schema.org](https://schema.org/)、[SKOS](https://www.w3.org/TR/skos-primer/)、[FOAF](http://xmlns.com/foaf/spec/)、ドメイン特化なら FIBO（金融）、SNOMED CT（医療）、[FoodOn](https://foodon.org/)（食品！）
3. **オントロジーデザインパターン** — [ODP ポータル](http://ontologydesignpatterns.org/)
4. **方法論** — NeOn Methodology、METHONTOLOGY、アジャイル的な [SAMOD](https://essepuntato.it/samod/)

**このリポジトリで**: 料理オントロジーを FoodOn の該当クラスにマッピング（`owl:equivalentClass` / `rdfs:subClassOf`）してみる。

**到達チェック**: 自分のドメイン（業務でも趣味でも）について CQ を 10 個書き、それに答える最小オントロジーを設計できる。

---

## Stage 6: 実務運用 — 検証・格納・公開

**目標**: データ品質検証 (SHACL)、トリプルストア運用、公開のベストプラクティスを身につける。

**このリポジトリで**: `usecase/shacl_validation.py` を実行。OWL 推論（開世界・導出）と SHACL 検証（閉世界・制約）の役割分担が実務の要点です。`usecase/allergen_checker.py` は「推論結果を業務ロジックに組み込む」例。

**学ぶこと**:
- [SHACL (W3C 勧告)](https://www.w3.org/TR/shacl/) と [pySHACL](https://github.com/RDFLib/pySHACL)
- トリプルストア: [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/)（無料・入門に最適）、GraphDB、Amazon Neptune、Virtuoso
- 公開: コンテンツネゴシエーション、[FAIR 原則](https://www.go-fair.org/fair-principles/)、PID 設計（`w3id.org` など）
- 命名・バージョニング規約: IRI は変えない、`owl:versionInfo` / `owl:deprecated` の運用

**到達チェック**: Fuseki を立てて `cuisine.ttl` をロードし、HTTP 経由の SPARQL エンドポイントとして `curl` から照会できる。

---

## Stage 7: LLM × オントロジー — 2026 年のフロンティア

**目標**: LLM とオントロジーの相互補完（構築の自動化 ⇄ 出力のグラウンディング）を理解し、最小構成を実装できる。

**このリポジトリで**: `usecase/nl_ontology_qa.py` を読む・動かす。
- 自然言語 → SPARQL 生成（LLM は語彙リストのみ参照・構造化出力で形式を保証）
- クエリはローカルの推論済みグラフで実行（事実の出所は常に知識グラフ）
- 回答生成はクエリ結果のみを根拠にさせる（ハルシネーション抑制）

**学ぶこと**:
- オントロジーで LLM を接地する: 神経記号アーキテクチャ（例: [Ontology-Constrained Neural Reasoning](https://arxiv.org/html/2604.00555v2)）
- LLM でオントロジー構築を加速する: [survey (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1570826825000022)、NeOn-GPT、マルチエージェント方式
- コミュニティ: [LLMs4KGOE ワークショップ @ESWC](https://koncordantlab.github.io/LLM4KGOE-ESWC/)
- 発展: GraphRAG（知識グラフ×検索拡張生成）、Text2SPARQL ベンチマーク

**到達チェック**: `nl_ontology_qa.py` の語彙記述を改造し、自作オントロジーに対する自然言語 QA を動かせる。LLM が語彙に無いプロパティを使ったときに検出・再生成する仕組みを追加できる。

---

## 学習の進め方の目安

| 期間の目安 | 内容 |
|---|---|
| 1週目 | Stage 1–2: Turtle を読み、SPARQL を書く（毎日 1 クエリ） |
| 2–3週目 | Stage 3–4: OWL 2 Primer を読みつつ Protégé Pizza Tutorial、本リポジトリの公理を改造 |
| 4–5週目 | Stage 5: 自分のドメインで CQ →最小オントロジー設計 |
| 6週目 | Stage 6: SHACL シェイプを書く、Fuseki で公開 |
| 7週目〜 | Stage 7: LLM 連携の改造・拡張 |

## 総合演習課題（このリポジトリを使って）

1. **メニュー拡張**: 料理を 10 品・食材を 20 種追加し、`DessertDish`（甘味料を含む料理）の定義クラスを作って自動分類させる
2. **ベジタリアン判定**: OWA のもとで「ベジタリアン対応」を安全に表現する方法を設計する（ヒント: 閉包公理、または SHACL + 明示フラグ）
3. **FoodOn マッピング**: 食材クラスを FoodOn の IRI に `rdfs:subClassOf` で接続し、外部語彙との相互運用を体験する
4. **SPARQL エンドポイント化**: Fuseki + 推論済みグラフで API を立て、`allergen_checker` を HTTP クライアントに書き換える
5. **LLM 検証ループ**: `nl_ontology_qa.py` に「生成 SPARQL の構文検証 → 失敗時に再生成」のループを実装する

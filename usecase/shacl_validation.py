"""実践ユースケース②: SHACL によるデータ品質検証。

知識グラフを実運用すると「新しいメニューデータの投入」が日常的に発生する。
OWL の推論は開世界仮説 (OWA) のため「食材が書かれていない」ことをエラーに
できないが、SHACL (W3C 勧告) は閉世界的な制約検証ができる。

このスクリプトは:
  1. Dish に対する SHACL シェイプ (制約) を定義する
     - 食材を 1 つ以上持つこと
     - カロリーは 0〜2000 の整数で高々 1 つ
     - 日本語ラベルを持つこと
  2. 既存データを検証 → 適合
  3. 不正な新規メニューを混ぜて検証 → 違反レポートを表示
"""

from pathlib import Path

from pyshacl import validate
from rdflib import Graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

SHAPES_TTL = """
@prefix sh:      <http://www.w3.org/ns/shacl#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix cuisine: <https://example.org/onto/cuisine#> .

cuisine:DishShape
    a sh:NodeShape ;
    sh:targetClass cuisine:Dish ;
    sh:property [
        sh:path cuisine:hasIngredient ;
        sh:minCount 1 ;
        sh:class cuisine:Ingredient ;
        sh:message "料理は食材を 1 つ以上持ち、値は Ingredient でなければならない" ;
    ] ;
    sh:property [
        sh:path cuisine:calories ;
        sh:datatype xsd:integer ;
        sh:minInclusive 0 ;
        sh:maxInclusive 2000 ;
        sh:maxCount 1 ;
        sh:message "カロリーは 0〜2000 の整数で高々 1 つ" ;
    ] ;
    sh:property [
        sh:path rdfs:label ;
        sh:minCount 1 ;
        sh:message "料理にはラベルが必要" ;
    ] .
"""

# 投入されてきた「不正な」新規メニューデータ:
# 食材なし・カロリーが文字列・ラベルなし
BAD_RECORD_TTL = """
@prefix cuisine: <https://example.org/onto/cuisine#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

cuisine:mystery_dish a cuisine:Dish ;
    cuisine:calories "たくさん" .
"""


def run_validation(data: Graph, title: str) -> None:
    shapes = Graph().parse(data=SHAPES_TTL, format="turtle")
    conforms, _report_graph, report_text = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="rdfs",  # サブクラス (Meat ⊑ Ingredient) を考慮して sh:class を評価
    )
    print(f"\n=== {title} ===")
    print(f"適合 (conforms): {conforms}")
    if not conforms:
        print(report_text)


def main() -> None:
    ttl = OUTPUT_DIR / "cuisine.ttl"
    if not ttl.exists():
        raise SystemExit("output/cuisine.ttl がありません。先に src/build_ontology.py を実行してください。")

    data = Graph().parse(ttl, format="turtle")
    run_validation(data, "検証①: 既存メニューデータ (正常)")

    data.parse(data=BAD_RECORD_TTL, format="turtle")
    run_validation(data, "検証②: 不正な新規メニューを追加後 (違反を検出)")


if __name__ == "__main__":
    main()

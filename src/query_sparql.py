"""rdflib による SPARQL クエリと、owlrl (純 Python) による OWL 2 RL 推論のデモ。

HermiT (Java) を使わなくても、OWL 2 RL プロファイルの範囲ならルールベース推論で
同等の分類・導出ができることを示す。プロパティパス (SPARQL 1.1) を使えば
推論なしでもアレルゲンを辿れることも比較する。

先に build_ontology.py を実行して output/cuisine.ttl を生成しておくこと。
"""

from pathlib import Path

import owlrl
from rdflib import Graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

PREFIXES = """
PREFIX cuisine: <https://example.org/onto/cuisine#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

QUERIES = {
    "1. 料理一覧（日本語ラベルとカロリー）": PREFIXES + """
SELECT ?labelJa ?cal WHERE {
  ?dish a cuisine:Dish ; rdfs:label ?labelJa ; cuisine:calories ?cal .
  FILTER(LANG(?labelJa) = "ja")
}
ORDER BY DESC(?cal)
""",
    "2. プロパティパスでアレルゲンを辿る（推論不要・SPARQL 1.1）": PREFIXES + """
SELECT ?dishLabel (GROUP_CONCAT(DISTINCT ?aLabel; separator=", ") AS ?allergens) WHERE {
  ?dish cuisine:hasIngredient/cuisine:containsAllergen ?a .
  ?dish rdfs:label ?dishLabel . FILTER(LANG(?dishLabel) = "ja")
  ?a rdfs:label ?aLabel .      FILTER(LANG(?aLabel) = "ja")
}
GROUP BY ?dishLabel
""",
    "3. OWL 2 RL 推論後: 肉料理として分類された個体": PREFIXES + """
SELECT ?dishLabel WHERE {
  ?dish a cuisine:MeatDish ; rdfs:label ?dishLabel .
  FILTER(LANG(?dishLabel) = "ja")
}
""",
    "4. OWL 2 RL 推論後: プロパティチェーン由来の hasAllergen": PREFIXES + """
SELECT ?dishLabel ?aLabel WHERE {
  ?dish cuisine:hasAllergen ?a .
  ?dish rdfs:label ?dishLabel . FILTER(LANG(?dishLabel) = "ja")
  ?a rdfs:label ?aLabel .      FILTER(LANG(?aLabel) = "ja")
}
ORDER BY ?dishLabel ?aLabel
""",
    "5. 集計: 料理ごとの食材数": PREFIXES + """
SELECT ?dishLabel (COUNT(?ing) AS ?numIngredients) WHERE {
  ?dish cuisine:hasIngredient ?ing ; rdfs:label ?dishLabel .
  FILTER(LANG(?dishLabel) = "ja")
}
GROUP BY ?dishLabel
ORDER BY DESC(?numIngredients)
""",
}


def run_query(g: Graph, title: str, query: str) -> None:
    print(f"\n--- {title} ---")
    rows = list(g.query(query))
    if not rows:
        print("  (結果なし)")
    for row in rows:
        print("  " + " | ".join(str(v) for v in row))


def main() -> None:
    ttl_path = OUTPUT_DIR / "cuisine.ttl"
    if not ttl_path.exists():
        raise SystemExit("output/cuisine.ttl がありません。先に build_ontology.py を実行してください。")

    g = Graph()
    g.parse(ttl_path, format="turtle")
    print(f"読み込み: {ttl_path} ({len(g)} トリプル)")

    # クエリ 1, 2 は明示的な知識＋プロパティパスだけで動く
    for title in list(QUERIES)[:2]:
        run_query(g, title, QUERIES[title])

    # OWL 2 RL のルールベース推論で閉包を計算（純 Python・Java 不要）
    before = len(g)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    print(f"\nOWL 2 RL 閉包を計算: {before} → {len(g)} トリプル")

    for title in list(QUERIES)[2:]:
        run_query(g, title, QUERIES[title])


if __name__ == "__main__":
    main()

"""実践ユースケース: 運航管理 (OCC) ダッシュボード。

OWL 2 RL 推論 (owlrl, 純 Python・Java 不要) + SPARQL で、運航管理者が朝一で
見たい情報を知識グラフから引き出す。

  1. 影響便アラート    — 整備事象の機材からの波及 (プロパティチェーン推論) を含む
  2. 遅延の波及リスク  — 機材繰り (rotatesTo+) を推移的にたどって下流便を洗い出す
  3. 乗務資格チェック  — 便の機種に対する型式限定を持たないパイロットを検出 (閉世界チェック)
  4. 運航サマリ        — 推論による分類 (国内線/ワイドボディ/影響便) の集計

先に build_ontology.py を実行して output/aviation.ttl を生成しておくこと。
"""

from pathlib import Path

import owlrl
from rdflib import Graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

PREFIXES = """
PREFIX avi:  <https://example.org/onto/aviation#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

QUERIES = {
    "1. 影響便アラート（整備・天候起因、推論による波及を含む）": PREFIXES + """
SELECT ?flight ?dep ?cause WHERE {
  ?f a avi:DisruptedFlight ;
     rdfs:label ?flight ;
     avi:scheduledDeparture ?dep ;
     avi:affectedBy ?event .
  ?event rdfs:label ?cause .
  FILTER(LANG(?flight) = "ja" && LANG(?cause) = "ja")
}
ORDER BY ?dep
""",
    "2. 遅延の波及リスク（機材繰り rotatesTo+ の下流便）": PREFIXES + """
SELECT ?delayedFlight ?downstream ?dep WHERE {
  ?f avi:affectedBy ?d .
  ?d a avi:Delay .
  ?f rdfs:label ?delayedFlight .
  ?f avi:rotatesTo+ ?g .
  ?g rdfs:label ?downstream ;
     avi:scheduledDeparture ?dep .
  FILTER(LANG(?delayedFlight) = "ja" && LANG(?downstream) = "ja")
}
ORDER BY ?dep
""",
    "3. 乗務資格チェック（型式限定を持たない割当 = 違反）": PREFIXES + """
SELECT ?flight ?pilot ?model WHERE {
  ?f avi:operatedWithModel ?m ;    # 推論で導出された運航機種
     avi:hasCrew ?p ;
     rdfs:label ?flight .
  ?p a avi:Pilot ; rdfs:label ?pilot .
  ?m rdfs:label ?model .
  FILTER NOT EXISTS { ?p avi:ratedOn ?m }
  FILTER(LANG(?flight) = "ja" && LANG(?pilot) = "ja" && LANG(?model) = "ja")
}
""",
    "4. 運航サマリ（推論による分類の集計）": PREFIXES + """
SELECT ?category (COUNT(DISTINCT ?f) AS ?flights) WHERE {
  VALUES ?cls { avi:DomesticFlight avi:WidebodyFlight avi:DisruptedFlight }
  ?f a ?cls .
  ?cls rdfs:label ?category .
  FILTER(LANG(?category) = "ja")
}
GROUP BY ?category
ORDER BY DESC(?flights)
""",
}


def main() -> None:
    ttl = OUTPUT_DIR / "aviation.ttl"
    if not ttl.exists():
        raise SystemExit("output/aviation.ttl がありません。先に build_ontology.py を実行してください。")

    g = Graph()
    g.parse(ttl, format="turtle")
    before = len(g)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    print(f"OWL 2 RL 閉包を計算: {before} → {len(g)} トリプル")

    for title, query in QUERIES.items():
        print(f"\n--- {title} ---")
        rows = list(g.query(query))
        if not rows:
            print("  (該当なし)")
        for row in rows:
            print("  " + " | ".join(str(v) for v in row))


if __name__ == "__main__":
    main()

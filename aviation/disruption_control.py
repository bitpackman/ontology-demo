"""イレギュラー運航統制 (IROPS) ダッシュボード。

build_irregular_scenario.py が生成した「台風21号シナリオ」に対して、
OWL 2 RL 推論 + SPARQL で統制業務の判断材料を出す。

  0. What-if 比較   — 台風統制の「前後」で影響便がどう変わるかを差分表示
  1. 空港統制の内訳 — どの便が・どちら側 (出発/到着) の空港制限で影響を受けたか
  2. 波及経路の追跡 — 機材繰り (rotatesTo+) と乗務員繰り (crewConnectsTo) の 2 系統
  3. 影響旅客       — AffectedPassenger の推論結果と原因の一覧
  4. 統制サマリ

先に build_irregular_scenario.py を実行しておくこと。
"""

from pathlib import Path

import owlrl
from rdflib import Graph, Namespace, RDF, RDFS

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
AVI = Namespace("https://example.org/onto/aviation#")

PREFIXES = """
PREFIX avi:  <https://example.org/onto/aviation#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

Q_AIRPORT_CONTROL = PREFIXES + """
SELECT DISTINCT ?flight ?dep ?side ?airport WHERE {
  ?f avi:affectedBy ?event .
  ?event a avi:Typhoon .
  ?f rdfs:label ?flight ; avi:scheduledDeparture ?dep .
  {
    ?f avi:departsFrom ?ap . ?ap avi:disruptedBy ?event .
    BIND("出発空港" AS ?side)
  } UNION {
    ?f avi:arrivesAt ?ap . ?ap avi:disruptedBy ?event .
    BIND("到着空港" AS ?side)
  }
  ?ap rdfs:label ?airport .
  FILTER(LANG(?flight) = "ja" && LANG(?airport) = "ja")
}
ORDER BY ?dep
"""

# 影響便から機材繰りで到達できる、まだ影響判定されていない下流便
Q_ROTATION_RISK = PREFIXES + """
SELECT DISTINCT ?srcFlight ?dstFlight ?dep WHERE {
  ?src a avi:DisruptedFlight ; rdfs:label ?srcFlight .
  ?src avi:rotatesTo+ ?dst .
  FILTER NOT EXISTS { ?dst a avi:DisruptedFlight }
  ?dst rdfs:label ?dstFlight ; avi:scheduledDeparture ?dep .
  FILTER(LANG(?srcFlight) = "ja" && LANG(?dstFlight) = "ja")
}
ORDER BY ?dep
"""

# 影響便から「乗務員繰りを少なくとも 1 回経由して」到達できる下流便
# (機材は別でも乗務員が乗り継ぐため波及しうる)
Q_CREW_RISK = PREFIXES + """
SELECT DISTINCT ?srcFlight ?dstFlight ?dep WHERE {
  ?src a avi:DisruptedFlight ; rdfs:label ?srcFlight .
  ?src (avi:rotatesTo|avi:crewConnectsTo)*/avi:crewConnectsTo/(avi:rotatesTo|avi:crewConnectsTo)* ?dst .
  FILTER NOT EXISTS { ?dst a avi:DisruptedFlight }
  ?dst rdfs:label ?dstFlight ; avi:scheduledDeparture ?dep .
  FILTER(LANG(?srcFlight) = "ja" && LANG(?dstFlight) = "ja")
}
ORDER BY ?dep
"""

Q_AFFECTED_PAX = PREFIXES + """
SELECT ?pax ?flight ?cause WHERE {
  ?p a avi:AffectedPassenger ; rdfs:label ?pax ; avi:bookedOn ?f .
  ?f a avi:DisruptedFlight ; rdfs:label ?flight ; avi:affectedBy ?e .
  ?e rdfs:label ?cause .
  FILTER(LANG(?pax) = "ja" && LANG(?flight) = "ja" && LANG(?cause) = "ja")
}
ORDER BY ?pax ?flight
"""


def label_ja(g: Graph, node) -> str:
    for lab in g.objects(node, RDFS.label):
        if getattr(lab, "language", None) == "ja":
            return str(lab)
    return str(node)


def disrupted_flights(g: Graph) -> set:
    return set(g.subjects(RDF.type, AVI.DisruptedFlight))


def closure(g: Graph) -> Graph:
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    return g


def run(g: Graph, title: str, query: str) -> list:
    print(f"\n--- {title} ---")
    rows = list(g.query(query))
    if not rows:
        print("  (該当なし)")
    for row in rows:
        print("  " + " | ".join(str(v) for v in row))
    return rows


def main() -> None:
    ttl = OUTPUT_DIR / "aviation_irregular.ttl"
    if not ttl.exists():
        raise SystemExit("output/aviation_irregular.ttl がありません。"
                         "先に build_irregular_scenario.py を実行してください。")

    raw = Graph()
    raw.parse(ttl, format="turtle")

    # --- 0. What-if: 台風統制 (disruptedBy) を取り除いた世界と比較する ---
    baseline = Graph()
    for t in raw:
        if t[1] != AVI.disruptedBy:  # 空港の運用制限だけを取り除く
            baseline.add(t)
    closure(baseline)
    scenario = closure(raw)

    before = disrupted_flights(baseline)
    after = disrupted_flights(scenario)
    print("=== 0. What-if 比較: 台風統制の発動前後 ===")
    print(f"  影響便 (台風なし): {len(before)} 便 → (台風統制発動後): {len(after)} 便")
    for f in sorted(after - before, key=lambda x: str(x)):
        print(f"    + 新たに影響: {label_ja(scenario, f)}")

    # --- 1〜3. シナリオ世界での統制クエリ ---
    run(scenario, "1. 空港統制の内訳（台風起因・どちら側の空港か）", Q_AIRPORT_CONTROL)
    rot = run(scenario, "2a. 波及リスク: 機材繰り (rotatesTo+) の下流便", Q_ROTATION_RISK)
    crew = run(scenario, "2b. 波及リスク: 乗務員繰り (crewConnectsTo) 経由の下流便", Q_CREW_RISK)
    pax = run(scenario, "3. 影響旅客（推論による自動抽出）と原因", Q_AFFECTED_PAX)

    # --- 4. サマリ ---
    risk_flights = {r[1] for r in rot} | {r[1] for r in crew}
    print("\n=== 4. 統制サマリ ===")
    print(f"  影響便            : {len(after)} 便")
    print(f"  うち台風起因      : {len(after - before)} 便")
    print(f"  波及リスク便      : {len(risk_flights)} 便 ({', '.join(sorted(str(x) for x in risk_flights))})")
    print(f"  影響旅客          : {len({r[0] for r in pax})} 名")


if __name__ == "__main__":
    main()

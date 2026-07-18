"""航空オペレーション・オントロジーを公開する MCP サーバー (stdio)。

Claude Code などの MCP クライアントから、推論済み知識グラフに
ツール経由でアクセスできるようにする。

公開ツール:
- get_schema            : オントロジーの語彙 (SPARQL を書くための情報)
- sparql_query          : 任意の SPARQL SELECT/ASK を実行 (読み取り専用)
- disrupted_flights     : 影響便と原因の一覧 (推論結果)
- propagation_risks     : 機材繰り・乗務員繰りによる波及リスク便
- affected_passengers   : 影響旅客の一覧 (推論結果)
- reload_graph          : TTL を再読み込み (シナリオ再構築後に使用)

Claude Code への登録例:
    claude mcp add aviation-ontology -- \
        /path/to/ontology-demo/.venv/bin/python \
        /path/to/ontology-demo/mcp_server/aviation_ontology_server.py

グラフは output/aviation_irregular.ttl (台風シナリオ) があればそれを、
なければ output/aviation.ttl を読み込み、初回アクセス時に OWL 2 RL の
閉包を計算してメモリに保持する。
"""

import json
from pathlib import Path

import owlrl
from mcp.server.fastmcp import FastMCP
from rdflib import Graph, Namespace, OWL, RDF, RDFS

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
AVI = Namespace("https://example.org/onto/aviation#")

PREFIXES = """
PREFIX avi:  <https://example.org/onto/aviation#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

mcp = FastMCP("aviation-ontology")

_graph: Graph | None = None
_source: str = ""


def _load_graph() -> Graph:
    """TTL を読み込み OWL 2 RL 閉包を計算 (初回のみ・数秒かかる)。"""
    global _graph, _source
    if _graph is not None:
        return _graph
    for name in ("aviation_irregular.ttl", "aviation.ttl"):
        path = OUTPUT_DIR / name
        if path.exists():
            g = Graph()
            g.parse(path, format="turtle")
            owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
            g.bind("avi", AVI)
            _graph, _source = g, name
            return g
    raise RuntimeError(
        "output/aviation*.ttl がありません。先に aviation/build_ontology.py "
        "(と aviation/build_irregular_scenario.py) を実行してください。")


def _ja(g: Graph, node) -> str:
    for lab in g.objects(node, RDFS.label):
        if getattr(lab, "language", None) == "ja":
            return str(lab)
    return str(node).split("#")[-1]


def _rows_to_json(rows, var_names) -> str:
    data = [dict(zip(var_names, (str(v) if v is not None else None for v in row)))
            for row in rows]
    return json.dumps(data, ensure_ascii=False, indent=1)


@mcp.tool()
def get_schema() -> str:
    """オントロジーの語彙一覧 (クラス・プロパティ・主な個体) を返す。
    sparql_query で SPARQL を書く前に必ず呼ぶこと。"""
    g = _load_graph()

    def locals_of(rdf_type):
        return sorted(
            {s for s in g.subjects(RDF.type, rdf_type)
             if str(s).startswith(str(AVI))})

    lines = [f"# 航空オペレーション・オントロジー (データソース: {_source}, OWL 2 RL 推論済み)",
             "PREFIX avi: <https://example.org/onto/aviation#>", "", "## クラス"]
    for c in locals_of(OWL.Class):
        lines.append(f"- avi:{str(c).split('#')[1]}  # {_ja(g, c)}")
    lines.append("\n## プロパティ")
    for p in locals_of(OWL.ObjectProperty) + locals_of(OWL.DatatypeProperty):
        lines.append(f"- avi:{str(p).split('#')[1]}  # {_ja(g, p)}")
    lines.append("\n## 主な個体 (便・空港・旅客)")
    for cls in (AVI.Flight, AVI.Airport, AVI.Passenger):
        for i in sorted(g.subjects(RDF.type, cls)):
            if str(i).startswith(str(AVI)):
                lines.append(f"- avi:{str(i).split('#')[1]}  ({_ja(g, i)})")
    lines.append(
        "\n## 注意\n"
        "- グラフは推論済み。avi:DisruptedFlight / avi:DomesticFlight / "
        "avi:WidebodyFlight / avi:AffectedPassenger への分類、"
        "avi:affectedBy / avi:departureCountry / avi:operatedWithModel の値は"
        "導出済みなので直接クエリできる。\n"
        "- ラベルは日本語: FILTER(LANG(?label) = \"ja\")\n"
        "- 機材繰りの下流は avi:rotatesTo+ 、乗務員繰りは avi:crewConnectsTo で辿れる。")
    return "\n".join(lines)


@mcp.tool()
def sparql_query(query: str) -> str:
    """SPARQL SELECT/ASK クエリを推論済みグラフに対して実行する (読み取り専用)。
    PREFIX avi: <https://example.org/onto/aviation#> は自動付与される。"""
    lowered = query.lower()
    if any(kw in lowered for kw in ("insert", "delete", "drop", "clear", "load ")):
        return "エラー: 読み取り専用サーバーのため更新系クエリは実行できません。"
    g = _load_graph()
    full = query if "prefix" in lowered else PREFIXES + query
    try:
        result = g.query(full)
    except Exception as e:
        return f"SPARQL エラー: {e}"
    if result.type == "ASK":
        return json.dumps({"ask": bool(result.askAnswer)})
    rows = list(result)
    if len(rows) > 200:
        rows = rows[:200]
    return _rows_to_json(rows, [str(v) for v in result.vars])


@mcp.tool()
def disrupted_flights() -> str:
    """影響便 (DisruptedFlight) と影響の原因を返す。推論による波及
    (機材の整備事象・空港の台風統制など) を含む。"""
    g = _load_graph()
    rows = g.query(PREFIXES + """
        SELECT ?flight ?departure ?cause WHERE {
          ?f a avi:DisruptedFlight ; rdfs:label ?flight ;
             avi:scheduledDeparture ?departure ; avi:affectedBy ?e .
          ?e rdfs:label ?cause .
          FILTER(LANG(?flight) = "ja" && LANG(?cause) = "ja")
        } ORDER BY ?departure""")
    return _rows_to_json(rows, ["flight", "departure", "cause"])


@mcp.tool()
def propagation_risks() -> str:
    """影響便から機材繰り (rotatesTo+) と乗務員繰り (crewConnectsTo) で
    波及しうる下流便 (まだ影響判定されていないもの) を返す。"""
    g = _load_graph()
    rot = g.query(PREFIXES + """
        SELECT DISTINCT ?src ?dst ?departure WHERE {
          ?s a avi:DisruptedFlight ; rdfs:label ?src .
          ?s avi:rotatesTo+ ?d .
          FILTER NOT EXISTS { ?d a avi:DisruptedFlight }
          ?d rdfs:label ?dst ; avi:scheduledDeparture ?departure .
          FILTER(LANG(?src) = "ja" && LANG(?dst) = "ja")
        } ORDER BY ?departure""")
    crew = g.query(PREFIXES + """
        SELECT DISTINCT ?src ?dst ?departure WHERE {
          ?s a avi:DisruptedFlight ; rdfs:label ?src .
          ?s (avi:rotatesTo|avi:crewConnectsTo)*/avi:crewConnectsTo/(avi:rotatesTo|avi:crewConnectsTo)* ?d .
          FILTER NOT EXISTS { ?d a avi:DisruptedFlight }
          ?d rdfs:label ?dst ; avi:scheduledDeparture ?departure .
          FILTER(LANG(?src) = "ja" && LANG(?dst) = "ja")
        } ORDER BY ?departure""")
    return json.dumps({
        "aircraft_rotation": json.loads(_rows_to_json(rot, ["source", "downstream", "departure"])),
        "crew_connection": json.loads(_rows_to_json(crew, ["source", "downstream", "departure"])),
    }, ensure_ascii=False, indent=1)


@mcp.tool()
def affected_passengers() -> str:
    """影響旅客 (AffectedPassenger、推論で自動抽出) と予約便・原因を返す。"""
    g = _load_graph()
    rows = g.query(PREFIXES + """
        SELECT ?passenger ?flight ?cause WHERE {
          ?p a avi:AffectedPassenger ; rdfs:label ?passenger ; avi:bookedOn ?f .
          ?f a avi:DisruptedFlight ; rdfs:label ?flight ; avi:affectedBy ?e .
          ?e rdfs:label ?cause .
          FILTER(LANG(?passenger) = "ja" && LANG(?flight) = "ja" && LANG(?cause) = "ja")
        } ORDER BY ?passenger""")
    return _rows_to_json(rows, ["passenger", "flight", "cause"])


@mcp.tool()
def reload_graph() -> str:
    """TTL ファイルを再読み込みして推論をやり直す (シナリオ再構築後に使う)。"""
    global _graph
    _graph = None
    g = _load_graph()
    return f"再読み込み完了: {_source} ({len(g)} トリプル, 推論済み)"


if __name__ == "__main__":
    mcp.run()  # stdio transport

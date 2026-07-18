"""オントロジー・デモ MCP サーバー (stdio) — マルチグラフ対応版。

2 つの推論済み知識グラフを公開する:
- aviation : 航空オペレーション (台風 IROPS シナリオがあればそれを読み込む)
- cuisine  : 料理・食材・アレルゲン

公開ツール:
- get_schema(graph)               : 語彙一覧 (SPARQL を書くための情報)
- sparql_query(query, graph)      : 任意の SELECT/ASK (読み取り専用)
- disrupted_flights()             : 影響便と原因 (aviation)
- propagation_risks()             : 機材繰り・乗務員繰りの波及リスク (aviation)
- affected_passengers()           : 影響旅客 (aviation)
- alternate_airports(flight)      : ダイバート先候補の推論 (滑走路長×機種制約) (aviation)
- simulate_airport_disruption(..) : What-if — 任意の空港を運用制限にして再推論 (aviation)
- safe_dishes(avoid_allergens)    : アレルゲン回避メニュー判定 (cuisine)
- reload_graph()                  : ファイルから再読み込み (シミュレーションの解除も)

Claude Code への登録例:
    claude mcp add ontology-demo -- \
        /path/to/ontology-demo/.venv/bin/python \
        /path/to/ontology-demo/mcp_server/ontology_server.py
"""

import json
from pathlib import Path

import owlrl
from mcp.server.fastmcp import FastMCP
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
AVI = Namespace("https://example.org/onto/aviation#")
CUI = Namespace("https://example.org/onto/cuisine#")

GRAPH_FILES = {
    "aviation": ["aviation_irregular.ttl", "aviation.ttl"],
    "cuisine": ["cuisine.ttl"],
}
NSMAP = {"aviation": ("avi", AVI), "cuisine": ("cuisine", CUI)}
SCHEMA_INDIVIDUALS = {
    "aviation": ("Flight", "Airport", "Passenger"),
    "cuisine": ("Dish", "Ingredient", "Allergen"),
}
SCHEMA_NOTES = {
    "aviation": (
        "- 推論済み: avi:DisruptedFlight / avi:DomesticFlight / avi:WidebodyFlight / "
        "avi:AffectedPassenger への分類、avi:affectedBy / avi:departureCountry / "
        "avi:operatedWithModel の値は導出済み。\n"
        "- 機材繰りの下流は avi:rotatesTo+ 、乗務員繰りは avi:crewConnectsTo。\n"
        "- 滑走路長は avi:runwayLengthM、機種の必要滑走路長は avi:requiredRunwayM。"),
    "cuisine": (
        "- 推論済み: cuisine:MeatDish / cuisine:SeafoodDish / cuisine:GlutenDish への分類、"
        "cuisine:hasAllergen (料理→アレルゲン) は導出済み。"),
}

mcp = FastMCP("ontology-demo")

# グラフ名 → {"graph": 推論済み Graph, "source": 説明}
_states: dict[str, dict] = {}


def _parse_files(name: str) -> tuple[Graph, str]:
    for fname in GRAPH_FILES[name]:
        path = OUTPUT_DIR / fname
        if path.exists():
            g = Graph()
            g.parse(path, format="turtle")
            prefix, ns = NSMAP[name]
            g.bind(prefix, ns)
            return g, fname
    raise RuntimeError(
        f"output/ に {name} のTTLがありません。先にビルドスクリプトを実行してください。")


def _expand(g: Graph) -> Graph:
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    return g


def _get(name: str = "aviation") -> Graph:
    if name not in GRAPH_FILES:
        raise ValueError(f"graph は {list(GRAPH_FILES)} のいずれかを指定してください")
    if name not in _states:
        g, src = _parse_files(name)
        _states[name] = {"graph": _expand(g), "source": src}
    return _states[name]["graph"]


def _ja(g: Graph, node) -> str:
    for lab in g.objects(node, RDFS.label):
        if getattr(lab, "language", None) == "ja":
            return str(lab)
    return str(node).split("#")[-1]


def _rows_to_json(rows, var_names) -> str:
    data = [dict(zip(var_names, (str(v) if v is not None else None for v in row)))
            for row in rows]
    return json.dumps(data, ensure_ascii=False, indent=1)


PREFIXES = {
    "aviation": "PREFIX avi: <https://example.org/onto/aviation#>\n"
                "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n",
    "cuisine": "PREFIX cuisine: <https://example.org/onto/cuisine#>\n"
               "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n",
}


# ---------------------------------------------------------------- 共通ツール

@mcp.tool()
def get_schema(graph: str = "aviation") -> str:
    """オントロジーの語彙一覧を返す。graph は "aviation" か "cuisine"。
    sparql_query で SPARQL を書く前に必ず呼ぶこと。"""
    g = _get(graph)
    prefix, ns = NSMAP[graph]
    src = _states[graph]["source"]

    def locals_of(rdf_type):
        return sorted({s for s in g.subjects(RDF.type, rdf_type)
                       if str(s).startswith(str(ns))})

    lines = [f"# グラフ: {graph} (データソース: {src}, OWL 2 RL 推論済み)",
             f"PREFIX {prefix}: <{ns}>", "", "## クラス"]
    for c in locals_of(OWL.Class):
        lines.append(f"- {prefix}:{str(c).split('#')[1]}  # {_ja(g, c)}")
    lines.append("\n## プロパティ")
    for p in locals_of(OWL.ObjectProperty) + locals_of(OWL.DatatypeProperty):
        lines.append(f"- {prefix}:{str(p).split('#')[1]}  # {_ja(g, p)}")
    lines.append("\n## 主な個体")
    for cls_name in SCHEMA_INDIVIDUALS[graph]:
        for i in sorted(g.subjects(RDF.type, ns[cls_name])):
            if str(i).startswith(str(ns)):
                lines.append(f"- {prefix}:{str(i).split('#')[1]}  ({_ja(g, i)})")
    lines.append("\n## 注意\n" + SCHEMA_NOTES[graph] +
                 "\n- ラベルは日本語: FILTER(LANG(?label) = \"ja\")")
    return "\n".join(lines)


@mcp.tool()
def sparql_query(query: str, graph: str = "aviation") -> str:
    """SPARQL SELECT/ASK を推論済みグラフに対して実行する (読み取り専用)。
    graph は "aviation" か "cuisine"。PREFIX は自動付与される。"""
    lowered = query.lower()
    if any(kw in lowered for kw in ("insert", "delete", "drop", "clear", "load ")):
        return "エラー: 読み取り専用サーバーのため更新系クエリは実行できません。"
    g = _get(graph)
    full = query if "prefix" in lowered else PREFIXES[graph] + query
    try:
        result = g.query(full)
    except Exception as e:
        return f"SPARQL エラー: {e}"
    if result.type == "ASK":
        return json.dumps({"ask": bool(result.askAnswer)})
    rows = list(result)[:200]
    return _rows_to_json(rows, [str(v) for v in result.vars])


@mcp.tool()
def reload_graph() -> str:
    """全グラフをファイルから再読み込みして推論をやり直す。
    simulate_airport_disruption のシミュレーション状態も解除される。"""
    _states.clear()
    msgs = []
    for name in GRAPH_FILES:
        try:
            g = _get(name)
            msgs.append(f"{name}: {_states[name]['source']} ({len(g)} トリプル)")
        except RuntimeError as e:
            msgs.append(f"{name}: 読み込み失敗 ({e})")
    return "再読み込み完了\n" + "\n".join(msgs)


# ---------------------------------------------------------------- aviation

@mcp.tool()
def disrupted_flights() -> str:
    """影響便 (DisruptedFlight) と原因を返す (aviation)。推論による波及を含む。"""
    g = _get("aviation")
    rows = g.query(PREFIXES["aviation"] + """
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
    波及しうる下流便を返す (aviation)。"""
    g = _get("aviation")
    rot = g.query(PREFIXES["aviation"] + """
        SELECT DISTINCT ?src ?dst ?departure WHERE {
          ?s a avi:DisruptedFlight ; rdfs:label ?src .
          ?s avi:rotatesTo+ ?d .
          FILTER NOT EXISTS { ?d a avi:DisruptedFlight }
          ?d rdfs:label ?dst ; avi:scheduledDeparture ?departure .
          FILTER(LANG(?src) = "ja" && LANG(?dst) = "ja")
        } ORDER BY ?departure""")
    crew = g.query(PREFIXES["aviation"] + """
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
    """影響旅客 (AffectedPassenger、推論で自動抽出) と予約便・原因を返す (aviation)。"""
    g = _get("aviation")
    rows = g.query(PREFIXES["aviation"] + """
        SELECT ?passenger ?flight ?cause WHERE {
          ?p a avi:AffectedPassenger ; rdfs:label ?passenger ; avi:bookedOn ?f .
          ?f a avi:DisruptedFlight ; rdfs:label ?flight ; avi:affectedBy ?e .
          ?e rdfs:label ?cause .
          FILTER(LANG(?passenger) = "ja" && LANG(?flight) = "ja" && LANG(?cause) = "ja")
        } ORDER BY ?passenger""")
    return _rows_to_json(rows, ["passenger", "flight", "cause"])


@mcp.tool()
def alternate_airports(flight: str) -> str:
    """便のダイバート先 (代替空港) 候補を推論する (aviation)。
    機種の必要滑走路長 (requiredRunwayM) と空港の滑走路長 (runwayLengthM)、
    空港の運用制限 (disruptedBy) を制約として候補を絞り込む。
    flight には便コード (例: "az987") を指定する。"""
    g = _get("aviation")
    f = AVI[flight.lower()]
    model = g.value(f, AVI.operatedWithModel)
    if model is None:
        return f"エラー: 便 {flight} が見つからないか、機材が未割当です。"
    required = g.value(model, AVI.requiredRunwayM)
    dest = g.value(f, AVI.arrivesAt)
    dest_country = g.value(dest, AVI.locatedIn) if dest else None

    candidates, excluded = [], []
    for ap in sorted(g.subjects(RDF.type, AVI.Airport)):
        if not str(ap).startswith(str(AVI)) or ap == dest:
            continue
        runway = g.value(ap, AVI.runwayLengthM)
        disruptions = [_ja(g, e) for e in g.objects(ap, AVI.disruptedBy)]
        entry = {
            "code": str(ap).split("#")[1].upper(),
            "airport": _ja(g, ap),
            "country": _ja(g, g.value(ap, AVI.locatedIn)),
            "runway_m": int(runway) if runway is not None else None,
        }
        if disruptions:
            entry["reason"] = f"運用制限中: {', '.join(disruptions)}"
            excluded.append(entry)
        elif runway is None or (required is not None and int(runway) < int(required)):
            entry["reason"] = f"滑走路長不足 (必要 {required}m)"
            excluded.append(entry)
        else:
            entry["same_country_as_destination"] = (
                dest_country is not None and g.value(ap, AVI.locatedIn) == dest_country)
            candidates.append(entry)

    candidates.sort(key=lambda e: (not e["same_country_as_destination"], -e["runway_m"]))
    return json.dumps({
        "flight": _ja(g, f),
        "aircraft_model": _ja(g, model),
        "required_runway_m": int(required) if required is not None else None,
        "destination": _ja(g, dest) if dest else None,
        "candidates": candidates,
        "excluded": excluded,
    }, ensure_ascii=False, indent=1)


@mcp.tool()
def simulate_airport_disruption(airport_codes: list[str],
                                cause: str = "台風(シミュレーション)") -> str:
    """What-if シミュレーション (aviation): 指定した空港を運用制限にして推論を
    やり直し、影響便・影響旅客の変化を返す。既存の空港制限は置き換えられる。
    airport_codes の例: ["cts"] や ["hnd", "oka"]。
    元に戻すには reload_graph を呼ぶ。"""
    raw, src = _parse_files("aviation")

    # 現在の空港運用制限をすべて外し、指定空港に新しい制限を置く
    for t in list(raw.triples((None, AVI.disruptedBy, None))):
        raw.remove(t)
    event = AVI["sim_disruption"]
    raw.add((event, RDF.type, AVI.Typhoon))
    raw.add((event, RDFS.label, Literal(cause, lang="ja")))
    applied = []
    for code in airport_codes:
        ap = AVI[code.lower()]
        if (ap, RDF.type, AVI.Airport) not in raw:
            return f"エラー: 空港コード {code} が見つかりません。get_schema で確認してください。"
        raw.add((ap, AVI.disruptedBy, event))
        applied.append(_ja(raw, ap))

    prev = _get("aviation")
    prev_disrupted = {f for f in prev.subjects(RDF.type, AVI.DisruptedFlight)}

    g = _expand(raw)
    _states["aviation"] = {"graph": g, "source": f"{src} + シミュレーション({', '.join(applied)})"}

    now_disrupted = {f for f in g.subjects(RDF.type, AVI.DisruptedFlight)}
    pax = {p for p in g.subjects(RDF.type, AVI.AffectedPassenger)}
    return json.dumps({
        "simulation": f"{cause} → {', '.join(applied)} を運用制限に設定",
        "disrupted_flights": sorted(_ja(g, f) for f in now_disrupted),
        "newly_disrupted_vs_before": sorted(_ja(g, f) for f in now_disrupted - prev_disrupted),
        "no_longer_disrupted": sorted(_ja(g, f) for f in prev_disrupted - now_disrupted),
        "affected_passengers": sorted(_ja(g, p) for p in pax),
        "note": "以後の全ツールはこのシミュレーション状態で応答する。解除は reload_graph。",
    }, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- cuisine

@mcp.tool()
def safe_dishes(avoid_allergens: list[str]) -> str:
    """アレルゲンを避けたい顧客に提供できる料理を判定する (cuisine)。
    avoid_allergens は日本語名の部分一致 (例: ["小麦", "えび"])。
    推論済みの hasAllergen (食材経由の導出を含む) に基づいて判定する。"""
    g = _get("cuisine")
    all_allergens = {a: _ja(g, a) for a in g.subjects(RDF.type, CUI.Allergen)
                     if str(a).startswith(str(CUI))}
    avoid = set()
    for word in avoid_allergens:
        matched = {iri for iri, name in all_allergens.items() if word in name}
        if not matched:
            return (f"エラー: 未知のアレルゲン '{word}'。"
                    f"選択肢: {', '.join(sorted(all_allergens.values()))}")
        avoid |= matched

    result = []
    for dish in sorted(g.subjects(RDF.type, CUI.Dish)):
        if not str(dish).startswith(str(CUI)):
            continue
        allergens = set(g.objects(dish, CUI.hasAllergen))
        hit = allergens & avoid
        result.append({
            "dish": _ja(g, dish),
            "servable": not hit,
            "contains": sorted(_ja(g, a) for a in allergens),
            "blocked_by": sorted(_ja(g, a) for a in hit),
        })
    return json.dumps({
        "avoiding": sorted(all_allergens[a] for a in avoid),
        "menu": result,
    }, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    mcp.run()  # stdio transport

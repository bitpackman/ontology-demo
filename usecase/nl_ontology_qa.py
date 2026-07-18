"""実践ユースケース③: LLM × オントロジー — 自然言語でメニュー知識グラフに質問する。

2026 年時点の代表的トレンド「オントロジーによる LLM のグラウンディング」の最小実装。

  自然言語の質問
    → Claude が SPARQL を生成 (オントロジーの語彙のみ使用・構造化出力)
    → ローカルの知識グラフ (推論済み) で実行
    → Claude が「クエリ結果だけ」を根拠に日本語で回答

LLM は知識グラフの照会役に徹するため、グラフに無い事実を捏造できない
(ハルシネーション抑制)。

使用例:
    export ANTHROPIC_API_KEY=sk-ant-...
    python usecase/nl_ontology_qa.py "小麦アレルギーの人が食べられる料理は？"
    python usecase/nl_ontology_qa.py --offline   # API キーなしで固定クエリのデモ
"""

import argparse
import json
import sys
from pathlib import Path

import owlrl
from rdflib import Graph, Namespace, RDF, RDFS

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CUISINE = Namespace("https://example.org/onto/cuisine#")

MODEL = "claude-opus-4-8"

SPARQL_SCHEMA = {
    "type": "object",
    "properties": {
        "sparql": {"type": "string", "description": "実行可能な SPARQL SELECT クエリ"},
        "note": {"type": "string", "description": "クエリ設計の一言メモ (日本語)"},
    },
    "required": ["sparql", "note"],
    "additionalProperties": False,
}

OFFLINE_QUESTION = "小麦アレルギーの人が食べられる料理は？"
OFFLINE_SPARQL = """
PREFIX cuisine: <https://example.org/onto/cuisine#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?label WHERE {
  ?dish a cuisine:Dish ; rdfs:label ?label .
  FILTER(LANG(?label) = "ja")
  FILTER NOT EXISTS { ?dish cuisine:hasAllergen cuisine:gluten }
}
"""


def load_graph() -> Graph:
    ttl = OUTPUT_DIR / "cuisine.ttl"
    if not ttl.exists():
        raise SystemExit("output/cuisine.ttl がありません。先に src/build_ontology.py を実行してください。")
    g = Graph()
    g.parse(ttl, format="turtle")
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    g.bind("cuisine", CUISINE)
    return g


def describe_vocabulary(g: Graph) -> str:
    """LLM に渡すオントロジー語彙の要約 (クラス・プロパティ・個体と日本語ラベル)。"""

    def ja(node):
        for lab in g.objects(node, RDFS.label):
            if getattr(lab, "language", None) == "ja":
                return str(lab)
        return ""

    def local_entities(rdf_type):
        seen = set()
        for s in g.subjects(RDF.type, rdf_type):
            if isinstance(s, type(CUISINE.Dish)) and str(s).startswith(str(CUISINE)):
                seen.add(s)
        return sorted(seen)

    from rdflib import OWL

    lines = ["PREFIX cuisine: <https://example.org/onto/cuisine#>", "", "## クラス"]
    for c in local_entities(OWL.Class):
        lines.append(f"- cuisine:{str(c).split('#')[1]}  # {ja(c)}")
    lines.append("\n## プロパティ")
    for p in local_entities(OWL.ObjectProperty) + local_entities(OWL.DatatypeProperty):
        lines.append(f"- cuisine:{str(p).split('#')[1]}  # {ja(p)}")
    lines.append("\n## 個体 (一部)")
    for cls in (CUISINE.Dish, CUISINE.Allergen):
        for i in sorted(g.subjects(RDF.type, cls)):
            if str(i).startswith(str(CUISINE)):
                lines.append(f"- cuisine:{str(i).split('#')[1]}  ({ja(i)})")
    lines.append("\n注: グラフは OWL 2 RL 推論済み。cuisine:hasAllergen (料理→アレルゲン) や "
                 "cuisine:MeatDish への分類は導出済みなので直接クエリできる。")
    return "\n".join(lines)


def generate_sparql(client, question: str, vocab: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=(
            "あなたは SPARQL 生成器です。以下の語彙だけを使い、ユーザーの質問に答える "
            "SPARQL SELECT クエリを 1 つ生成してください。ラベルは日本語 (LANG='ja') を返すこと。\n\n"
            + vocab
        ),
        messages=[{"role": "user", "content": question}],
        output_config={"format": {"type": "json_schema", "schema": SPARQL_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def generate_answer(client, question: str, rows: list[tuple]) -> str:
    results_text = "\n".join(" | ".join(str(v) for v in row) for row in rows) or "(結果なし)"
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=(
            "知識グラフへの SPARQL クエリ結果だけを根拠に、日本語で簡潔に回答してください。"
            "結果に含まれない情報を推測・追加してはいけません。結果が空なら「該当なし」と答えること。"
        ),
        messages=[{
            "role": "user",
            "content": f"質問: {question}\n\nクエリ結果:\n{results_text}",
        }],
    )
    return next(b.text for b in response.content if b.type == "text")


def main() -> None:
    parser = argparse.ArgumentParser(description="自然言語→SPARQL→グラウンディングされた回答")
    parser.add_argument("question", nargs="?", help="日本語の質問")
    parser.add_argument("--offline", action="store_true",
                        help="API を呼ばず、固定の質問・クエリでパイプラインをデモする")
    args = parser.parse_args()

    g = load_graph()

    if args.offline:
        question, sparql, note = OFFLINE_QUESTION, OFFLINE_SPARQL, "(オフライン固定クエリ)"
        client = None
    else:
        if not args.question:
            parser.error("質問を指定するか --offline を使ってください")
        try:
            import anthropic
        except ImportError:
            raise SystemExit("anthropic パッケージが必要です: pip install anthropic")
        client = anthropic.Anthropic()
        question = args.question
        print("Claude に SPARQL 生成を依頼中...")
        try:
            generated = generate_sparql(client, question, describe_vocabulary(g))
        except (anthropic.AuthenticationError, TypeError):
            # TypeError: SDK が認証情報を解決できなかった場合 (キー未設定)
            raise SystemExit("認証エラー: ANTHROPIC_API_KEY を設定してください "
                             "(キーなしで試すには --offline)")
        except anthropic.RateLimitError:
            raise SystemExit("レート制限に達しました。しばらく待って再実行してください。")
        except anthropic.APIStatusError as e:
            raise SystemExit(f"API エラー ({e.status_code}): {e.message}")
        except anthropic.APIConnectionError:
            raise SystemExit("ネットワークエラー: 接続を確認してください。")
        sparql, note = generated["sparql"], generated["note"]

    print(f"\n質問: {question}")
    print(f"\n--- 生成された SPARQL ({note}) ---\n{sparql.strip()}\n")

    try:
        rows = [tuple(row) for row in g.query(sparql)]
    except Exception as e:
        raise SystemExit(f"SPARQL 実行エラー: {e}")

    print("--- クエリ結果 ---")
    for row in rows:
        print("  " + " | ".join(str(v) for v in row))
    if not rows:
        print("  (結果なし)")

    if client is not None:
        print("\nClaude に回答生成を依頼中...")
        try:
            answer = generate_answer(client, question, rows)
        except anthropic.APIError as e:
            raise SystemExit(f"回答生成に失敗しました: {e}")
        print(f"\n--- 回答 (クエリ結果にグラウンディング) ---\n{answer}")
    else:
        print("\n(オフラインモードのため回答生成はスキップ。"
              "ANTHROPIC_API_KEY を設定して質問を渡すと Claude が回答します)")


if __name__ == "__main__":
    main()

"""RDF 1.2 (2026年4月 勧告候補) の「トリプルターム」によるステートメント注釈のデモ。

RDF 1.2 では、トリプルそのものを注釈対象にできる (旧称 RDF-star)。
例: 「親子丼は鶏肉を含む」という言明に対して、出典と確信度を付与する。

    cuisine:oyakodon cuisine:hasIngredient cuisine:chicken ~ _:r .
    _:r ex:source <https://example.org/recipes/123> ; ex:confidence 0.98 .

内部的には _:r rdf:reifies <<( s p o )>> というトリプルタームで表現される。

執筆時点の rdflib 7.6 は RDF 1.2 構文 (<<( ... )>>) を未サポートのため、
このスクリプトでは
  1. RDF 1.2 での書き方をテキストとして提示し、
  2. 現行ツールで動く等価表現 (RDF 1.1 標準 reification) を rdflib で構築して
     SPARQL で照会する
という 2 段構成で示す。
"""

from pathlib import Path

from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

CUISINE = Namespace("https://example.org/onto/cuisine#")
EX = Namespace("https://example.org/meta#")

RDF12_EXAMPLE = """\
# --- RDF 1.2 (Candidate Recommendation) での書き方（参考・将来のパーサ対応待ち） ---
PREFIX cuisine: <https://example.org/onto/cuisine#>
PREFIX ex:      <https://example.org/meta#>

cuisine:oyakodon cuisine:hasIngredient cuisine:chicken ~ _:r .
_:r ex:source <https://example.org/recipes/123> ;
    ex:confidence 0.98 .

# 上記の糖衣構文は、内部的には次のトリプルターム表現に展開される:
# _:r rdf:reifies <<( cuisine:oyakodon cuisine:hasIngredient cuisine:chicken )>> .
"""


def main() -> None:
    print(RDF12_EXAMPLE)
    print("--- 現行ツールで動く等価表現 (RDF 1.1 reification) を rdflib で構築 ---\n")

    g = Graph()
    g.bind("cuisine", CUISINE)
    g.bind("ex", EX)

    # 対象の言明そのもの
    g.add((CUISINE.oyakodon, CUISINE.hasIngredient, CUISINE.chicken))

    # 言明への注釈 (標準 reification)
    stmt = BNode()
    g.add((stmt, RDF.type, RDF.Statement))
    g.add((stmt, RDF.subject, CUISINE.oyakodon))
    g.add((stmt, RDF.predicate, CUISINE.hasIngredient))
    g.add((stmt, RDF.object, CUISINE.chicken))
    g.add((stmt, EX.source, URIRef("https://example.org/recipes/123")))
    g.add((stmt, EX.confidence, Literal("0.98", datatype=XSD.decimal)))

    out = OUTPUT_DIR / "annotation.ttl"
    OUTPUT_DIR.mkdir(exist_ok=True)
    g.serialize(destination=out, format="turtle")
    print(g.serialize(format="turtle"))

    query = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX ex:  <https://example.org/meta#>
    SELECT ?s ?p ?o ?source ?conf WHERE {
      ?stmt a rdf:Statement ;
            rdf:subject ?s ; rdf:predicate ?p ; rdf:object ?o ;
            ex:source ?source ; ex:confidence ?conf .
    }
    """
    print("--- SPARQL: 注釈付き言明の照会 ---")
    for row in g.query(query):
        print(f"  言明: {row.s.n3(g.namespace_manager)} "
              f"{row.p.n3(g.namespace_manager)} {row.o.n3(g.namespace_manager)}")
        print(f"  出典: {row.source}  確信度: {row.conf}")
    print(f"\n保存先: {out}")


if __name__ == "__main__":
    main()

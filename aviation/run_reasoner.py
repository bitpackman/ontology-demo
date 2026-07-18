"""HermiT 推論器で航空オペレーション知識を導出する (要 Java)。

導出されるもの:
- 便の自動分類: WidebodyFlight / DomesticFlight / DisruptedFlight
- プロパティチェーンによる値:
    出発国・到着国 (departsFrom ∘ locatedIn など)
    運航機種 (assignedAircraft ∘ hasModel)
    整備事象の便への波及 (assignedAircraft ∘ hasOpenIssue ⊑ affectedBy)
- 推移的プロパティ rotatesTo の閉包 (AZ101 → AZ103 が直接たどれるようになる)

先に build_ontology.py を実行して output/aviation.owl を生成しておくこと。
"""

from pathlib import Path

from owlready2 import get_ontology, sync_reasoner
from rdflib import Graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
BASE_IRI = "https://example.org/onto/aviation#"


def label_ja(entity) -> str:
    for lab in entity.label:
        if getattr(lab, "lang", None) == "ja":
            return str(lab)
    return entity.name


def show_flights(onto, title: str) -> None:
    print(f"\n=== {title} ===")
    for f in sorted(onto.Flight.instances(), key=lambda x: x.name):
        types = ", ".join(sorted(c.name for c in f.is_a if hasattr(c, "name")))
        affected = ", ".join(label_ja(e) for e in f.affectedBy)
        dep = f.departureCountry[0] if f.departureCountry else None
        arr = f.arrivalCountry[0] if f.arrivalCountry else None
        route = f"{label_ja(dep) if dep else '?'}→{label_ja(arr) if arr else '?'}"
        model = f.operatedWithModel[0] if f.operatedWithModel else None
        rot = ", ".join(sorted(x.name.upper() for x in f.rotatesTo))
        print(f"  {label_ja(f)}")
        print(f"      分類: [{types}]  国: {route}  機種: {label_ja(model) if model else '?'}")
        print(f"      影響: [{affected or 'なし'}]  機材繰り下流: [{rot or 'なし'}]")


def main() -> None:
    owl_path = OUTPUT_DIR / "aviation.owl"
    if not owl_path.exists():
        raise SystemExit("output/aviation.owl がありません。先に build_ontology.py を実行してください。")

    onto = get_ontology(owl_path.as_uri()).load()

    show_flights(onto, "推論前（明示的に書いた知識のみ）")

    with onto:
        sync_reasoner(infer_property_values=True)

    show_flights(onto, "推論後（HermiT が導出した知識を含む）")

    inferred_owl = OUTPUT_DIR / "aviation_inferred.owl"
    inferred_ttl = OUTPUT_DIR / "aviation_inferred.ttl"
    onto.save(file=str(inferred_owl), format="rdfxml")
    g = Graph()
    g.parse(inferred_owl, format="xml")
    g.bind("avi", BASE_IRI)
    g.serialize(destination=inferred_ttl, format="turtle")
    print(f"\n推論結果を保存: {inferred_ttl}")


if __name__ == "__main__":
    main()

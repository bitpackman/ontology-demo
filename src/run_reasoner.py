"""HermiT 推論器 (Owlready2 同梱・要 Java) で自動分類とプロパティ値推論を行う。

- 定義クラス (equivalent_to) に基づき、料理個体を MeatDish / SeafoodDish /
  GlutenDish に自動分類する
- プロパティチェーンから料理ごとの hasAllergen を導出する
- 推論結果込みのオントロジーを output/cuisine_inferred.ttl に保存する

先に build_ontology.py を実行して output/cuisine.owl を生成しておくこと。
"""

from pathlib import Path

from owlready2 import get_ontology, sync_reasoner
from rdflib import Graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
BASE_IRI = "https://example.org/onto/cuisine#"


def label_ja(entity) -> str:
    for lab in entity.label:
        if getattr(lab, "lang", None) == "ja":
            return str(lab)
    return entity.name


def show_dishes(onto, title: str) -> None:
    print(f"\n=== {title} ===")
    dish_cls = onto.Dish
    for dish in sorted(dish_cls.instances(), key=lambda d: d.name):
        types = ", ".join(sorted(c.name for c in dish.is_a))
        allergens = ", ".join(sorted(label_ja(a) for a in dish.hasAllergen))
        print(f"  {label_ja(dish):<14} 型: [{types}]  アレルゲン: [{allergens or 'なし'}]")


def main() -> None:
    owl_path = OUTPUT_DIR / "cuisine.owl"
    if not owl_path.exists():
        raise SystemExit("output/cuisine.owl がありません。先に build_ontology.py を実行してください。")

    onto = get_ontology(owl_path.as_uri()).load()

    show_dishes(onto, "推論前（明示的に書いた知識のみ）")

    with onto:
        # HermiT (タブロー法の OWL DL 推論器) を実行。
        # infer_property_values=True でプロパティチェーン由来の値も具体化する。
        sync_reasoner(infer_property_values=True)

    show_dishes(onto, "推論後（HermiT が導出した知識を含む）")

    inferred_ttl = OUTPUT_DIR / "cuisine_inferred.ttl"
    inferred_owl = OUTPUT_DIR / "cuisine_inferred.owl"
    onto.save(file=str(inferred_owl), format="rdfxml")
    g = Graph()
    g.parse(inferred_owl, format="xml")
    g.bind("cuisine", BASE_IRI)
    g.serialize(destination=inferred_ttl, format="turtle")
    print(f"\n推論結果を保存: {inferred_ttl}")


if __name__ == "__main__":
    main()

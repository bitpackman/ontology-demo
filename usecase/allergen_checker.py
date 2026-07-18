"""実践ユースケース①: 飲食店向けメニュー適合性チェッカー (CLI)。

顧客のアレルギー・食事制限プロファイルを受け取り、オントロジー推論
(OWL 2 RL) に基づいて「安全に提供できるメニュー」を判定する。

ポイント: アレルゲン情報はメニューに直接書かれていない。
「親子丼は醤油を含む」「醤油は小麦を含む」という知識から、
プロパティチェーン推論で「親子丼は小麦アレルゲンを含む」を導出して判定する。

使用例:
    python usecase/allergen_checker.py --avoid 小麦 えび
    python usecase/allergen_checker.py --no-meat
    python usecase/allergen_checker.py --avoid 大豆 --no-seafood
"""

import argparse
from pathlib import Path

import owlrl
from rdflib import Graph, Namespace, RDF, RDFS

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CUISINE = Namespace("https://example.org/onto/cuisine#")


def label_ja(g: Graph, node) -> str:
    for lab in g.objects(node, RDFS.label):
        if getattr(lab, "language", None) == "ja":
            return str(lab)
    return g.qname(node)


def load_inferred_graph() -> Graph:
    ttl = OUTPUT_DIR / "cuisine.ttl"
    if not ttl.exists():
        raise SystemExit("output/cuisine.ttl がありません。先に src/build_ontology.py を実行してください。")
    g = Graph()
    g.parse(ttl, format="turtle")
    # 純 Python のルールベース推論で、料理の分類とアレルゲンを導出する
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    return g


def check_menu(g: Graph, avoid_allergens: list[str], no_meat: bool, no_seafood: bool):
    results = []
    for dish in sorted(g.subjects(RDF.type, CUISINE.Dish)):
        # OWL 2 RL 閉包により owl:Thing なども Dish の型に混ざるため個体のみ対象
        if (dish, RDF.type, CUISINE.MeatDish) in g:
            is_meat = True
        else:
            is_meat = False
        is_seafood = (dish, RDF.type, CUISINE.SeafoodDish) in g

        allergens = {label_ja(g, a) for a in g.objects(dish, CUISINE.hasAllergen)}

        reasons = []
        hit = allergens.intersection(avoid_allergens)
        if hit:
            reasons.append(f"アレルゲン: {', '.join(sorted(hit))}")
        if no_meat and is_meat:
            reasons.append("肉料理 (推論による分類)")
        if no_seafood and is_seafood:
            reasons.append("魚介料理 (推論による分類)")

        results.append({
            "name": label_ja(g, dish),
            "ok": not reasons,
            "reasons": reasons,
            "allergens": sorted(allergens),
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="メニュー適合性チェッカー")
    parser.add_argument("--avoid", nargs="*", default=[], metavar="ALLERGEN",
                        help="避けたいアレルゲンの日本語名 (例: 小麦(グルテン) 大豆 えび・かに)。部分一致可")
    parser.add_argument("--no-meat", action="store_true", help="肉料理を除外")
    parser.add_argument("--no-seafood", action="store_true", help="魚介料理を除外")
    args = parser.parse_args()

    g = load_inferred_graph()

    # 部分一致でアレルゲン名を解決 (例: "小麦" → "小麦(グルテン)")
    all_allergens = {label_ja(g, a) for a in g.subjects(RDF.type, CUISINE.Allergen)}
    avoid = set()
    for word in args.avoid:
        matched = {a for a in all_allergens if word in a}
        if not matched:
            raise SystemExit(f"未知のアレルゲン: {word}\n選択肢: {', '.join(sorted(all_allergens))}")
        avoid |= matched

    print("=== 顧客プロファイル ===")
    print(f"  避けるアレルゲン: {', '.join(sorted(avoid)) or 'なし'}")
    print(f"  肉料理を除外: {args.no_meat} / 魚介料理を除外: {args.no_seafood}")

    print("\n=== 判定結果 ===")
    for r in check_menu(g, sorted(avoid), args.no_meat, args.no_seafood):
        mark = "○ 提供可" if r["ok"] else "× 提供不可"
        detail = f"  [{'; '.join(r['reasons'])}]" if r["reasons"] else ""
        allergen_info = f"(含有: {', '.join(r['allergens']) or 'なし'})"
        print(f"  {mark}  {r['name']:<14} {allergen_info}{detail}")


if __name__ == "__main__":
    main()

"""料理オントロジーを Owlready2 で構築し、OWL (RDF/XML) と Turtle で保存する。

デモする OWL 2 の機能:
- クラス階層と Disjoint 宣言
- オブジェクトプロパティ / 逆プロパティ / データプロパティ (Functional)
- プロパティチェーン (hasIngredient ∘ containsAllergen → hasAllergen)
- 存在制約による定義クラス (MeatDish ≡ Dish ⊓ ∃hasIngredient.Meat)
- hasValue 制約 (GlutenDish ≡ Dish ⊓ ∋hasAllergen.gluten)
- 多言語ラベル (ja / en)
"""

from pathlib import Path

from owlready2 import (
    AllDisjoint,
    DataProperty,
    FunctionalProperty,
    ObjectProperty,
    PropertyChain,
    Thing,
    get_ontology,
    locstr,
)
from rdflib import Graph

BASE_IRI = "https://example.org/onto/cuisine#"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

onto = get_ontology(BASE_IRI)

with onto:
    # ---- クラス ----
    class Dish(Thing):
        label = [locstr("料理", "ja"), locstr("Dish", "en")]

    class Ingredient(Thing):
        label = [locstr("食材", "ja"), locstr("Ingredient", "en")]

    class Allergen(Thing):
        label = [locstr("アレルゲン", "ja"), locstr("Allergen", "en")]

    class Meat(Ingredient):
        label = [locstr("肉類", "ja"), locstr("Meat", "en")]

    class Seafood(Ingredient):
        label = [locstr("魚介類", "ja"), locstr("Seafood", "en")]

    class Vegetable(Ingredient):
        label = [locstr("野菜", "ja"), locstr("Vegetable", "en")]

    class Grain(Ingredient):
        label = [locstr("穀物", "ja"), locstr("Grain", "en")]

    AllDisjoint([Meat, Seafood, Vegetable, Grain])
    AllDisjoint([Dish, Ingredient, Allergen])

    # ---- プロパティ ----
    class hasIngredient(ObjectProperty):
        domain = [Dish]
        range = [Ingredient]
        label = [locstr("食材を含む", "ja")]

    class ingredientOf(ObjectProperty):
        inverse_property = hasIngredient

    class containsAllergen(ObjectProperty):
        domain = [Ingredient]
        range = [Allergen]
        label = [locstr("アレルゲンを含む(食材)", "ja")]

    class hasAllergen(ObjectProperty):
        domain = [Dish]
        range = [Allergen]
        label = [locstr("アレルゲンを含む(料理)", "ja")]

    # プロパティチェーン: 料理が食材を含み、その食材がアレルゲンを含むなら、
    # 料理はそのアレルゲンを含む（推論器が導出する）
    hasAllergen.property_chain.append(PropertyChain([hasIngredient, containsAllergen]))

    class calories(DataProperty, FunctionalProperty):
        domain = [Dish]
        range = [int]
        label = [locstr("カロリー(kcal)", "ja")]

    # ---- アレルゲン個体 ----
    gluten = Allergen("gluten", label=[locstr("小麦(グルテン)", "ja")])
    soy = Allergen("soy", label=[locstr("大豆", "ja")])
    egg_allergen = Allergen("egg_allergen", label=[locstr("卵", "ja")])
    crustacean = Allergen("crustacean", label=[locstr("えび・かに", "ja")])
    buckwheat = Allergen("buckwheat", label=[locstr("そば", "ja")])

    # ---- 定義クラス（必要十分条件）: 推論器による自動分類の対象 ----
    class MeatDish(Dish):
        equivalent_to = [Dish & hasIngredient.some(Meat)]
        label = [locstr("肉料理", "ja"), locstr("Meat dish", "en")]

    class SeafoodDish(Dish):
        equivalent_to = [Dish & hasIngredient.some(Seafood)]
        label = [locstr("魚介料理", "ja"), locstr("Seafood dish", "en")]

    class GlutenDish(Dish):
        equivalent_to = [Dish & hasAllergen.value(gluten)]
        label = [locstr("グルテン含有料理", "ja"), locstr("Gluten-containing dish", "en")]

    # ---- 食材個体 ----
    chicken = Meat("chicken", label=[locstr("鶏肉", "ja")])
    pork = Meat("pork", label=[locstr("豚肉", "ja")])
    shrimp = Seafood("shrimp", label=[locstr("えび", "ja")],
                     containsAllergen=[crustacean])
    rice = Grain("rice", label=[locstr("米", "ja")])
    soba_noodle = Grain("soba_noodle", label=[locstr("そば(麺)", "ja")],
                        containsAllergen=[buckwheat, gluten])
    soy_sauce = Ingredient("soy_sauce", label=[locstr("醤油", "ja")],
                           containsAllergen=[gluten, soy])
    tofu = Ingredient("tofu", label=[locstr("豆腐", "ja")],
                      containsAllergen=[soy])
    egg = Ingredient("egg", label=[locstr("卵", "ja")],
                     containsAllergen=[egg_allergen])
    negi = Vegetable("negi", label=[locstr("ねぎ", "ja")])
    cabbage = Vegetable("cabbage", label=[locstr("キャベツ", "ja")])

    # ---- 料理個体（型は Dish のみ。MeatDish 等への分類は推論器の仕事） ----
    Dish("oyakodon", label=[locstr("親子丼", "ja"), locstr("Oyakodon", "en")],
         hasIngredient=[chicken, egg, rice, soy_sauce], calories=680)
    Dish("tempura_soba", label=[locstr("天ぷらそば", "ja"), locstr("Tempura soba", "en")],
         hasIngredient=[shrimp, soba_noodle, soy_sauce], calories=550)
    Dish("hiyayakko", label=[locstr("冷奴", "ja"), locstr("Hiyayakko", "en")],
         hasIngredient=[tofu, negi, soy_sauce], calories=110)
    Dish("yasai_itame", label=[locstr("野菜炒め(豚入り)", "ja"), locstr("Stir-fried vegetables with pork", "en")],
         hasIngredient=[cabbage, negi, pork], calories=320)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    owl_path = OUTPUT_DIR / "cuisine.owl"
    ttl_path = OUTPUT_DIR / "cuisine.ttl"

    onto.save(file=str(owl_path), format="rdfxml")

    # Turtle は rdflib で変換して保存（人間が読みやすい形式）
    g = Graph()
    g.parse(owl_path, format="xml")
    g.bind("cuisine", BASE_IRI)
    g.serialize(destination=ttl_path, format="turtle")

    print(f"クラス数        : {len(list(onto.classes()))}")
    print(f"プロパティ数    : {len(list(onto.properties()))}")
    print(f"個体数          : {len(list(onto.individuals()))}")
    print(f"トリプル数(RDF) : {len(g)}")
    print(f"保存先          : {owl_path}")
    print(f"                  {ttl_path}")


if __name__ == "__main__":
    main()

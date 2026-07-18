"""航空オペレーション・オントロジーを Owlready2 で構築し、OWL/Turtle で保存する。

題材: 架空の航空会社「青空航空 (Aozora Air)」の 1 日の運航。
便・空港・機材・乗務員・整備事象・遅延をモデル化する。

デモする OWL 2 の機能:
- プロパティチェーン ×3
    departureCountry ⊇ departsFrom ∘ locatedIn      (出発国の導出)
    operatedWithModel ⊇ assignedAircraft ∘ hasModel (運航機種の導出)
    affectedBy ⊇ assignedAircraft ∘ hasOpenIssue    (機材の整備問題が便に波及)
- 推移的プロパティ: rotatesTo (同一機材の次レグ) → 機材繰りの下流をたどれる
- 定義クラス (推論器による自動分類):
    WidebodyFlight  ≡ Flight ⊓ ∃operatedWithModel.WidebodyModel
    DomesticFlight  ≡ Flight ⊓ departureCountry∋japan ⊓ arrivalCountry∋japan
    DisruptedFlight ≡ Flight ⊓ ∃affectedBy.OperationalEvent
- Functional プロパティ、Disjoint、日英ラベル
"""

from pathlib import Path

from owlready2 import (
    AllDisjoint,
    DataProperty,
    FunctionalProperty,
    ObjectProperty,
    PropertyChain,
    Thing,
    TransitiveProperty,
    get_ontology,
    locstr,
)
from rdflib import Graph

BASE_IRI = "https://example.org/onto/aviation#"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

onto = get_ontology(BASE_IRI)

with onto:
    # ---- クラス ----
    class Flight(Thing):
        label = [locstr("フライト", "ja"), locstr("Flight", "en")]

    class Airport(Thing):
        label = [locstr("空港", "ja")]

    class Country(Thing):
        label = [locstr("国", "ja")]

    class Airline(Thing):
        label = [locstr("航空会社", "ja")]

    class Aircraft(Thing):
        label = [locstr("機材(個体機)", "ja")]

    class AircraftModel(Thing):
        label = [locstr("機種", "ja")]

    class WidebodyModel(AircraftModel):
        label = [locstr("ワイドボディ機種", "ja")]

    class NarrowbodyModel(AircraftModel):
        label = [locstr("ナローボディ機種", "ja")]

    class CrewMember(Thing):
        label = [locstr("乗務員", "ja")]

    class Pilot(CrewMember):
        label = [locstr("運航乗務員(パイロット)", "ja")]

    class OperationalEvent(Thing):
        label = [locstr("運航イベント", "ja")]

    class MaintenanceIssue(OperationalEvent):
        label = [locstr("整備事象", "ja")]

    class Delay(OperationalEvent):
        label = [locstr("遅延", "ja")]

    AllDisjoint([Flight, Airport, Country, Airline, Aircraft, AircraftModel,
                 CrewMember, OperationalEvent])
    AllDisjoint([WidebodyModel, NarrowbodyModel])

    # ---- オブジェクトプロパティ ----
    class departsFrom(ObjectProperty, FunctionalProperty):
        domain = [Flight]; range = [Airport]
        label = [locstr("出発空港", "ja")]

    class arrivesAt(ObjectProperty, FunctionalProperty):
        domain = [Flight]; range = [Airport]
        label = [locstr("到着空港", "ja")]

    class locatedIn(ObjectProperty, FunctionalProperty):
        domain = [Airport]; range = [Country]
        label = [locstr("所在国", "ja")]

    class departureCountry(ObjectProperty):
        domain = [Flight]; range = [Country]
        label = [locstr("出発国(導出)", "ja")]

    class arrivalCountry(ObjectProperty):
        domain = [Flight]; range = [Country]
        label = [locstr("到着国(導出)", "ja")]

    departureCountry.property_chain.append(PropertyChain([departsFrom, locatedIn]))
    arrivalCountry.property_chain.append(PropertyChain([arrivesAt, locatedIn]))

    class operatedBy(ObjectProperty, FunctionalProperty):
        domain = [Flight]; range = [Airline]
        label = [locstr("運航会社", "ja")]

    class assignedAircraft(ObjectProperty, FunctionalProperty):
        domain = [Flight]; range = [Aircraft]
        label = [locstr("使用機材", "ja")]

    class hasModel(ObjectProperty, FunctionalProperty):
        domain = [Aircraft]; range = [AircraftModel]
        label = [locstr("機種", "ja")]

    class operatedWithModel(ObjectProperty):
        domain = [Flight]; range = [AircraftModel]
        label = [locstr("運航機種(導出)", "ja")]

    operatedWithModel.property_chain.append(PropertyChain([assignedAircraft, hasModel]))

    class hasOpenIssue(ObjectProperty):
        domain = [Aircraft]; range = [MaintenanceIssue]
        label = [locstr("未解決の整備事象", "ja")]

    class affectedBy(ObjectProperty):
        domain = [Flight]; range = [OperationalEvent]
        label = [locstr("影響を受けている", "ja")]

    # 機材に未解決の整備事象があれば、その機材を使う便は影響を受ける
    affectedBy.property_chain.append(PropertyChain([assignedAircraft, hasOpenIssue]))

    class rotatesTo(ObjectProperty, TransitiveProperty):
        domain = [Flight]; range = [Flight]
        label = [locstr("機材繰りの次レグ(推移的)", "ja")]

    class hasCrew(ObjectProperty):
        domain = [Flight]; range = [CrewMember]
        label = [locstr("乗務員割当", "ja")]

    class ratedOn(ObjectProperty):
        domain = [Pilot]; range = [AircraftModel]
        label = [locstr("限定資格(型式)", "ja")]

    # ---- データプロパティ ----
    class scheduledDeparture(DataProperty, FunctionalProperty):
        domain = [Flight]; range = [str]
        label = [locstr("出発予定時刻", "ja")]

    class delayMinutes(DataProperty, FunctionalProperty):
        domain = [Delay]; range = [int]
        label = [locstr("遅延時間(分)", "ja")]

    class runwayLengthM(DataProperty, FunctionalProperty):
        domain = [Airport]; range = [int]
        label = [locstr("最長滑走路長(m)", "ja")]

    class requiredRunwayM(DataProperty, FunctionalProperty):
        domain = [AircraftModel]; range = [int]
        label = [locstr("必要滑走路長(m)", "ja")]

    # ---- 定義クラス (必要十分条件): 推論器が個体を自動分類する ----
    japan = Country("japan", label=[locstr("日本", "ja")])
    usa = Country("usa", label=[locstr("アメリカ", "ja")])
    singapore = Country("singapore", label=[locstr("シンガポール", "ja")])

    class WidebodyFlight(Flight):
        equivalent_to = [Flight & operatedWithModel.some(WidebodyModel)]
        label = [locstr("ワイドボディ運航便", "ja")]

    class DomesticFlight(Flight):
        equivalent_to = [Flight
                         & departureCountry.value(japan)
                         & arrivalCountry.value(japan)]
        label = [locstr("国内線(日本)", "ja")]

    class DisruptedFlight(Flight):
        equivalent_to = [Flight & affectedBy.some(OperationalEvent)]
        label = [locstr("影響便(要対応)", "ja")]

    # ---- 個体: 空港 (滑走路長はダイバート先推論に使う。値はデモ用の概数) ----
    hnd = Airport("hnd", label=[locstr("東京/羽田", "ja")], locatedIn=japan,
                  runwayLengthM=3360)
    itm = Airport("itm", label=[locstr("大阪/伊丹", "ja")], locatedIn=japan,
                  runwayLengthM=3000)
    cts = Airport("cts", label=[locstr("札幌/新千歳", "ja")], locatedIn=japan,
                  runwayLengthM=3000)
    oka = Airport("oka", label=[locstr("沖縄/那覇", "ja")], locatedIn=japan,
                  runwayLengthM=3000)
    ukb = Airport("ukb", label=[locstr("神戸", "ja")], locatedIn=japan,
                  runwayLengthM=2500)
    ngo = Airport("ngo", label=[locstr("中部/セントレア", "ja")], locatedIn=japan,
                  runwayLengthM=3500)
    lax = Airport("lax", label=[locstr("ロサンゼルス", "ja")], locatedIn=usa,
                  runwayLengthM=3939)
    sin = Airport("sin", label=[locstr("シンガポール", "ja")], locatedIn=singapore,
                  runwayLengthM=4000)

    # ---- 個体: 機種・機材 ----
    b787_9 = WidebodyModel("b787_9", label=[locstr("ボーイング787-9", "ja")],
                           requiredRunwayM=2600)
    b777_300 = WidebodyModel("b777_300", label=[locstr("ボーイング777-300", "ja")],
                             requiredRunwayM=2700)
    a320neo = NarrowbodyModel("a320neo", label=[locstr("エアバスA320neo", "ja")],
                              requiredRunwayM=2000)

    issue_eng01 = MaintenanceIssue(
        "issue_eng01",
        label=[locstr("エンジン防氷系統の点検未完了", "ja")])

    ja801x = Aircraft("ja801x", label=[locstr("JA801X (787-9)", "ja")], hasModel=b787_9)
    ja802x = Aircraft("ja802x", label=[locstr("JA802X (777-300)", "ja")],
                      hasModel=b777_300, hasOpenIssue=[issue_eng01])
    ja803x = Aircraft("ja803x", label=[locstr("JA803X (A320neo)", "ja")], hasModel=a320neo)
    ja804x = Aircraft("ja804x", label=[locstr("JA804X (777-300)", "ja")], hasModel=b777_300)

    # ---- 個体: 航空会社・乗務員・遅延 ----
    aozora = Airline("aozora_air", label=[locstr("青空航空", "ja")])

    capt_sato = Pilot("capt_sato", label=[locstr("佐藤機長", "ja")],
                      ratedOn=[b787_9, b777_300])
    capt_suzuki = Pilot("capt_suzuki", label=[locstr("鈴木機長", "ja")],
                        ratedOn=[a320neo])

    delay_wx01 = Delay("delay_wx01", label=[locstr("羽田の強風による出発遅延", "ja")],
                       delayMinutes=45)

    # ---- 個体: フライト (型は Flight のみ。分類は推論器の仕事) ----
    # JA803X の機材繰り: AZ101 → AZ102 → AZ103 (AZ101 が天候遅延)
    az103 = Flight("az103", label=[locstr("AZ103 羽田→新千歳", "ja")],
                   departsFrom=hnd, arrivesAt=cts, operatedBy=aozora,
                   assignedAircraft=ja803x, scheduledDeparture="15:30",
                   hasCrew=[capt_suzuki])
    az102 = Flight("az102", label=[locstr("AZ102 伊丹→羽田", "ja")],
                   departsFrom=itm, arrivesAt=hnd, operatedBy=aozora,
                   assignedAircraft=ja803x, scheduledDeparture="11:00",
                   hasCrew=[capt_suzuki], rotatesTo=[az103])
    az101 = Flight("az101", label=[locstr("AZ101 羽田→伊丹", "ja")],
                   departsFrom=hnd, arrivesAt=itm, operatedBy=aozora,
                   assignedAircraft=ja803x, scheduledDeparture="08:00",
                   hasCrew=[capt_suzuki], rotatesTo=[az102],
                   affectedBy=[delay_wx01])

    # 国際線 (787 ワイドボディ、資格 OK)
    Flight("az012", label=[locstr("AZ012 羽田→ロサンゼルス", "ja")],
           departsFrom=hnd, arrivesAt=lax, operatedBy=aozora,
           assignedAircraft=ja801x, scheduledDeparture="22:55",
           hasCrew=[capt_sato])

    # 国際線 (777、機材に未解決整備事象あり → 影響便と推論されるはず)
    # さらに鈴木機長は A320 限定のみ → 資格チェックで違反検出されるはず
    Flight("az141", label=[locstr("AZ141 羽田→シンガポール", "ja")],
           departsFrom=hnd, arrivesAt=sin, operatedBy=aozora,
           assignedAircraft=ja802x, scheduledDeparture="10:45",
           hasCrew=[capt_suzuki])

    # 国内線ワイドボディ (777 で羽田→那覇: 国内線かつワイドボディの両方に分類されるはず)
    Flight("az987", label=[locstr("AZ987 羽田→那覇", "ja")],
           departsFrom=hnd, arrivesAt=oka, operatedBy=aozora,
           assignedAircraft=ja804x, scheduledDeparture="09:20",
           hasCrew=[capt_sato])


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    owl_path = OUTPUT_DIR / "aviation.owl"
    ttl_path = OUTPUT_DIR / "aviation.ttl"

    onto.save(file=str(owl_path), format="rdfxml")

    g = Graph()
    g.parse(owl_path, format="xml")
    g.bind("avi", BASE_IRI)
    g.serialize(destination=ttl_path, format="turtle")

    print(f"クラス数        : {len(list(onto.classes()))}")
    print(f"プロパティ数    : {len(list(onto.properties()))}")
    print(f"個体数          : {len(list(onto.individuals()))}")
    print(f"トリプル数(RDF) : {len(g)}")
    print(f"保存先          : {owl_path}")
    print(f"                  {ttl_path}")


if __name__ == "__main__":
    main()

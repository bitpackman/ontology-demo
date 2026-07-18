"""イレギュラー運航 (IROPS) シナリオ: 台風接近時の運航統制モデル。

build_ontology.py の航空オントロジーを拡張し、
「台風21号が沖縄に接近し、那覇空港が運用制限に入った日」を構築する。

追加するモデル:
- 気象イベント: Typhoon ⊑ WeatherEvent ⊑ OperationalEvent
- 空港レベルの運用制限: disruptedBy (Airport → OperationalEvent)
- 空港制限の便への波及 (プロパティチェーン):
    affectedBy ⊇ departsFrom ∘ disruptedBy   (出発空港が制限 → 便に影響)
    affectedBy ⊇ arrivesAt  ∘ disruptedBy   (到着空港が制限 → 便に影響)
- 乗務員繰り: crewConnectsTo (Flight → Flight)
    機材は別でも、前便の乗務員が次便に乗り継ぐ場合の波及経路
- 旅客: Passenger / bookedOn、および定義クラス
    AffectedPassenger ≡ Passenger ⊓ ∃bookedOn.DisruptedFlight
    (影響便の判定が推論なら、影響旅客の抽出も推論の連鎖で自動化できる)

シナリオ追加データ:
- 台風21号 → 那覇 (OKA) が運用制限
- JA804X の機材繰り: AZ987 羽田→那覇 → AZ988 那覇→羽田 → AZ989 羽田→伊丹
- 佐藤機長は AZ988 で羽田に戻った後、別機材の AZ345 羽田→福岡 に乗務 (乗務員繰り)
- 旅客 4 名 (乗継客・整備影響便の客・非影響の客を含む)
"""

from pathlib import Path

import build_ontology as bo
from owlready2 import ObjectProperty, PropertyChain, Thing, locstr
from rdflib import Graph

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

onto = bo.onto

with onto:
    # ---- 語彙の拡張 ----
    class WeatherEvent(bo.OperationalEvent):
        label = [locstr("気象イベント", "ja")]

    class Typhoon(WeatherEvent):
        label = [locstr("台風", "ja")]

    class disruptedBy(ObjectProperty):
        domain = [bo.Airport]
        range = [bo.OperationalEvent]
        label = [locstr("運用制限の原因", "ja")]

    # 空港の運用制限は、その空港を発着するすべての便に波及する
    bo.affectedBy.property_chain.append(PropertyChain([bo.departsFrom, disruptedBy]))
    bo.affectedBy.property_chain.append(PropertyChain([bo.arrivesAt, disruptedBy]))

    class crewConnectsTo(ObjectProperty):
        domain = [bo.Flight]
        range = [bo.Flight]
        label = [locstr("乗務員繰りの次便", "ja")]

    class Passenger(Thing):
        label = [locstr("旅客", "ja")]

    class bookedOn(ObjectProperty):
        domain = [Passenger]
        range = [bo.Flight]
        label = [locstr("予約便", "ja")]

    class AffectedPassenger(Passenger):
        equivalent_to = [Passenger & bookedOn.some(bo.DisruptedFlight)]
        label = [locstr("影響旅客(要リブック確認)", "ja")]

    # ---- シナリオ: 台風21号の接近 ----
    typhoon_21 = Typhoon("typhoon_21",
                         label=[locstr("台風21号(沖縄本島に接近中)", "ja")])
    onto.oka.disruptedBy = [typhoon_21]

    # ---- 追加の空港・機材・フライト ----
    fuk = bo.Airport("fuk", label=[locstr("福岡", "ja")], locatedIn=onto.japan,
                     runwayLengthM=2800)
    ja805x = bo.Aircraft("ja805x", label=[locstr("JA805X (A320neo)", "ja")],
                         hasModel=onto.a320neo)

    # JA804X の機材繰り: AZ987 → AZ988 → AZ989
    az989 = bo.Flight("az989", label=[locstr("AZ989 羽田→伊丹", "ja")],
                      departsFrom=onto.hnd, arrivesAt=onto.itm,
                      operatedBy=onto.aozora_air, assignedAircraft=onto.ja804x,
                      scheduledDeparture="18:00", hasCrew=[onto.capt_sato])
    az988 = bo.Flight("az988", label=[locstr("AZ988 那覇→羽田", "ja")],
                      departsFrom=onto.oka, arrivesAt=onto.hnd,
                      operatedBy=onto.aozora_air, assignedAircraft=onto.ja804x,
                      scheduledDeparture="12:40", hasCrew=[onto.capt_sato],
                      rotatesTo=[az989])
    onto.az987.rotatesTo = [az988]

    # 乗務員繰り: AZ988 で羽田に戻った佐藤機長が、別機材 JA805X の AZ345 に乗務。
    # 機材繰り (rotatesTo) では繋がっていないのに、乗務員経由で波及リスクが生じる。
    az345 = bo.Flight("az345", label=[locstr("AZ345 羽田→福岡", "ja")],
                      departsFrom=onto.hnd, arrivesAt=fuk,
                      operatedBy=onto.aozora_air, assignedAircraft=ja805x,
                      scheduledDeparture="19:30", hasCrew=[onto.capt_sato])
    az988.crewConnectsTo = [az345]

    # ---- 旅客 ----
    Passenger("pax_tanaka", label=[locstr("田中様", "ja")],
              bookedOn=[onto.az987])                       # 那覇行き → 台風影響
    Passenger("pax_ito", label=[locstr("伊藤様", "ja")],
              bookedOn=[onto.az102, onto.az987])           # 伊丹→羽田→那覇の乗継
    Passenger("pax_sasaki", label=[locstr("佐々木様", "ja")],
              bookedOn=[onto.az141])                       # 整備影響便
    Passenger("pax_takahashi", label=[locstr("高橋様", "ja")],
              bookedOn=[onto.az012])                       # 影響なし (対照用)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    owl_path = OUTPUT_DIR / "aviation_irregular.owl"
    ttl_path = OUTPUT_DIR / "aviation_irregular.ttl"

    onto.save(file=str(owl_path), format="rdfxml")
    g = Graph()
    g.parse(owl_path, format="xml")
    g.bind("avi", bo.BASE_IRI)
    g.serialize(destination=ttl_path, format="turtle")

    print("台風21号シナリオを構築しました (基本オントロジー + IROPS 拡張)")
    print(f"クラス数        : {len(list(onto.classes()))}")
    print(f"個体数          : {len(list(onto.individuals()))}")
    print(f"トリプル数(RDF) : {len(g)}")
    print(f"保存先          : {ttl_path}")


if __name__ == "__main__":
    main()

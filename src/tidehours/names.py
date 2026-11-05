"""Corrections to NOAA's station names, for display (docs/DECISIONS.md 0020).

Each entry is station id -> (the name as `catalog.tidy_name` gives it from
NOAA's list, the name the site shows). An entry applies only while NOAA's
name is still the one it corrects: when a data refresh changes the name, the
station shows NOAA's new name and `tests/test_site.py` fails until the entry
is updated or removed. Ids, URLs and the data file keep NOAA's name.
"""

from __future__ import annotations

# NOAA misspellings. Each is backed by the USGS GNIS official name of a
# feature near the station (the per-state DomesticNames files, distance from
# the station in km), and where NOAA's own harmonic-constants list spells it
# differently, that name too. Beacon (8518934): GNIS has no "Flushkill";
# NOAA's harmonic-constants list calls the station "Beacon, Hudson River",
# which is used rather than guessing at "Fishkill".
MISSPELLINGS: dict[str, tuple[str, str]] = {
    "8410715": ("Garnet Point, Pennamquan River", "Garnet Point, Pennamaquan River"),  # GNIS: Pennamaquan River (Stream, 1.6 km); NOAA harcon: GARNET POINT, HERSEY NECK
    "8412581": ("Millbridge, Narraguagus River, Maine", "Milbridge, Narraguagus River, Maine"),  # GNIS: Milbridge (Populated Place, 0.7 km); NOAA harcon: Milbridge
    "8512451": ("Ponquoque Point", "Ponquogue Point"),  # GNIS: Ponquogue Point (Cape, 0.3 km); NOAA harcon: PONQUOGUE POINT
    "8518934": ("Beacon, Flushkill", "Beacon, Hudson River"),  # GNIS: Fishkill Creek (Stream, 1.7 km); NOAA harcon: Beacon, Hudson River
    "8638445": ("Lanexa, Chicahomny River", "Lanexa, Chickahominy River"),  # GNIS: Chickahominy Shores (Populated Place, 2.8 km); NOAA harcon: Lanexa, Chickahominy River
    "8724996": ("McIlvaine Bay", "McIlvane Bay"),  # GNIS: McIlvane Bay (Bay, 1.1 km); NOAA harcon: MCILVAINE BAY
    "8729747": ("Shield Point, Blackwater River", "Shields Point, Blackwater River"),  # GNIS: Shields Point (Cape, 0.3 km); NOAA harcon: SHIELD POINT, BLACKWATER RIVER
    "8737138": ("William Brooks Park, Chichasaw Creek", "William Brooks Park, Chickasaw Creek"),  # GNIS: City of Chickasaw (Civil, 1.3 km); NOAA harcon: Chickasaw Creek
    "8739803": ("Bayou LaBatre Bridge", "Bayou La Batre Bridge"),  # GNIS: Bayou La Batre (Populated Place, 0.3 km); NOAA harcon: Bayou La Batre Bridge
    "8765746": ("Bayou Fearman, Vermillion Bay", "Bayou Fearman, Vermilion Bay"),  # GNIS: Vermilion River (Bay, 10.2 km); NOAA harcon: Bayou Fearman, Vermillion Bay
    "8765994": ("Schooner Bayou, Vermillion Bay", "Schooner Bayou, Vermilion Bay"),  # GNIS: Vermilion Parish (Civil, 7.1 km); NOAA harcon: Schooner Bayou
    "8775132": ("La Qunita Channel North", "La Quinta Channel North"),  # GNIS: La Quinta Island (Island, 2.8 km); NOAA harcon: La Quinta Channel North
    "8779280": ("Realitos Pennisula, Laguna Madre", "Realitos Peninsula, Laguna Madre"),  # GNIS: El Realito Peninsula (Cape, 2.0 km); NOAA harcon: Realitos Peninsula
    "9450192": ("Hidden Inter Entrance, Pearse Inlet", "Hidden Inlet Entrance, Pearse Inlet"),  # GNIS: Hidden Inlet (Bay, 6.1 km); NOAA harcon: HIDDEN INLET ENTRANCE, PEARSE INLET
    "9450753": ("Magnetic Point, Union Bay, Earnest Sound", "Magnetic Point, Union Bay, Ernest Sound"),  # GNIS: Ernest Point (Cape, 13.2 km); NOAA harcon: Magnetic Point, Union Bay, Earnest Sound
    "9450914": ("Burrough Bay, Behm Canal", "Burroughs Bay, Behm Canal"),  # GNIS: Burroughs Bay (Bay, 2.5 km); NOAA harcon: Burrough Bay, Behm Canal
    "9451853": ("Serguis Narrows", "Sergius Narrows"),  # GNIS: Sergius Point (Cape, 0.3 km); NOAA harcon: Sergius Narrows
    "9452438": ("Hoonah, Port Fredrick", "Hoonah, Port Frederick"),  # GNIS: Port Frederick (Bay, 7.9 km); NOAA harcon: Hoonah, Port Fredrick
    "9454616": ("5 miles NE of Point Brazil, Montague Island", "5 miles NE of Point Bazil, Montague Island"),  # GNIS: Point Bazil (Cape, 7.5 km); NOAA harcon: Montague Island
    "9454818": ("Blue Fjord, Port Nellie Juan", "Blue Fiord, Port Nellie Juan"),  # GNIS: Blue Fiord (Bay, 3.2 km); NOAA harcon: BLUE FjORD, PORT NELLIE JUAN
    "9464961": ("Cape Constantine, Nushagak Penninsula", "Cape Constantine, Nushagak Peninsula"),  # GNIS: Nushagak Peninsula (Cape, 10.8 km); NOAA harcon: CAPE CONSTANTINE, NUSHAGAK PENINSULA
    "9466298": ("Nelson Island, Tooksook Bay", "Nelson Island, Toksook Bay"),  # GNIS: City of Toksook Bay (Civil, 1.4 km); NOAA harcon: Nelson Island, Tooksook Bay
    "9469146": ("Umuruk Basin", "Imuruk Basin"),  # GNIS: Imuruk Basin (Lake, 9.5 km); NOAA harcon: Imuruk Basin
    "9469239": ("Teller, Port Clarance", "Teller, Port Clarence"),  # GNIS: Port Clarence (Sea (GNIS, Alaska)); NOAA harcon: TELLER, PORT CLARENCE
    "9751584": ("Fredericksted, St. Croix", "Frederiksted, St. Croix"),  # GNIS: Estate Frederiksted (Civil, 0.2 km); NOAA harcon: Fredericksted, St. Croix
    "9759421": ("Punta Guanajibo, Mayagues", "Punta Guanajibo, Mayagüez"),  # GNIS: Jardines de Mayaquez (Populated Place, 4.3 km); NOAA harcon: PUNTA GUANAJIBO, MAYAGUES
    "1616696": ("Kuheia Bay", "Kuheeia Bay"),  # GNIS: Kuheeia Bay (Bay, 0.6 km)
    "8447742": ("Poponesset Island, Poponesset Bay", "Popponesset Island, Popponesset Bay"),  # GNIS: Popponesset Island (Populated Place, 0.4 km)
    "8530186": ("New Millford", "New Milford"),  # GNIS: Borough of New Milford (Civil, 0.9 km)
    "8536801": ("Riggins Ditch, 0.5 n.mi. above entrance", "Riggin Ditch, 0.5 n.mi. above entrance"),  # GNIS: Riggin Ditch (Canal, 2.6 km)
    "8536855": ("Riggins Ditch, Heislerville", "Riggin Ditch, Heislerville"),  # GNIS: Riggin Ditch (Canal, 0.4 km)
    "8571181": ("Colburn Creek, Big Annemessex River", "Colbourn Creek, Big Annemessex River"),  # GNIS: Colbourn Creek (Stream, 0.5 km)
    "8571881": ("Cherry Island, Beckwiths Creek", "Cherry Island, Beckwith Creek"),  # GNIS: Beckwith Creek (Bay, 1.7 km)
    "8578465": ("Colton Point, Md.", "Coltons Point, Md."),  # GNIS: Coltons Point (Cape, 0.3 km)
    "8665257": ("Canaday Landing, south of, Edisto River", "Canady Landing, south of, Edisto River"),  # GNIS: Canady Landing (Populated Place, 0.3 km)
    "8726089": ("Longboats Key, Sarasota Bay", "Longboat Key, Sarasota Bay"),  # GNIS: Town of Longboat Key (Civil, 7.3 km)
    "8761993": ("Tchefuncta River, Lake Pontchartrain", "Tchefuncte River, Lake Pontchartrain"),  # GNIS: Tchefuncte River (Stream, 0.2 km)
    "9446800": ("Dofflemeyer Point, Boston Hbr., Budd Inlet", "Dofflemyer Point, Boston Hbr., Budd Inlet"),  # GNIS: Dofflemyer Point (Cape, 0.4 km)
    "9450258": ("Keete Island, Nutkwa Inlets", "Keete Island, Nutkwa Inlet"),  # GNIS: Keete Inlet (Bay, 3.3 km)
    "TWC1785": ("Lindenburg Head", "Lindenberg Head"),  # GNIS: Lindenberg Harbor (Bay, 1.0 km)
}  # fmt: skip

# Spanish diacritics for Puerto Rico, as GNIS writes the names.
SPANISH: dict[str, tuple[str, str]] = {
    "9758053": ("Penuelas (Punta Guayanilla)", "Peñuelas (Punta Guayanilla)"),
    "9758627": ("Guanica", "Guánica"),
    "9759173": ("Boqueron", "Boquerón"),
    "9759197": ("Bahia Salinas", "Bahía Salinas"),
    "9759394": ("Mayaguez", "Mayagüez"),
}  # fmt: skip

# Hawaiian ʻokina and kahakō, as GNIS writes the names. Names GNIS does not
# confirm are left as NOAA writes them (Moku o Loe, Kaumalapau).
HAWAIIAN: dict[str, tuple[str, str]] = {
    "1611347": ("Port Allen, Hanapepe Bay", "Port Allen, Hanapēpē Bay"),
    "1611400": ("Nawiliwili", "Nāwiliwili"),
    "1610367": ("Nonopapa, Niihau Island", "Nonopapa, Niʻihau Island"),
    "1612376": ("Waimanalo", "Waimānalo"),
    "1612482": ("Waianae", "Waiʻanae"),
    "1612668": ("Haleiwa, Waialua Bay", "Haleʻiwa, Waialua Bay"),
    "1613077": ("Kamalo Harbor", "Kamalō Harbor"),
    "1613155": ("Pukoo Harbor", "Pūkoʻo Harbor"),
    "1614465": ("Kaumalapau, Lanai Island", "Kaumalapau, Lānaʻi Island"),
    "1615202": ("Makena", "Mākena"),
    "1615395": ("Hana", "Hāna"),
    "1618021": ("Napoopoo, Kealakekua Bay", "Nāpōʻopoʻo, Kealakekua Bay"),
    "1618578": ("Honuapo", "Honuʻapo"),
}  # fmt: skip

# NOAA's lowercase words, abbreviations that read as words once the name is
# out of capitals ("Vineyard Hvn Hbr", "Yaquina USCG Sta"), and "St. Park",
# where "St." means State.
CASING: dict[str, tuple[str, str]] = {
    "1612480": ("Moku O Loe", "Moku o Loe"),
    "8448157": ("Vineyard Haven, Vineyard Hvn Hbr", "Vineyard Haven, Vineyard Haven Harbor"),
    "8661070": ("Springmaid Pier, Myrtle beach", "Springmaid Pier, Myrtle Beach"),
    "8664699": ("North Charleston, Ashley river", "North Charleston, Ashley River"),
    "8720011": ("Cut 1N Front Range, St Marys River Entr", "Cut 1N Front Range, St. Marys River Entrance"),
    "8725019": ("Keewaydin island (inside)", "Keewaydin Island (inside)"),
    "8761115": ("Bay Pomme D'or", "Bay Pomme d'Or"),
    "9448614": ("Deception Pass St. Park, Bowman Bay, Fidalgo I.", "Deception Pass State Park, Bowman Bay, Fidalgo I."),
    "9469677": ("Buckland, Buckland river", "Buckland, Buckland River"),
    "8450898": ("North End, Bay Oil pier", "North End, Bay Oil Pier"),
    "9435385": ("Yaquina USCG Sta, Newport", "Yaquina USCG Station, Newport"),
    "9454674": ("Macleod Harbor", "MacLeod Harbor"),
}  # fmt: skip

# Stray punctuation: a period or comma where the other belongs, and a period
# ending a full word. Abbreviations keep theirs ("Fidalgo I.", "ent.").
PUNCTUATION: dict[str, tuple[str, str]] = {
    "8669246": ("Brighton Beach. May River", "Brighton Beach, May River"),
    "9751082": ("Grapetree Bay, St, Croix", "Grapetree Bay, St. Croix"),
    "9451095": ("Port Protection, Prince of Wales Island.", "Port Protection, Prince of Wales Island"),
    "TEC3061": ("Shipyard Creek, 0.8 mile above entrance.", "Shipyard Creek, 0.8 mile above entrance"),
}  # fmt: skip

# "St." for Saint everywhere, as NOAA writes it in 68 names and the towns
# write it themselves (Port St. Joe, St. Helens). Street ("Madison St.") is
# left alone.
SAINT: dict[str, tuple[str, str]] = {
    "8720503": ("Red Bay Point, St Johns River", "Red Bay Point, St. Johns River"),
    "8720625": ("Racy Point, St Johns River", "Racy Point, St. Johns River"),
    "8728912": ("Port Saint Joe, St. Joseph Bay", "Port St. Joe, St. Joseph Bay"),
    "9439201": ("Saint Helens", "St. Helens"),
    "9466229": ("Offshore St Matthew Island (GNSS Buoy)", "Offshore St. Matthew Island (GNSS Buoy)"),
    "9751364": ("Christiansted Harbor, St Croix", "Christiansted Harbor, St. Croix"),
    "9751401": ("Lime Tree Bay, St.Croix Island", "Lime Tree Bay, St. Croix Island"),
    "9751768": ("Dorothea Bay, Saint Thomas Island", "Dorothea Bay, St. Thomas Island"),
}  # fmt: skip

# Stations that would share a title with another, told apart with NOAA's
# own detail: its current per-station name (mdapi stations/{id}.json) or,
# for Anchor Point, its region.
DUPLICATES: dict[str, tuple[str, str]] = {
    "8772440": ("Freeport Harbor", "Freeport"),  # NOAA: FREEPORT; 8772471 keeps Freeport Harbor
    "9451317": ("Anchor Point", "Anchor Point, Wrangell Narrows"),  # NOAA region: Wrangell Narrows
    "9455606": ("Anchor Point", "Anchor Point, Cook Inlet"),  # NOAA: Anchor Point, Cook Inlet
    "8724224": ("Little Torch Key, Pine Channel Bridge, south side", "Little Torch Key"),  # NOAA: LITTLE TORCH KEY
    "8542885": ("Tinicum National Wildlife Refuge", "Tinicum National Wildlife Refuge 4"),  # NOAA: TINICUM 4, DARBY CREEK
    "8543024": ("Tinicum National Wildlife Refuge", "Tinicum National Wildlife Refuge 3"),  # NOAA: TINICUM 3, DARBY CREEK
}  # fmt: skip

NAME_FIXES: dict[str, tuple[str, str]] = {
    **MISSPELLINGS,
    **SPANISH,
    **HAWAIIAN,
    **CASING,
    **PUNCTUATION,
    **SAINT,
    **DUPLICATES,
}


def fixed_name(station_id: str, name: str) -> str:
    """The name the site shows for a station whose tidied NOAA name is
    `name`: the correction in NAME_FIXES while NOAA's name is still the one
    it corrects, otherwise `name` itself."""
    fix = NAME_FIXES.get(station_id)
    if fix is not None and fix[0] == name:
        return fix[1]
    return name

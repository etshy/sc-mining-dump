#!/usr/bin/env python3
"""
Extract mineable ore data from Star Citizen mining XML files.

Generates:
  - ores.json                  : ore/element definitions with all mining properties
  - deposits.json              : rock/deposit compositions with resolved ore names
  - deposits_by_category.json  : deposits grouped by category
  - ores_in_deposits.json      : inverted index — ore → every deposit containing it
  - locations.json             : provider presets fully resolved:
                                   location → mining groups → presets → entity → composition → ores
  - ores_by_location.json      : inverted index — ore → every location where it spawns
"""

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import defaultdict


RECORDS_DIR    = Path(__file__).parent / "input" / "Data" / "Libs" / "Foundry" / "Records"
MINING_DIR     = RECORDS_DIR / "mining"
HARVESTABLE_DIR = RECORDS_DIR / "harvestable"
ENTITIES_DIR   = RECORDS_DIR / "entities" / "mineable"
PROVIDER_DIR   = HARVESTABLE_DIR / "providerpresets" / "system"
OUTPUT_DIR     = Path(__file__).parent / "output"

NULL_UUID = "00000000-0000-0000-0000-000000000000"

# ---------------------------------------------------------------------------
# Location name mappings
# ---------------------------------------------------------------------------

# Maps hpp file-stem body part (after stripping "hpp_") to a human-readable name.
BODY_NAMES: dict[str, str] = {
    # Stanton – planets
    "stanton1":  "Hurston",
    "stanton2":  "Crusader",
    "stanton3":  "ArcCorp",
    "stanton4":  "MicroTech",
    # Stanton – moons
    "stanton1a": "Arial",
    "stanton1b": "Aberdeen",
    "stanton1c": "Magda",
    "stanton1d": "Ita",
    "stanton2a": "Cellin",
    "stanton2b": "Daymar",
    "stanton2c": "Yela",
    "stanton3a": "Lyria",
    "stanton3b": "Wala",
    "stanton4a": "Calliope",
    "stanton4b": "Clio",
    "stanton4c": "Euterpe",
    # Pyro – planets/gas giants
    "pyro1":  "Athos",
    "pyro2":  "Monox",
    "pyro3":  "Bloom",
    "pyro4":  "Terminus",
    "pyro5":  "Pyro V",
    "pyro6":  "Adir",
    # Pyro – moons of Pyro V
    "pyro5a": "Ignis",
    "pyro5b": "Pyro V-b",
    "pyro5c": "Pyro V-c",
    "pyro5d": "Pyro V-d",
    "pyro5e": "Pyro V-e",
    "pyro5f": "Pyro V-f",
}

ASTEROID_FIELD_NAMES: dict[str, str] = {
    # Stanton
    "aaronhalo":                    "Aaron Halo",
    "lagrange_a":                   "Lagrange A",
    "lagrange_b":                   "Lagrange B",
    "lagrange_c":                   "Lagrange C",
    "lagrange_d":                   "Lagrange D",
    "lagrange_e":                   "Lagrange E",
    "lagrange_f":                   "Lagrange F",
    "lagrange_g":                   "Lagrange G",
    "lagrange_occupied":            "Lagrange (Occupied)",
    "stanton2c_belt":               "Yela Belt",
    "asteroidcluster_low_yield":    "Asteroid Cluster (Low Yield)",
    "asteroidcluster_medium_yield": "Asteroid Cluster (Medium Yield)",
    "resourcerush_gold":            "Resource Rush – Gold",
    "resourcerush_gold_highdensity":"Resource Rush – Gold (High Density)",
    # Nyx
    "nyx_keegerbelt":  "Keeger Belt",
    "nyx_glaciemring": "Glaciem Ring",
    # Pyro
    "pyro_akirocluster":        "Akiro Cluster",
    "pyro_cool01":              "Pyro Asteroid Field (Cool 01)",
    "pyro_cool02":              "Pyro Asteroid Field (Cool 02)",
    "pyro_warm01":              "Pyro Asteroid Field (Warm 01)",
    "pyro_warm02":              "Pyro Asteroid Field (Warm 02)",
    "pyro_deepspaceasteroids":  "Pyro Deep Space Asteroids",
}

SYSTEM_NAMES: dict[str, str] = {
    "stanton": "Stanton",
    "pyro":    "Pyro",
    "nyx":     "Nyx",
}

# Maps groupName to a tidy mining-mode string
MINING_MODE: dict[str, str] = {
    "SpaceShip_Mineables":   "ship",
    "FPS_Mineables":         "fps",
    "GroundVehicle_Mineables": "vehicle",
    "Havestables":           "general",   # typo in game data
    "Harvestables":          "general",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag_suffix(tag: str) -> str:
    """'MineableElement.Iron_Ore' → 'Iron_Ore'"""
    return tag.split(".", 1)[1] if "." in tag else tag


def _localization_to_display(key: str) -> str:
    if not key.startswith("@"):
        return key
    name = key[1:]
    for prefix in ("hud_mining_", "items_commodities_", "items_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.replace("_", " ").title()


def _f(value) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _i(value, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_xml(path: Path):
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        print(f"  [WARN] Could not parse {path}: {exc}")
        return None


def _rarity(stem: str) -> str | None:
    s = stem.lower()
    for tier in ("legendary", "epic", "rare", "uncommon", "common"):
        if tier in s:
            return tier
    return None


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    count = len(data) if isinstance(data, (list, dict)) else "—"
    print(f"  Written: {path.relative_to(path.parent.parent)}  ({count} entries)")


# ---------------------------------------------------------------------------
# Step 1 — MineableElement definitions
# ---------------------------------------------------------------------------

def load_ore_elements(elements_dir: Path) -> dict:
    """Returns { uuid: ore_dict } for every MineableElement XML."""
    ores: dict = {}
    for xml_file in sorted(elements_dir.glob("*.xml")):
        root = _parse_xml(xml_file)
        if root is None or root.get("__type") != "MineableElement":
            continue
        ref = root.get("__ref")
        if not ref:
            continue
        ore_name = _tag_suffix(root.tag)
        if "template" in ore_name.lower():
            continue
        ores[ref] = {
            "id":                             ref,
            "name":                           ore_name,
            "display_name":                   ore_name.replace("_", " ").title(),
            "resource_type":                  root.get("resourceType", ""),
            "instability":                    _f(root.get("elementInstability")),
            "resistance":                     _f(root.get("elementResistance")),
            "optimal_window_midpoint":        _f(root.get("elementOptimalWindowMidpoint")),
            "optimal_window_midpoint_randomness": _f(root.get("elementOptimalWindowMidpointRandomness")),
            "optimal_window_thinness":        _f(root.get("elementOptimalWindowThinness")),
            "explosion_multiplier":           _f(root.get("elementExplosionMultiplier")),
            "cluster_factor":                 _f(root.get("elementClusterFactor")),
            "source_file":                    xml_file.name,
        }
    return ores


# ---------------------------------------------------------------------------
# Step 2 — MineableComposition presets
# ---------------------------------------------------------------------------

def _category(xml_path: Path, presets_dir: Path) -> str:
    rel = xml_path.relative_to(presets_dir)
    parts_lower = [p.lower() for p in rel.parts]
    if "surfaceshipmining" in parts_lower:
        return "surface_ship"
    if "asteroidshipmining" in parts_lower:
        return "asteroid_ship"
    stem = xml_path.stem.lower()
    if stem.startswith("fps_"):
        return "fps"
    if stem.startswith("asteroid_"):
        return "asteroid"
    if stem.startswith("groundvehicle_"):
        return "vehicle"
    if any(d in stem for d in ("deposit", "atacamite", "felsic", "gneiss", "granite",
                                "igneous", "obsidian", "quartzite", "shale")):
        return "surface"
    if "test" in stem:
        return "test"
    return "other"


def load_compositions(presets_dir: Path, ores_by_id: dict) -> dict:
    """Returns { uuid: deposit_dict } for every MineableComposition XML."""
    deposits: dict = {}
    unknown_refs: set = set()

    for xml_file in sorted(presets_dir.rglob("*.xml")):
        root = _parse_xml(xml_file)
        if root is None or root.get("__type") != "MineableComposition":
            continue
        name = _tag_suffix(root.tag)
        if "template" in name.lower():
            continue
        ref = root.get("__ref", "")
        deposit_key = root.get("depositName", "")
        category = _category(xml_file, presets_dir)
        rarity = _rarity(xml_file.stem)

        composition = []
        array_node = root.find("compositionArray")
        if array_node is not None:
            for part in array_node.findall("MineableCompositionPart"):
                eid = part.get("mineableElement", "")
                ore = ores_by_id.get(eid)
                if ore is None:
                    unknown_refs.add(eid)
                composition.append({
                    "ore_id":          eid,
                    "ore_name":        ore["name"] if ore else f"unknown_{eid[:8]}",
                    "ore_display_name": ore["display_name"] if ore else f"Unknown ({eid[:8]})",
                    "probability":     _f(part.get("probability")),
                    "min_percentage":  _f(part.get("minPercentage")),
                    "max_percentage":  _f(part.get("maxPercentage")),
                    "quality_scale":   _f(part.get("qualityScale")),
                    "curve_exponent":  _f(part.get("curveExponent")),
                })

        deposits[ref] = {
            "id":                        ref,
            "name":                      name,
            "display_name":              _localization_to_display(deposit_key),
            "deposit_name_key":          deposit_key,
            "category":                  category,
            "rarity":                    rarity,
            "minimum_distinct_elements": _i(root.get("minimumDistinctElements")),
            "source_file":               str(xml_file.relative_to(presets_dir.parent)),
            "composition":               composition,
        }

    if unknown_refs:
        print(f"  [INFO] {len(unknown_refs)} ore UUIDs in compositions not found "
              f"in mineableelements (likely template/waste entries).")
    return deposits


# ---------------------------------------------------------------------------
# Step 3 — Mineable entity class definitions
# ---------------------------------------------------------------------------

def load_mineable_entities(entities_dir: Path) -> dict:
    """
    Returns { uuid: entity_dict } for every EntityClassDefinition with a
    MineableParams component (i.e., actually mineable rocks).
    """
    entities: dict = {}

    for xml_file in sorted(entities_dir.glob("*.xml")):
        root = _parse_xml(xml_file)
        if root is None or root.get("__type") != "EntityClassDefinition":
            continue
        ref = root.get("__ref", "")
        if not ref or ref == NULL_UUID:
            continue

        # Find MineableParams component
        mineable_params = root.find(
            ".//MineableParams[@__polymorphicType='MineableParams']"
        )
        if mineable_params is None:
            continue

        composition_id = mineable_params.get("composition", "")
        filled_factor  = _f(mineable_params.get("filledFactor", "1"))

        # Extract health/damage params for laser_damage_full_value
        health_node = root.find(
            ".//SMineableHealthComponentParams/damageMapParamsCenter"
        )
        laser_damage = 0.0
        if health_node is not None:
            laser_damage = _f(health_node.get("laserDamageFullValue"))

        entities[ref] = {
            "id":               ref,
            "name":             _tag_suffix(root.tag),
            "composition_id":   composition_id,
            "filled_factor":    filled_factor,
            "laser_damage_full_value": laser_damage,
            "source_file":      xml_file.name,
        }

    return entities


# ---------------------------------------------------------------------------
# Step 4 — HarvestablePreset records
# ---------------------------------------------------------------------------

def load_harvestable_presets(presets_dir: Path) -> dict:
    """
    Returns { uuid: preset_dict } for every HarvestablePreset XML.
    Only keeps presets whose entityClass is non-null (filters out placeholder entries).
    """
    presets: dict = {}

    for xml_file in sorted(presets_dir.rglob("*.xml")):
        root = _parse_xml(xml_file)
        if root is None or root.get("__type") != "HarvestablePreset":
            continue
        ref = root.get("__ref", "")
        if not ref:
            continue

        entity_class_id = root.get("entityClass", NULL_UUID)
        respawn_time    = _i(root.get("respawnInSlotTime"), 3600)

        transform = root.find("transformParams")
        scale_min = _f(transform.get("minScale")) if transform is not None else 0.0
        scale_max = _f(transform.get("maxScale")) if transform is not None else 1.0

        despawn = root.find(".//despawnTimer")
        despawn_time = _i(despawn.get("despawnTimeSeconds")) if despawn is not None else 0
        despawn_wait = _i(despawn.get("additionalWaitForNearbyPlayersSeconds")) if despawn is not None else 0

        presets[ref] = {
            "id":                ref,
            "name":              _tag_suffix(root.tag),
            "entity_class_id":   entity_class_id,
            "respawn_time_s":    respawn_time,
            "despawn_time_s":    despawn_time,
            "despawn_wait_s":    despawn_wait,
            "scale_min":         scale_min,
            "scale_max":         scale_max,
            "source_file":       xml_file.name,
        }

    return presets


# ---------------------------------------------------------------------------
# Step 5 — HarvestableProviderPreset (location → groups → presets)
# ---------------------------------------------------------------------------

def _location_meta(xml_path: Path) -> dict:
    """Derive system, body, zone_type from the provider preset file path."""
    # Expected path structure: .../system/<system>/[asteroidfield/]hpp_*.xml
    parts = xml_path.parts
    try:
        sys_idx = next(i for i, p in enumerate(parts) if p == "system")
        system_key = parts[sys_idx + 1].lower()
    except (StopIteration, IndexError):
        system_key = "unknown"

    system = SYSTEM_NAMES.get(system_key, system_key.title())
    is_asteroid_field = "asteroidfield" in [p.lower() for p in parts]
    zone_type = "asteroid_field" if is_asteroid_field else "planet"

    stem = xml_path.stem.lower()
    if stem.startswith("hpp_"):
        stem = stem[4:]

    if is_asteroid_field:
        body = ASTEROID_FIELD_NAMES.get(stem, stem.replace("_", " ").title())
    else:
        body = BODY_NAMES.get(stem, stem.replace("_", " ").title())

    return {
        "system":    system,
        "body":      body,
        "zone_type": zone_type,
    }


def _resolve_item(
    preset_id: str,
    relative_probability: float,
    total_group_prob: float,
    presets_by_id: dict,
    entities_by_id: dict,
    compositions_by_id: dict,
) -> dict | None:
    """
    Resolve a single HarvestableElement entry all the way down to ore composition.
    Returns None if the chain can't be resolved to a mineable rock.
    """
    preset = presets_by_id.get(preset_id)
    if preset is None:
        return None

    entity_class_id = preset.get("entity_class_id", NULL_UUID)
    entity = entities_by_id.get(entity_class_id)
    if entity is None:
        return None  # not a mineable rock entity

    composition_id = entity.get("composition_id", "")
    composition = compositions_by_id.get(composition_id)

    norm_prob = (relative_probability / total_group_prob) if total_group_prob > 0 else 0.0

    item: dict = {
        "relative_probability":   relative_probability,
        "normalized_probability": round(norm_prob, 6),
        "preset_id":              preset_id,
        "preset_name":            preset["name"],
        "respawn_time_s":         preset["respawn_time_s"],
        "despawn_time_s":         preset["despawn_time_s"],
        "scale_min":              preset["scale_min"],
        "scale_max":              preset["scale_max"],
        "entity_id":              entity_class_id,
        "entity_name":            entity["name"],
        "laser_damage_full_value": entity["laser_damage_full_value"],
        "composition_id":         composition_id,
    }

    if composition:
        item.update({
            "composition_name":     composition["name"],
            "composition_display_name": composition["display_name"],
            "composition_category": composition["category"],
            "rarity":               composition.get("rarity"),
            "minimum_distinct_elements": composition["minimum_distinct_elements"],
            "composition":          composition["composition"],
        })
    else:
        item.update({
            "composition_name":     None,
            "composition_display_name": None,
            "composition_category": None,
            "rarity":               None,
            "minimum_distinct_elements": 0,
            "composition":          [],
        })

    return item


def load_locations(
    provider_dir: Path,
    presets_by_id: dict,
    entities_by_id: dict,
    compositions_by_id: dict,
) -> list:
    """
    Parse every HarvestableProviderPreset file and resolve the full chain:
    location → groups → presets → entity → composition → ores.
    Only groups that contain at least one resolvable mineable rock are kept.
    """
    locations = []

    for xml_file in sorted(provider_dir.rglob("*.xml")):
        root = _parse_xml(xml_file)
        if root is None or root.get("__type") != "HarvestableProviderPreset":
            continue

        ref  = root.get("__ref", "")
        name = _tag_suffix(root.tag)
        meta = _location_meta(xml_file)

        groups = []
        for grp in root.findall(".//HarvestableElementGroup"):
            group_name = grp.get("groupName", "Unknown")
            group_prob = _f(grp.get("groupProbability"))
            mining_mode = MINING_MODE.get(group_name, "unknown")

            raw_items = []
            for elem in grp.findall("harvestables/HarvestableElement"):
                pid  = elem.get("harvestable", NULL_UUID)
                rprob = _f(elem.get("relativeProbability"))
                if pid != NULL_UUID:
                    raw_items.append((pid, rprob))

            total_rprob = sum(rp for _, rp in raw_items)

            resolved_items = []
            for pid, rprob in raw_items:
                item = _resolve_item(
                    pid, rprob, total_rprob,
                    presets_by_id, entities_by_id, compositions_by_id,
                )
                if item is not None:
                    resolved_items.append(item)

            if not resolved_items:
                continue  # skip groups with no mineable rocks

            resolved_items.sort(key=lambda x: -x["relative_probability"])
            groups.append({
                "group_name":        group_name,
                "mining_mode":       mining_mode,
                "group_probability": group_prob,
                "total_relative_probability": total_rprob,
                "items":             resolved_items,
            })

        if not groups:
            continue  # skip locations with no mining groups

        locations.append({
            "id":          ref,
            "name":        f"{meta['body']} ({meta['system']})",
            "system":      meta["system"],
            "body":        meta["body"],
            "zone_type":   meta["zone_type"],
            "source_file": str(xml_file.relative_to(provider_dir.parent.parent)),
            "groups":      groups,
        })

    locations.sort(key=lambda x: (x["system"], x["body"]))
    return locations


# ---------------------------------------------------------------------------
# Step 6 — Build inverted index: ore → locations
# ---------------------------------------------------------------------------

def build_ores_by_location(locations: list) -> dict:
    """
    Returns { ore_name: [ {location_info + composition_part_info}, … ] }
    """
    ore_index: dict = defaultdict(list)

    for loc in locations:
        loc_base = {
            "location_id":   loc["id"],
            "location_name": loc["name"],
            "system":        loc["system"],
            "body":          loc["body"],
            "zone_type":     loc["zone_type"],
        }
        for grp in loc["groups"]:
            for item in grp["items"]:
                for part in item.get("composition", []):
                    ore_index[part["ore_name"]].append({
                        **loc_base,
                        "mining_mode":              grp["mining_mode"],
                        "group_name":               grp["group_name"],
                        "group_probability":        grp["group_probability"],
                        "relative_probability":     item["relative_probability"],
                        "normalized_probability":   item["normalized_probability"],
                        "preset_name":              item["preset_name"],
                        "entity_name":              item["entity_name"],
                        "composition_name":         item.get("composition_name"),
                        "composition_category":     item.get("composition_category"),
                        "rarity":                   item.get("rarity"),
                        "respawn_time_s":           item["respawn_time_s"],
                        "scale_min":                item["scale_min"],
                        "scale_max":                item["scale_max"],
                        "ore_probability":          part["probability"],
                        "ore_min_percentage":       part["min_percentage"],
                        "ore_max_percentage":       part["max_percentage"],
                        "ore_quality_scale":        part["quality_scale"],
                    })

    # Sort each ore's appearances: by system, body, then group probability desc
    for ore_name in ore_index:
        ore_index[ore_name].sort(
            key=lambda x: (x["system"], x["body"], -x["group_probability"])
        )

    return dict(sorted(ore_index.items()))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    elements_dir  = MINING_DIR / "mineableelements"
    presets_dir   = MINING_DIR / "rockcompositionpresets"
    preset_hp_dir = HARVESTABLE_DIR / "harvestablepresets"

    for p in (elements_dir, presets_dir, ENTITIES_DIR, preset_hp_dir, PROVIDER_DIR):
        if not p.is_dir():
            raise SystemExit(f"[ERROR] Directory not found: {p}")

    # --- Load source data ---
    print("Loading ore element definitions…")
    ores_by_id = load_ore_elements(elements_dir)
    print(f"  {len(ores_by_id)} ore elements loaded.\n")

    print("Loading rock composition presets…")
    compositions_by_id = load_compositions(presets_dir, ores_by_id)
    print(f"  {len(compositions_by_id)} compositions loaded.\n")

    print("Loading mineable entity class definitions…")
    entities_by_id = load_mineable_entities(ENTITIES_DIR)
    print(f"  {len(entities_by_id)} mineable entities loaded.\n")

    print("Loading harvestable presets…")
    presets_by_id = load_harvestable_presets(preset_hp_dir)
    print(f"  {len(presets_by_id)} harvestable presets loaded.\n")

    print("Loading and resolving location provider presets…")
    locations = load_locations(PROVIDER_DIR, presets_by_id, entities_by_id, compositions_by_id)
    print(f"  {len(locations)} locations with mining data loaded.\n")

    # --- Write output ---
    print("Writing output files…")

    # 1. ores.json
    ores_list = sorted(ores_by_id.values(), key=lambda x: x["name"].lower())
    write_json(OUTPUT_DIR / "ores.json", ores_list)

    # 2. deposits.json
    deposits_list = sorted(compositions_by_id.values(),
                           key=lambda d: (d["category"], d["name"].lower()))
    write_json(OUTPUT_DIR / "deposits.json", deposits_list)

    # 3. deposits_by_category.json
    by_cat: dict = defaultdict(list)
    for d in deposits_list:
        by_cat[d["category"]].append(d)
    write_json(OUTPUT_DIR / "deposits_by_category.json", dict(sorted(by_cat.items())))

    # 4. ores_in_deposits.json – inverted index: ore → deposit appearances
    ore_deposit_index: dict = defaultdict(list)
    for dep in deposits_list:
        for part in dep["composition"]:
            ore_deposit_index[part["ore_name"]].append({
                "deposit_name":         dep["name"],
                "deposit_display_name": dep["display_name"],
                "deposit_id":           dep["id"],
                "category":             dep["category"],
                "rarity":               dep.get("rarity"),
                "probability":          part["probability"],
                "min_percentage":       part["min_percentage"],
                "max_percentage":       part["max_percentage"],
                "quality_scale":        part["quality_scale"],
            })
    for ore_name in ore_deposit_index:
        ore_deposit_index[ore_name].sort(
            key=lambda x: (-x["probability"], x["deposit_name"])
        )
    write_json(OUTPUT_DIR / "ores_in_deposits.json", dict(sorted(ore_deposit_index.items())))

    # 5. locations.json
    write_json(OUTPUT_DIR / "locations.json", locations)

    # 6. ores_by_location.json
    ores_by_location = build_ores_by_location(locations)
    write_json(OUTPUT_DIR / "ores_by_location.json", ores_by_location)

    print("\nExtraction complete.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Extract mineable ore data from Star Citizen mining XML files.

Generates four JSON output files:
  - ores.json               : all ore/element definitions
  - deposits.json           : all rock/deposit compositions with resolved ore names
  - deposits_by_category.json : deposits grouped by category (asteroid, surface, fps, etc.)
  - ores_in_deposits.json   : inverted index — for each ore, every deposit that contains it
"""

import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import defaultdict


BASE_DIR = Path(__file__).parent / "input" / "Data" / "Libs" / "Foundry" / "Records" / "mining"
OUTPUT_DIR = Path(__file__).parent / "output"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag_suffix(tag: str) -> str:
    """Return the part after the first dot: 'MineableElement.Iron_Ore' → 'Iron_Ore'."""
    return tag.split(".", 1)[1] if "." in tag else tag


def _localization_to_display(key: str) -> str:
    """
    Convert a localization key to a human-readable name.
    '@hud_mining_asteroid_name_4'   → 'Asteroid Name 4'
    '@items_commodities_aluminum_ore' → 'Aluminum Ore'
    """
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


def _i(value, default=0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Step 1 — parse all MineableElement files → UUID lookup table
# ---------------------------------------------------------------------------

def load_ore_elements(elements_dir: Path) -> dict:
    """
    Returns { uuid: ore_dict } for every non-template MineableElement XML.
    """
    ores = {}

    for xml_file in sorted(elements_dir.glob("*.xml")):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as exc:
            print(f"  [WARN] Could not parse {xml_file.name}: {exc}")
            continue

        if root.get("__type") != "MineableElement":
            continue

        ref = root.get("__ref")
        if not ref:
            continue

        ore_name = _tag_suffix(root.tag)

        # Skip template/placeholder entries
        if "template" in ore_name.lower():
            continue

        ores[ref] = {
            "id": ref,
            "name": ore_name,
            "display_name": ore_name.replace("_", " ").title(),
            "resource_type": root.get("resourceType", ""),
            "instability": _f(root.get("elementInstability")),
            "resistance": _f(root.get("elementResistance")),
            "optimal_window_midpoint": _f(root.get("elementOptimalWindowMidpoint")),
            "optimal_window_midpoint_randomness": _f(root.get("elementOptimalWindowMidpointRandomness")),
            "optimal_window_thinness": _f(root.get("elementOptimalWindowThinness")),
            "explosion_multiplier": _f(root.get("elementExplosionMultiplier")),
            "cluster_factor": _f(root.get("elementClusterFactor")),
            "source_file": xml_file.name,
        }

    return ores


# ---------------------------------------------------------------------------
# Step 2 — parse all MineableComposition files → deposit list
# ---------------------------------------------------------------------------

def _category(xml_path: Path, presets_dir: Path) -> str:
    """Infer deposit category from directory and filename."""
    rel = xml_path.relative_to(presets_dir)
    parts_lower = [p.lower() for p in rel.parts]

    if "surfaceshipmining" in parts_lower:
        return "surface_ship"
    if "asteroidshipmining" in parts_lower:
        return "asteroid_ship"

    stem = xml_path.stem.lower()
    if stem.startswith("fps_") or "fps" in stem:
        return "fps"
    if stem.startswith("asteroid_"):
        return "asteroid"
    if stem.endswith("deposit"):
        return "surface"
    if "test" in stem:
        return "test"
    return "other"


def _rarity(stem: str) -> str | None:
    s = stem.lower()
    for tier in ("legendary", "epic", "rare", "uncommon", "common"):
        if tier in s:
            return tier
    return None


def load_compositions(presets_dir: Path, ores_by_id: dict) -> list:
    """
    Returns a list of deposit dicts, each containing a resolved composition array.
    """
    deposits = []
    unknown_refs = set()

    for xml_file in sorted(presets_dir.rglob("*.xml")):
        try:
            root = ET.parse(xml_file).getroot()
        except ET.ParseError as exc:
            print(f"  [WARN] Could not parse {xml_file.name}: {exc}")
            continue

        if root.get("__type") != "MineableComposition":
            continue

        composition_name = _tag_suffix(root.tag)
        if "template" in composition_name.lower():
            continue

        deposit_key = root.get("depositName", "")
        category = _category(xml_file, presets_dir)
        rarity = _rarity(xml_file.stem)

        # Build composition list
        composition = []
        array_node = root.find("compositionArray")
        if array_node is not None:
            for part in array_node.findall("MineableCompositionPart"):
                eid = part.get("mineableElement", "")
                ore = ores_by_id.get(eid)
                if ore is None:
                    unknown_refs.add(eid)

                composition.append({
                    "ore_id": eid,
                    "ore_name": ore["name"] if ore else f"unknown_{eid[:8]}",
                    "ore_display_name": ore["display_name"] if ore else f"Unknown ({eid[:8]})",
                    "probability": _f(part.get("probability")),
                    "min_percentage": _f(part.get("minPercentage")),
                    "max_percentage": _f(part.get("maxPercentage")),
                    "quality_scale": _f(part.get("qualityScale")),
                    "curve_exponent": _f(part.get("curveExponent")),
                })

        deposit: dict = {
            "id": root.get("__ref", ""),
            "name": composition_name,
            "display_name": _localization_to_display(deposit_key),
            "deposit_name_key": deposit_key,
            "category": category,
            "minimum_distinct_elements": _i(root.get("minimumDistinctElements")),
            "source_file": str(xml_file.relative_to(presets_dir.parent)),
            "composition": composition,
        }
        if rarity:
            deposit["rarity"] = rarity

        deposits.append(deposit)

    if unknown_refs:
        print(f"  [INFO] {len(unknown_refs)} ore UUIDs referenced in compositions "
              f"but not found in mineableelements (likely template/waste entries).")

    return deposits


# ---------------------------------------------------------------------------
# Step 3 — write output JSON files
# ---------------------------------------------------------------------------

def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"  Written: {path.relative_to(path.parent.parent)}  "
          f"({len(data) if isinstance(data, (list, dict)) else '—'} entries)")


def main() -> None:
    elements_dir = BASE_DIR / "mineableelements"
    presets_dir = BASE_DIR / "rockcompositionpresets"

    # Validate input paths
    for p in (elements_dir, presets_dir):
        if not p.is_dir():
            raise SystemExit(f"[ERROR] Directory not found: {p}")

    # --- Load source data ---
    print("Loading ore element definitions…")
    ores_by_id = load_ore_elements(elements_dir)
    print(f"  {len(ores_by_id)} ore elements loaded.\n")

    print("Loading rock composition presets…")
    deposits = load_compositions(presets_dir, ores_by_id)
    print(f"  {len(deposits)} deposits loaded.\n")

    # --- Build outputs ---
    print("Writing output files…")

    # 1. ores.json — sorted alphabetically by name
    ores_list = sorted(ores_by_id.values(), key=lambda x: x["name"].lower())
    write_json(OUTPUT_DIR / "ores.json", ores_list)

    # 2. deposits.json — sorted by category then name
    deposits_sorted = sorted(deposits, key=lambda d: (d["category"], d["name"].lower()))
    write_json(OUTPUT_DIR / "deposits.json", deposits_sorted)

    # 3. deposits_by_category.json — {category: [deposit, …]}
    by_cat: dict = defaultdict(list)
    for d in deposits_sorted:
        by_cat[d["category"]].append(d)
    write_json(OUTPUT_DIR / "deposits_by_category.json", dict(sorted(by_cat.items())))

    # 4. ores_in_deposits.json — inverted index: {ore_name: [{deposit info, probability, …}]}
    #    Each entry in the list = one composition part (same ore can appear twice in a deposit
    #    with different quality_scale tiers, so we keep them separate).
    ore_index: dict = defaultdict(list)
    for dep in deposits_sorted:
        for part in dep["composition"]:
            ore_index[part["ore_name"]].append({
                "deposit_name": dep["name"],
                "deposit_display_name": dep["display_name"],
                "deposit_id": dep["id"],
                "category": dep["category"],
                "rarity": dep.get("rarity"),
                "probability": part["probability"],
                "min_percentage": part["min_percentage"],
                "max_percentage": part["max_percentage"],
                "quality_scale": part["quality_scale"],
            })
    # Sort each ore's entries by probability descending, then by deposit name
    for ore_name in ore_index:
        ore_index[ore_name].sort(key=lambda x: (-x["probability"], x["deposit_name"]))
    write_json(OUTPUT_DIR / "ores_in_deposits.json", dict(sorted(ore_index.items())))

    print("\nExtraction complete.")


if __name__ == "__main__":
    main()

# SC Mining Extractor

Extracts mineable ore data from Star Citizen game files and generates JSON datasets with deposit compositions, ore probabilities, percentage ranges, quality scales, and spawn locations across all systems.

---

## Prerequisites

- Python 3.10+
- A Star Citizen installation
- [sc-data-extractor](https://github.com/dolkensp/unp4k) (or any tool capable of unpacking `.p4k` files), such as **unp4k**

---

## Step 1 — Extract files from Data.p4k

Star Citizen stores all game data in a single archive called `Data.p4k`, located in your installation directory under `StarCitizen/LIVE/`.

You need to extract files from it. The recommended tool is **unp4k**.

### Using unp4k

1. Download the latest release of [unp4k](https://github.com/dolkensp/unp4k/releases).

2. **Option A — Extract everything** (may take a long time and requires ~50 GB of free disk space):

   ```
   unp4k /path/to/StarCitizen/LIVE/Data.p4k -o /path/to/extract
   ```

3. **Option B — Extract only the files needed by this script** (fast, a few hundred MB):

   ```
   unp4k /path/to/StarCitizen/LIVE/Data.p4k "Data/Libs/Foundry/Records/mining/*" -o /path/to/extract
   unp4k /path/to/StarCitizen/LIVE/Data.p4k "Data/Libs/Foundry/Records/harvestable/*" -o /path/to/extract
   unp4k /path/to/StarCitizen/LIVE/Data.p4k "Data/Libs/Foundry/Records/entities/mineable/*" -o /path/to/extract
   ```

4. After extraction you should have a folder structure like:

   ```
   /path/to/extract/
   └── Data/
       └── Libs/
           └── Foundry/
               └── Records/
                   ├── mining/
                   │   ├── mineableelements/
                   │   └── rockcompositionpresets/
                   │       ├── surfaceshipmining/
                   │       └── asteroidshipmining/
                   ├── harvestable/
                   │   ├── harvestablepresets/
                   │   └── providerpresets/
                   │       └── system/
                   │           ├── stanton/
                   │           ├── pyro/
                   │           └── nyx/
                   └── entities/
                       └── mineable/
   ```

---

## Step 2 — Move the Data folder into the input folder

Move or copy the extracted `Data/` folder into the `input/` directory of this project:

```bash
mv /path/to/extract/Data /path/to/sc-mining-extractor/input/
```

The script expects files at exactly this path.

---

## Step 3 — Run the script

```bash
python3 extract_mining_data.py
```

No dependencies beyond the Python standard library are required.

### Expected output

```
Loading ore element definitions…
  43 ore elements loaded.

Loading rock composition presets…
  237 compositions loaded.

Loading mineable entity class definitions…
  266 mineable entities loaded.

Loading harvestable presets…
  571 harvestable presets loaded.

Loading and resolving location provider presets…
  45 locations with mining data loaded.

Writing output files…
  Written: output/ores.json  (43 entries)
  Written: output/deposits.json  (237 entries)
  Written: output/deposits_by_category.json  (7 entries)
  Written: output/ores_in_deposits.json  (42 entries)
  Written: output/locations.json  (45 entries)
  Written: output/ores_by_location.json  (33 entries)

Extraction complete.
```

All JSON files are written to the `output/` directory (created automatically if absent).

---

## Output files

### `ores.json`

A list of all 43 mineable ore/element definitions.

```json
[
  {
    "id": "05708bae-1cb1-4e63-bb95-ec7f4a3ef430",
    "name": "Iron_Ore",
    "display_name": "Iron Ore",
    "resource_type": "32c57a12-5de5-49b1-827a-9fd80278fbc4",
    "instability": 50.0,
    "resistance": -0.4,
    "optimal_window_midpoint": 0.6,
    "optimal_window_midpoint_randomness": 0.0,
    "optimal_window_thinness": -0.9,
    "explosion_multiplier": 20.0,
    "cluster_factor": 0.4,
    "source_file": "iron_ore.xml"
  },
  ...
]
```

| Field | Description |
|-------|-------------|
| `id` | Internal UUID used as a cross-reference key |
| `name` | Internal name as found in the XML |
| `display_name` | Human-readable name |
| `resource_type` | UUID of the associated `ResourceType` record (links to commodity data) |
| `instability` | How much the rock destabilises when this ore is hit |
| `resistance` | Mining resistance modifier |
| `optimal_window_midpoint` | Centre of the optimal extraction window (0–1) |
| `optimal_window_midpoint_randomness` | Random offset applied to the midpoint each spawn |
| `optimal_window_thinness` | Width of the optimal window — more negative = narrower |
| `explosion_multiplier` | Explosion risk factor |
| `cluster_factor` | How tightly this ore clusters within a deposit |

---

### `deposits.json`

A list of all 237 rock/deposit composition presets, sorted by category then name.

```json
[
  {
    "id": "deb46765-9070-4122-a272-082bbcab84d4",
    "name": "Asteroid_QType_Iron",
    "display_name": "Asteroid Name 4",
    "deposit_name_key": "@hud_mining_asteroid_name_4",
    "category": "asteroid",
    "rarity": null,
    "minimum_distinct_elements": 3,
    "source_file": "rockcompositionpresets/asteroid_qtype_iron.xml",
    "composition": [
      {
        "ore_id": "05708bae-1cb1-4e63-bb95-ec7f4a3ef430",
        "ore_name": "Iron_Ore",
        "ore_display_name": "Iron Ore",
        "probability": 1.0,
        "min_percentage": 30.0,
        "max_percentage": 70.0,
        "quality_scale": 1.0,
        "curve_exponent": 1.0
      },
      ...
    ]
  },
  ...
]
```

| Field | Description |
|-------|-------------|
| `category` | Deposit context — see categories table below |
| `rarity` | `common` / `uncommon` / `rare` / `epic` / `legendary` (ship-mining presets only; `null` for others) |
| `minimum_distinct_elements` | Minimum number of different ores that must be present |
| `composition[].probability` | Probability (0–1) that this ore appears at all in a given rock |
| `composition[].min_percentage` | Minimum percentage this ore contributes to the deposit |
| `composition[].max_percentage` | Maximum percentage this ore contributes to the deposit |
| `composition[].quality_scale` | Quality multiplier for extracted ore (1.0 = full quality, 0.49 = ~half) |
| `composition[].curve_exponent` | Distribution curve exponent for percentage rolls |

**Deposit categories:**

| Category | Count | Description |
|----------|-------|-------------|
| `asteroid` | 70 | Generic asteroid composition presets (used by asteroid-type rocks) |
| `asteroid_ship` | 27 | Ship-mined asteroid deposits — have rarity tiers |
| `surface` | 12 | Generic planetary surface deposits |
| `surface_ship` | 26 | Ship-mined surface deposits — have rarity tiers |
| `fps` | 12 | FPS hand-mining deposits |
| `vehicle` | 8 | Ground vehicle mining deposits |
| `test` | 17 | Internal test/balance compositions |
| `other` | 65 | Ore-specific surface deposit variants |

**Note on duplicate ore entries:** Some deposits list the same ore twice with different `quality_scale` values. This is intentional — it represents a high-quality fraction (e.g. `quality_scale: 1.0`, 2–7%) and a bulk lower-quality fraction (e.g. `quality_scale: 0.49`, 39–83%) of the same material in one rock.

---

### `deposits_by_category.json`

The same deposit data as `deposits.json`, restructured as an object keyed by category:

```json
{
  "asteroid": [ ... ],
  "asteroid_ship": [ ... ],
  "fps": [ ... ],
  "other": [ ... ],
  "surface": [ ... ],
  "surface_ship": [ ... ],
  "test": [ ... ]
}
```

Useful for filtering to a specific mining context without post-processing.

---

### `ores_in_deposits.json`

Inverted index: for each ore, every deposit that contains it, sorted by probability descending.

```json
{
  "Savrilium_Ore": [
    {
      "deposit_name": "LegendaryShipMineablesAsteroid_Savrilium",
      "deposit_display_name": "Savrilium Ore",
      "deposit_id": "3375ee93-f695-40d2-b86c-1ad23802e59b",
      "category": "asteroid_ship",
      "rarity": "legendary",
      "probability": 1.0,
      "min_percentage": 2.82,
      "max_percentage": 6.82,
      "quality_scale": 1.0
    },
    ...
  ],
  ...
}
```

Answers: "which deposit types can contain ore X, and in what quantities?"

---

### `locations.json` *(new)*

A list of 45 locations (planets, moons, asteroid fields) across the Stanton, Pyro, and Nyx systems. Each location contains its mining groups fully resolved down to ore compositions.

```json
[
  {
    "id": "230aecd3-2e5b-4d58-a884-bbba59a40cf7",
    "name": "Keeger Belt (Nyx)",
    "system": "Nyx",
    "body": "Keeger Belt",
    "zone_type": "asteroid_field",
    "source_file": "providerpresets/system/nyx/asteroidfield/hpp_nyx_keegerbelt.xml",
    "groups": [
      {
        "group_name": "SpaceShip_Mineables",
        "mining_mode": "ship",
        "group_probability": 0.1,
        "total_relative_probability": 100.0,
        "items": [
          {
            "relative_probability": 28.5,
            "normalized_probability": 0.285,
            "preset_name": "Mining_AsteroidUncommon_Torite",
            "respawn_time_s": 3600,
            "despawn_time_s": 600,
            "scale_min": 0.6,
            "scale_max": 1.0,
            "entity_name": "MineableRock_AsteroidUncommon_Torite",
            "laser_damage_full_value": 2500.0,
            "composition_name": "UncommonShipMineablesAsteroid_Torite",
            "composition_category": "asteroid_ship",
            "rarity": "uncommon",
            "minimum_distinct_elements": 2,
            "composition": [
              {
                "ore_name": "Torite_Ore",
                "probability": 1.0,
                "min_percentage": 2.82,
                "max_percentage": 6.82,
                "quality_scale": 1.0
              },
              ...
            ]
          },
          ...
        ]
      }
    ]
  },
  ...
]
```

**Location fields:**

| Field | Description |
|-------|-------------|
| `system` | Star system: `Stanton`, `Pyro`, or `Nyx` |
| `body` | Planet, moon, or asteroid field name |
| `zone_type` | `planet` or `asteroid_field` |
| `groups[].mining_mode` | `ship`, `fps`, `vehicle`, or `general` |
| `groups[].group_probability` | Density weight for this group type spawning at this location |
| `groups[].total_relative_probability` | Sum of all `relative_probability` values in the group (used as denominator for normalization) |
| `items[].relative_probability` | Spawn weight of this specific rock type within its group |
| `items[].normalized_probability` | `relative_probability / total_relative_probability` — share of spawns this rock type takes |
| `items[].respawn_time_s` | Seconds until the rock respawns after being mined |
| `items[].despawn_time_s` | Seconds until a mined rock's debris despawns |
| `items[].scale_min` / `scale_max` | Random scale range applied to spawned rocks |
| `items[].laser_damage_full_value` | Laser power required to deal full damage to this rock |
| `items[].rarity` | Rarity tier of the deposit (`common` … `legendary`) |

Only groups that contain at least one resolvable mineable rock are included. Non-mining harvestables (plants, salvage derelicts, etc.) are filtered out.

---

### `ores_by_location.json` *(new)*

Inverted index: for each ore, every location and group where it can spawn. Each entry represents one composition part (since the same ore can appear twice in one deposit with different quality tiers, both entries are listed separately).

```json
{
  "Savrilium_Ore": [
    {
      "location_id": "e9aa8f98-4c87-468f-ae03-10a96d9497e5",
      "location_name": "Glaciem Ring (Nyx)",
      "system": "Nyx",
      "body": "Glaciem Ring",
      "zone_type": "asteroid_field",
      "mining_mode": "ship",
      "group_name": "SpaceShip_Mineables",
      "group_probability": 0.1,
      "relative_probability": 2.0,
      "normalized_probability": 0.02,
      "preset_name": "Mining_AsteroidLegendary_Savrilium",
      "entity_name": "MineableRock_AsteroidLegendary_Savrilium",
      "composition_name": "LegendaryShipMineablesAsteroid_Savrilium",
      "composition_category": "asteroid_ship",
      "rarity": "legendary",
      "respawn_time_s": 3600,
      "scale_min": 0.6,
      "scale_max": 1.0,
      "ore_probability": 1.0,
      "ore_min_percentage": 2.82,
      "ore_max_percentage": 6.82,
      "ore_quality_scale": 1.0
    },
    ...
  ],
  ...
}
```

Answers: "where in the game can I find ore X, with what spawn weight, and in what concentration?"

Entries are sorted by system → body → group probability descending.

---

## Data pipeline

The script resolves a five-level chain from location down to raw ore:

```
HarvestableProviderPreset  (location file)
  └─ HarvestableElement.harvestable UUID
       └─ HarvestablePreset.entityClass UUID
            └─ EntityClassDefinition (MineableParams.composition UUID)
                 └─ MineableComposition
                      └─ MineableCompositionPart.mineableElement UUID
                           └─ MineableElement  (ore properties)
```

---

## Project structure

```
sc-mining-extractor/
├── extract_mining_data.py     # extraction script
├── input/
│   └── Data/                  # extracted game files go here
│       └── Libs/Foundry/Records/
│           ├── mining/
│           │   ├── mineableelements/
│           │   └── rockcompositionpresets/
│           ├── harvestable/
│           │   ├── harvestablepresets/
│           │   └── providerpresets/system/
│           └── entities/mineable/
└── output/                    # generated JSON files (created on first run)
    ├── ores.json
    ├── deposits.json
    ├── deposits_by_category.json
    ├── ores_in_deposits.json
    ├── locations.json
    └── ores_by_location.json
```

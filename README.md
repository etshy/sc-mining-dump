# SC Mining Extractor

Extracts mineable ore data from Star Citizen game files and generates JSON datasets with deposit compositions, ore probabilities, percentage ranges, and quality scales.

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

   This extracts the full archive into a `Data/` folder at the output path.

3. **Option B — Extract only mining data** (fast, a few MB):

   Use a filter to extract only the files needed by this script:

   ```
   unp4k /path/to/StarCitizen/LIVE/Data.p4k "Data/Libs/Foundry/Records/mining/*" -o /path/to/extract
   ```

   This creates a `Data/` folder containing only the mining XML files.

4. After extraction you should have a folder structure like:

   ```
   /path/to/extract/
   └── Data/
       └── Libs/
           └── Foundry/
               └── Records/
                   └── mining/
                       ├── mineableelements/
                       ├── rockcompositionpresets/
                       │   ├── surfaceshipmining/
                       │   └── asteroidshipmining/
                       ├── miningglobalparams.xml
                       └── ...
   ```

---

## Step 2 — Move the Data folder into the input folder

Move or copy the extracted `Data/` folder into the `input/` directory of this project:

```
sc-mining-extractor/
└── input/
    └── Data/                  ← place it here
        └── Libs/
            └── Foundry/
                └── Records/
                    └── mining/
                        ├── mineableelements/
                        ├── rockcompositionpresets/
                        └── ...
```

```bash
mv /path/to/extract/Data /path/to/sc-mining-extractor/input/
```

The script expects to find files at exactly this path. If your extraction produced a different directory layout, adjust accordingly.

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
  237 deposits loaded.

Writing output files…
  Written: output/ores.json  (43 entries)
  Written: output/deposits.json  (237 entries)
  Written: output/deposits_by_category.json  (7 entries)
  Written: output/ores_in_deposits.json  (42 entries)

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
| `instability` | How much the rock destabilises when this ore is hit |
| `resistance` | Mining resistance modifier |
| `optimal_window_midpoint` | Centre of the optimal extraction window (0–1) |
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
| `rarity` | `common` / `uncommon` / `rare` / `epic` / `legendary` (ship mining only) |
| `minimum_distinct_elements` | Minimum number of different ores that must be present |
| `composition[].probability` | Probability (0–1) that this ore appears at all in a given rock |
| `composition[].min_percentage` | Minimum percentage of this ore in the deposit |
| `composition[].max_percentage` | Maximum percentage of this ore in the deposit |
| `composition[].quality_scale` | Quality multiplier for extracted ore (1.0 = full quality, 0.49 = ~half) |

**Deposit categories:**

| Category | Count | Description |
|----------|-------|-------------|
| `asteroid` | 70 | Generic asteroid composition presets |
| `asteroid_ship` | 27 | Ship-mined asteroid deposits (with rarity tiers) |
| `surface` | 12 | Generic planetary surface deposits |
| `surface_ship` | 26 | Ship-mined surface deposits (with rarity tiers) |
| `fps` | 12 | FPS hand-mining deposits |
| `test` | 17 | Internal test/balance compositions |
| `other` | 73 | Ore-specific surface deposit variants |

**Note on duplicate ore entries:** Some deposits list the same ore twice with different `quality_scale` values. This is intentional — it represents a high-quality fraction (e.g. `quality_scale: 1.0`, 2–7%) and a bulk lower-quality fraction (e.g. `quality_scale: 0.49`, 39–83%) of the same material within one rock.

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
  "Quantainium_Raw": [
    {
      "deposit_name": "LegendaryShipMineablesAsteroid_Quantainium",
      "deposit_display_name": "Quantainium Raw",
      "deposit_id": "...",
      "category": "asteroid_ship",
      "rarity": "legendary",
      "probability": 1.0,
      "min_percentage": 2.8,
      "max_percentage": 6.8,
      "quality_scale": 1.0
    },
    ...
  ],
  ...
}
```

Useful for answering "which deposits can I find ore X in, and how likely is it?"

---

## Project structure

```
sc-mining-extractor/
├── extract_mining_data.py     # extraction script
├── input/
│   └── Data/                  # extracted game files go here
│       └── Libs/Foundry/Records/mining/
│           ├── mineableelements/
│           └── rockcompositionpresets/
└── output/                    # generated JSON files (created on first run)
    ├── ores.json
    ├── deposits.json
    ├── deposits_by_category.json
    └── ores_in_deposits.json
```

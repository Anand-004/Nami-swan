# Nami-swan Quick Reference Guide

## Project Overview
**Nami-swan** is a production-grade ship voyage route optimization engine that computes the safest and most economically efficient maritime route between ports.

---

## Prerequisites
- Python 3.10+
- Internet connection (for dependencies)

---

## Installation

### Navigate to Project
```bash
cd D:\Projects\Python\nami
```

### Install Dependencies (One-Time)
```bash
python -m pip install -r requirements.txt
```

**Dependencies installed:**
- numpy, pandas, networkx
- shapely, geopandas
- pyyaml, scipy, pytest

---

## Running the Optimizer

### Basic Command
```bash
python -m src.main --voyage data/inputs/voyage_request.json
```

### With Verbose Logging
```bash
python -m src.main --voyage data/inputs/voyage_request.json -v
```

### Full Command (All Options)
```bash
python -m src.main \
    --config config/penalties.yaml \
    --vessel config/vessel_specs.json \
    --voyage data/inputs/voyage_request.json \
    --zones data/static/restricted_zones.geojson \
    --weather data/weather/sample_forecast.json \
    --output data/outputs/optimized_route.csv \
    --grid-resolution 0.5 \
    -v
```

---

## Command Line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--config` | `config/penalties.yaml` | Cost/penalty YAML config |
| `--vessel` | `config/vessel_specs.json` | Vessel mechanical specs |
| `--voyage` | *(required)* | Voyage request JSON |
| `--zones` | `data/static/restricted_zones.geojson` | Restricted zone polygons |
| `--weather` | `data/weather/sample_forecast.json` | Weather forecast grid |
| `--output` | `data/outputs/optimized_route.csv` | Output CSV path |
| `--grid-resolution` | `0.5` | Grid spacing in degrees |
| `-v, --verbose` | off | Enable debug logging |

---

## Viewing Output

### View First 20 Lines
```bash
head -20 data/outputs/optimized_route.csv
```

### View Last 10 Lines
```bash
tail -10 data/outputs/optimized_route.csv
```

### View Full File
```bash
cat data/outputs/optimized_route.csv
```

### Open in Excel/Spreadsheet
```bash
# Windows
start data/outputs/optimized_route.csv

# Or manually open the file in Excel
```

---

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/test_physics.py -v
python -m pytest tests/test_optimizer.py -v
python -m pytest tests/test_formatter.py -v
```

### Run Tests with Coverage
```bash
python -m pytest tests/ -v --cov=src
```

---

## Customizing Your Voyage

### Edit Voyage Request
```bash
notepad data/inputs/voyage_request.json
# Or use any text editor
```

**Example voyage_request.json:**
```json
{
  "voyage_id": "VOY-2026-0801",
  "origin": {
    "name": "Port of Singapore",
    "lat": 1.2902,
    "lon": 103.8519
  },
  "destination": {
    "name": "Port of Colombo",
    "lat": 6.9271,
    "lon": 79.8612
  },
  "departure_time": "2026-09-01T06:00:00Z",
  "required_arrival_deadline": "2026-09-06T18:00:00Z"
}
```

### Edit Cost/Penalty Configuration
```bash
notepad config/penalties.yaml
```

### Edit Vessel Specifications
```bash
notepad config/vessel_specs.json
```

---

## Expected Output

### Console Output
```
============================================================
  Nami-swan: Ship Voyage Route Optimization Engine
============================================================
Loading configuration and data...
Vessel: CARGO-778 (Handymax Bulk Carrier)
Voyage: Port of Singapore -> Port of Colombo
Departure: 2026-09-01 06:00:00+00:00
Deadline:  2026-09-06 18:00:00+00:00
Building ocean navigation grid (0.50° resolution)...
Grid built in 0.02s — 846 navigable nodes
Running A* route optimisation...
Optimisation completed in 0.37s
------------------------------------------------------------
VOYAGE SUMMARY
------------------------------------------------------------
  Waypoints:      73
  Total fuel:     217.10 MT
  Total CO2:      676.05 MT
  Total cost:     $1,340,882.04
  Duration:       151.0 hours
  On-time:        NO ✗
  Output:         data\outputs\optimized_route.csv
============================================================
```

### CSV Output Format
```csv
waypoint_name,latitude,longitude,date,time,speed_knots,fuel_burn_mt,co2_mt,segment_cost
WP000_DEPART,1.2902,103.8519,01/09/2026,06:00:55,0.00,0.0000,0.0000,0.00
WP001,1.5000,102.0000,01/09/2026,09:15:55,12.50,1.2340,3.8403,1456.78
...
```

**CSV Format Specifications:**
- Coordinates: 4 decimal places
- Date: `DD/MM/YYYY`
- Time: `HH:MM:55` (fixed seconds at :55)
- Waypoint intervals: 1 minute to 3 hours
- No duplicate consecutive waypoints

---

## Quick Command Reference

| Action | Command |
|--------|---------|
| **Run optimizer** | `python -m src.main --voyage data/inputs/voyage_request.json` |
| **Run with logs** | `python -m src.main --voyage data/inputs/voyage_request.json -v` |
| **Run tests** | `python -m pytest tests/ -v` |
| **View output** | `cat data/outputs/optimized_route.csv` |
| **View help** | `python -m src.main --help` |
| **Install deps** | `python -m pip install -r requirements.txt` |

---

## Troubleshooting

### Module Not Found Error
```bash
# Reinstall dependencies
python -m pip install -r requirements.txt
```

### Permission Denied
```bash
# Run as administrator or check file permissions
```

### Invalid Voyage JSON
```bash
# Validate JSON syntax at https://jsonlint.com/
# Or use:
python -c "import json; print(json.load(open('data/inputs/voyage_request.json')))"
```

### Grid Resolution Too Fine (Slow Performance)
```bash
# Use larger grid resolution (default is 0.5)
python -m src.main --voyage data/inputs/voyage_request.json --grid-resolution 1.0
```

---

## Project Structure

```
nami/
├── config/
│   ├── penalties.yaml          # Cost coefficients & emission factors
│   └── vessel_specs.json       # Vessel mechanical specifications
├── data/
│   ├── inputs/
│   │   └── voyage_request.json # Origin, destination, schedule
│   ├── static/
│   │   └── restricted_zones.geojson  # Land & restricted zones
│   ├── weather/
│   │   └── sample_forecast.json      # Weather forecast grid
│   └── outputs/
│       └── optimized_route.csv       # Generated route (output)
├── src/
│   ├── main.py                 # CLI entry point
│   ├── models.py               # Data models
│   ├── data_loader.py          # JSON/YAML ingestion
│   ├── grid_builder.py         # Spatial grid builder
│   ├── physics_engine.py       # Fuel/CO2 calculations
│   ├── cost_engine.py          # Cost function
│   ├── optimizer.py            # A* pathfinding
│   └── output_formatter.py     # CSV generator
├── tests/
│   ├── test_physics.py
│   ├── test_optimizer.py
│   └── test_formatter.py
├── requirements.txt
├── README.md
└── QUICK_REFERENCE.md          # This file
```

---

## Cost Model

$$\text{Total Cost} = C_{\text{fuel}} + C_{\text{CO}_2} + C_{\text{ops}} + C_{\text{delay}} + C_{\text{weather risk}}$$

**Components:**
- **Fuel Cost**: `fuel_burned × fuel_price_per_mt`
- **CO₂ Cost**: `fuel_burned × emission_factor × co2_cost_per_mt`
- **Operations**: `segment_hours × operational_hourly_rate`
- **Delay Penalty**: `hours_past_deadline × delay_penalty_hourly`
- **Weather Risk**: Penalties for Hs > 4m, gale winds, storm proximity

---

## Support & Documentation

- **Full README**: `README.md`
- **Validation Summary**: `VALIDATION_SUMMARY.md`
- **Requirements PDF**: `Ship Voyage Route Optimization Understanding.pdf`

---

**Project Status**: ✅ Production Ready | All 39 Tests Passing
**Last Updated**: 2026-09-29

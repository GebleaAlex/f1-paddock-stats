# Data licences

This folder is where the pipeline keeps its data: `raw/` (downloaded sources), `timing/` (2018+ timing extracted by
`paddock timing`) and the built `paddock-*.duckdb` files. None of it is committed. The code in this repository is under
the Apache License 2.0 (see `LICENSE` and `NOTICE`); the data keeps the licences of its sources.

| Data | Source | Licence | What that means here |
| --- | --- | --- | --- |
| Results, qualifying, grids, standings, entrants, chassis, engines, tyres, circuits, circuit layouts (1950+) | [f1db](https://github.com/f1db/f1db) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Free to reuse, including commercially, with credit to f1db |
| Lap-by-lap times and positions (1996+) | [Jolpica-F1](https://github.com/jolpica/jolpica-f1) database dump | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Non-commercial use only, with credit, and anything shared from it under the same licence |
| Laps with tyres and sectors, track status, race control messages, weather and fastest-lap telemetry (2018+) | Formula 1 live timing, read with [FastF1](https://github.com/theOehrly/Fast-F1) | No licence; copyright Formula One World Championship Limited | Used for charts and summaries on the site. Never redistributed: no downloads, no bulk API, no database dumps |

The built database mixes all three, so it is for running this site and must not be published as a file. The
derived tables `teammate_race`, `retirement_reason` and `driver_rating` are calculated from f1db data only.

Formula 1 timing data and trade marks belong to the Formula 1 companies. This project is unofficial and
non-commercial. If a rights holder asks us to remove something, we will.

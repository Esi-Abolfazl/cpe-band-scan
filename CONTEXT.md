# cpe-band-scan — domain glossary

The closed vocabulary (`llm-09`). Code, copy keys, file names and docs use only these terms.
Introducing, renaming or retiring a term updates this file in the **same change**. Alphabetical.

| Term | Meaning (one sentence) | Code identifier | _Avoid_ |
| --- | --- | --- | --- |
| Anchor | The band the router is attached to on a side; other carriers ride on it. | first element of the `lte`/`nr` tuple in `lockfreq.lock` | primary, PCell |
| Auto row | The reference measurement taken with no lock, competing in the ranking like a band. | `"auto"` (`scanner.py:25`) | baseline, default row |
| Band | One LTE (`B7`) or NR (`N78`) frequency band, spelled with its letter and number. | `bands_of`, `band_info` (`lockfreq.py`) | channel, frequency |
| Copy | Every sentence a person reads, in one catalogue for page and terminal. | `copy.py` groups `APP`, `FIELDS`, `ACTIONS`, `COLUMNS`, `ERRORS`, `NOTES`, `PROGRESS` | strings, i18n, labels file |
| Device | The router's identity as probed: model, firmware, carrier, whether it can lock bands. | `Device`, `probe` (`device.py`) | modem, box |
| Home | The folder on this computer that holds runs, profiles and settings. | `store.home()`, `CPE_BAND_SCAN_HOME` | data dir, config dir |
| Job | The one background task a session runs at a time: a scan or a test. | `Session.kind` (`server.py:66`) | task, worker |
| Lock | The set of bands the router is told to use, per side, with optional secondary carriers. | `lockfreq.lock`, `read_lock` | band selection, pin |
| Measurement | One band's summary over its samples: lowest, typical, channel, strength, 5G kept. | `metrics.measure`, `summarise` | reading, stats |
| Profile | A named lock saved on this computer for one carrier or place. | `store.profiles` | preset, bookmark |
| Rating | The grade a measurement earns: excellent, good, fair, poor, no5g. | `metrics.grade`, `copy.GRADES` | score, verdict |
| Route | One `/api` path, named once in the route table; server, page and tests use the name. | `api.ROUTES[name]`, `routes.<name>` in the page | endpoint, URL, path literal |
| Router | The Huawei CPE reached over its LAN admin API; the only door to it is one class. | `Router` (`router.py:46`) | modem, gateway, device |
| RouterError code | The `snake_case` key naming one failure, and the key of its sentence in copy. | `RouterError.code`, `copy.ERRORS` | error message, exception text |
| Run | One finished scan: sets, results, order, verdict; saved as one JSON file. | `store.runs_dir`, `RUN_ID` | scan result, report |
| Sample | One reading of the router's signal line at one instant. | `metrics.sample` | poll, tick |
| Scan | Lock each band in turn, measure it, rank, then apply the best. | `scanner.scan` | sweep, survey |
| Secondary carrier | A band allowed to aggregate onto the anchor but never to be the anchor. | `lte_scell`, `nr_scell` (`lockfreq.lock`) | SCell, CA band |
| Session | The one connected router and its one job, held in memory by the page server. | `Session` (`server.py:56`) | state, context |
| Set | The group of bands locked together for one measurement; the auto row is the empty set. | `sets`, `set_result` (`scanner.py`) | combo, config |
| Side | The 4G (`lte`) or 5G (`nr`) network, scanned and shown separately. | `"lte"`, `"nr"`, `copy.SIDES` | RAT, mode, network type |
| Speed probe | Five pings and a five-second download through the router after a band's samples. | `SpeedProbe` (`speed.py:233`) | speed test, benchmark |
| Test | A timed trace of one lock, sampled every 10 s, ending in lowest/typical/best. | `scanner.trace`, `copy.SIDES["trace"]` | monitor, watch |
| Verdict | Which of four VPN situations the speed probe measured in. | `speed.verdict` | vpn status, bypass flag |

## Naming conventions derived from the glossary

- A module is named after the noun it owns (`store.py`, `device.py`); a function after the verb
  the product uses (`scan`, `probe`, `lock`).
- Routes are `/api/<verb-or-noun>` in the product's words (`/api/scan`, `/api/profiles`).
- Copy keys are `snake_case` of the glossary term (`auto_row`, `password_note`).

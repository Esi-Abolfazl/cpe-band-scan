# Huawei CPE band control: what each firmware actually accepts

Found by reading the router's own web UI code (`js/main.js`, developer-mode chunk `js/lockband.js`,
auth-gated) on an H155-381 running 4.0.0.5, and by watching what the router did with each write.

## Driver table

Select by the probe, not the name, not the version and not a feature switch: a successful
`net/lock-freq` read is the capability. Everything else is a proxy that was read off one device —
`SoftwareVersion` starting `4.` refuses the `10.x` line (`10.0.5.2(H1SP9C43)`, N5368X 5G CPE Max,
2026-09-18) and `lock_freq_switch == 3` is what the H155's firmware reports, not a constant. Both
still go in the refusal text, so a report names the model, the firmware and the switch value.

| Device / firmware | Read | Write | Notes |
|---|---|---|---|
| H155-381, H155-181, H153, H158 on **4.x and 10.x** (Vue web UI, `WEBUI 4.0`) | `api/net/lock-freq` | `api/net/lock-freq` | LTE and NR. `api/net/net-mode` accepts only `NetworkMode` + `networkOption`/`LTEBandOption`; an `LTEBand` field makes it answer `-1` **after** applying the mode part. |
| B525, B818, B535, H112-370, H122-373 on **3.x/2.x** (jQuery web UI) | `api/net/net-mode` | `api/net/net-mode` with `<NetworkMode>00</NetworkMode><NetworkBand>3FFFFFFF</NetworkBand><LTEBand>hex</LTEBand>` | Classic path used by huawei-lte-api `set_net_mode` and the community userscripts. No NR lock. |
| Anything else | `api/device/information` first | none | Stop and show the user the device/firmware line. |

The driver itself lives in `src/cpe_band_scan/device.py` in this repository; this table is the
reasoning behind it, not a second implementation. A new firmware family means a new driver module
there and a new row here.

## `api/net/lock-freq` (the 4.x and 10.x web UI)

Requires login. Body is XML under `<request>`; huawei-lte-api's `post_set` builds it from an
OrderedDict. `lock_mode`: `0` none, `3` band, `1` frequency (`band`+`freq`), `2` cell (`band`+`freq`+`pci`).

```xml
<request>
  <lte_info>
    <lock_mode>3</lock_mode>
    <freq_infos><freq_info><band>7</band></freq_info></freq_infos>   <!-- Pcell+Scell bands -->
    <all_bands>3,7</all_bands>                                         <!-- + Scell-only bands -->
  </lte_info>
  <nr_info><lock_mode>0</lock_mode><freq_infos></freq_infos><all_bands></all_bands></nr_info>
</request>
```

The UI drops `nr_info` when `NetworkMode` is `03` (4G only) and `lte_info` when it is `08` (5G SA only).
Error `100006` = band set refused. The write can log the session out (`ERRORSTATUS`); re-login.

Useful reads: `device/signal` (band string, SINR/RSRQ/RSRP, NR equivalents), `device/nbrcellinfo`
and `device/seccellinfo` (visible cells, restricted by an active lock), `config/network/bandfreqlist.xml`
(`lte_support_band_list`, `nr_support_band_list`, EARFCN ranges), `net/net-feature-switch`
(`lock_freq_switch`: 3 on the H155's 4.x firmware, other values elsewhere — diagnostic, not a gate),
`developer/developermode-featureswitch`.

## Reading the numbers

- Anchor SINR is the stability signal. Negative = retransmissions and drops even with strong RSRP.
- RSRQ worse than -14 dB on a strong RSRP means interference or load, not distance.
- In NSA, n78 rides on the LTE anchor: fix the anchor, the 5G leg follows.
- A single band lock disables carrier aggregation across bands; `--scell` keeps them as secondaries.
- Speed (Mbit/s) and Ping (ms) are the path from this computer through the router to `speed.cloudflare.com` at that moment: width, cell load and core path in one number. They change with the hour; the radio numbers do not, which is why they never rank.
- The probe bypasses a VPN by scoping sockets to the LAN interface (`IP_BOUND_IF` / `SO_BINDTODEVICE` / `IP_UNICAST_IF`) and resolving the host through the router. Fake-IP VPNs (198.18.0.0/15 answers) make the DNS step mandatory: a scoped connect to a system-resolved name just times out (seen 2026-09-16).

## Findings from the first field run (MCI, Tehran, 2026-09-14, H155-381)

Three runs, 17 bands. On air: B1, B3, B7, B39, B40, n78. B7 anchor won every run (SINR 9, RSRQ -10);
B1 anchor (the auto choice) was the unstable one (SINR -2 to 8, RSRQ -15). B40 swung 13 → 2 dB between
runs, which is why close calls need a second run. Final: `apply 7 --scell 3`, three LTE carriers + n78. A 2-minute `test` showed B7 holding 7-10 dB while B40 swung -4 to 18 dB.

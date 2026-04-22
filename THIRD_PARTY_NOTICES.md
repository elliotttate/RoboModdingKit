# Third-Party Notices

This repo contains original scripts/docs plus a small set of redistributed third-party binaries and runtime snapshots. The repo's own scripts/docs are licensed under `LICENSE`. Third-party components keep their upstream licenses and terms.

## Redistributed Binaries

### `tooling/bin/jmap_dumper.exe`

- Upstream: `https://github.com/trumank/jmap`
- Pinned source ref: `2f2683102d44c45ad99dcfc1c80ac81380d37348`
- Upstream license: MIT
- SHA-256: `5448117830FAC39493A8190BDFB25F941584127789FCFF35405154636F7CB0B7`

### `tooling/bin/repak.exe`

- Upstream: `https://github.com/trumank/repak`
- Pinned source ref: `355b5f62f51959c7cc6dd5a51708646ef483065d`
- Upstream license: dual Apache-2.0 / MIT
- SHA-256: `42DEA8DF98979D4DB160E0B22745081BFFA0A4FDD4A597FC76FF62B0C4174A33`

### `tooling/bin/retoc.exe`

- Upstream: `https://github.com/trumank/retoc`
- Pinned source ref: `d034ade1ae8117d4786eaf6b0418d4cf48474d7f`
- Upstream license: MIT
- SHA-256: `6D914593BDF7E7FCAA918F5510F15050765F56A92D9C5F9ECBFD545602748695`

### `tooling/bin/kismet-analyzer.exe`

- Upstream: `https://github.com/trumank/kismet-analyzer`
- Pinned source ref: `e8982e99d628c92a43f2109c0f604c0d4061c6dd`
- Upstream license: MIT
- SHA-256: `15E7AD9CDE9BFD6EE86589B542E107739E77849F7357F1D359AEFB3963E2C8A7`

### UE4SS runtime snapshots and release archives

- Files:
  - `runtime/UE4SS_working_runtime/Win64/UE4SS.dll`
  - `runtime/UE4SS_patch_analysis/UE4SS_original.dll`
  - `runtime/ue4ss_release_zips/UE4SS_v3.0.1.zip`
  - `runtime/ue4ss_release_zips/UE4SS_v3.0.1-946-g265115c0.zip`
- Upstream: `https://github.com/UE4SS-RE/RE-UE4SS`
- Pinned source ref: `d935b5b23bac03b65c14ae38382b02007204cc2e`
- Upstream license: MIT
- SHA-256:
  - `runtime/UE4SS_working_runtime/Win64/UE4SS.dll`: `C397DD1019BDD33BCD81C48DF95C5BF0BC6B3C2D1E26EDFEE42ACB47C3CADB15`
  - `runtime/UE4SS_patch_analysis/UE4SS_original.dll`: `8AC18FBFFC1EF96B0662D4A2D537B3F224C26D65CAABA7989A9404C566102B26`
  - `runtime/ue4ss_release_zips/UE4SS_v3.0.1.zip`: `4B47D4BCEDDD2F561A4E395BFA00924CCFC945AF576A2D0C613E6537846C57EC`
  - `runtime/ue4ss_release_zips/UE4SS_v3.0.1-946-g265115c0.zip`: `25F71CBB41A23D256710A60A74DE819028E1FFA6E3BB9C161E3C50D5D02A7A8A`

### `runtime/UE4SS_working_runtime/Win64/dwmapi.dll`

- Upstream: `https://github.com/praydog/UEVR`
- Pinned source ref: `6f66affc01cea22e4b1b5a47986e1ade80ccbd26`
- Upstream license/terms: see the upstream `UEVR` repository `LICENSE` file (`Copyright (c) 2022-2025 praydog`, `All rights reserved.`)
- SHA-256: `CE596412BEFA68C30B7F88F65BEB77D9BDAD55E9B96A276A5A9CF690C63F24BB`

## Notes

- The optional external-source clones bootstrapped under `tooling/external_sources` are not redistributed in this repo; see `tooling/setup/external_sources.json` for the pinned refs used during validation.
- If any bundled binary snapshot changes, update this file with the new upstream ref and SHA-256 values.

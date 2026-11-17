# Bigscreen Bridge — Home Assistant integration (HACS repository)

This repository distributes the `bigscreen_bridge` custom integration through HACS.
It is a published copy. The integration is developed and tested in the Bigscreen
Bridge project (`dbus-ha-connection`), next to the TV-side bridge service it talks
to, because the two share one protocol and one test suite.

## How to change the integration

1. Make the change in `dbus-ha-connection/custom_components/bigscreen_bridge` and
   run that project's tests (`python3 -m pytest`).
2. If the bridge protocol changes, update `docs/protocol.md` there and keep the
   integration working against bridges that do not have the change yet.
3. Bump `version` in `manifest.json`.
4. Copy it here: `python3 scripts/export-hacs.py` in that project
   (`--check` reports drift without copying).
5. Commit here, tag `v<version>`, push, and publish a GitHub release for the tag.
   HACS offers releases to users; without one it installs the default branch.

Do not edit `custom_components/` in this repository directly. A direct edit is
overwritten by the next export.

## Rules for this repository

- `manifest.json` keeps `domain` and `name` first and the other keys sorted;
  hassfest fails otherwise. `documentation` and `issue_tracker` point here.
- `hacs.json` states the minimum Home Assistant version. Raise it when the
  integration starts using a newer API.
- Every user-visible string lives in both `strings.json` and
  `translations/en.json`.
- The README describes only what works today. Do not list a feature until it has
  run against a real bridge.
- Never commit a pairing token, a TV address, or any other detail of one person's
  setup. Examples use `tv.local`.
- The entities are native `MediaPlayerEntity` objects. Do not add MQTT Discovery,
  and do not add a second music player: Music Assistant owns music playback.
- Expose a media player feature only when the bridge reports the matching
  capability.

## Checks

The `Validate` workflow runs hassfest and the HACS action on every push. Both must
pass before a release.

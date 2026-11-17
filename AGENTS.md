# Bigscreen Bridge — Home Assistant integration (HACS repository)

This repository is the home of the `bigscreen_bridge` custom integration and
distributes it through HACS. The TV-side bridge service it talks to lives in the
separate `bigscreen-bridge` repository
(https://github.com/shreyasajj/bigscreen-bridge), checked out next to this one as
`../dbus-ha-connection`.

## How to change the integration

1. Edit `custom_components/bigscreen_bridge` here.
2. Run the tests from the bridge checkout: `cd ../dbus-ha-connection && python3 -m
   pytest`. They live there because they run this integration against the real
   bridge code; `BIGSCREEN_INTEGRATION` points them at another checkout of this
   repository.
3. If the bridge protocol changes, update `docs/protocol.md` in the bridge
   repository and keep the integration working against bridges without the change.
4. Bump `version` in `manifest.json`, commit, tag `v<version>`, push, and publish a
   GitHub release for the tag. HACS offers releases to users; without one it
   installs the default branch.

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

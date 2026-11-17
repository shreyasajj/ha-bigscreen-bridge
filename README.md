# Bigscreen Bridge for Home Assistant

A Home Assistant integration for a TV running KDE Plasma Bigscreen. It talks to the
Bigscreen Bridge service on the TV over an authenticated local WebSocket and gives
you native media players for the TV and its apps.

This repository holds only the Home Assistant side, packaged for
[HACS](https://hacs.xyz). The bridge service that runs on the TV, and the patches
for the four supported apps, live in the separate [bigscreen-bridge](https://github.com/shreyasajj/bigscreen-bridge) repository. Without
the bridge running on the TV this integration has nothing to connect to.

## What you get

- One media player for the TV: source selection between apps, system volume and
  mute, display on and off, media browsing, `play_media` with typed IDs.
- One media player each for Stremio TV, Flimmer and YouTube (VacuumTube) when the
  app is installed: title, artwork, position, duration, and only the transport
  controls the app reports.
- Media browsing for Flimmer channels, the Music Assistant library shown in
  Couchside, and Stremio's stored library.
- Couchside is navigation only. Music playback stays with the Music Assistant
  integration, so no duplicate music player is created.

## Install

1. In HACS open the menu, choose **Custom repositories**, add
   `https://github.com/shreyasajj/ha-bigscreen-bridge` with type **Integration**.
2. Install **Bigscreen Bridge** and restart Home Assistant.
3. A bridge on the same network segment appears under **Settings → Devices &
   services → Discovered**. Otherwise choose **Add integration → Bigscreen Bridge**
   and enter its address, for example `http://tv.local:8765`.
4. Enter the pairing token from `~/.config/bigscreen-bridge/config.json` on the TV.

Discovery uses mDNS, which does not cross VLANs. If Home Assistant and the TV are on
different subnets, enter the address by hand.

## Typed media IDs

| `media_content_type` | `media_content_id` |
| --- | --- |
| `app` | `couchside`, `stremio`, `flimmer`, `vacuumtube` |
| `youtube_video`, `youtube_playlist`, `youtube_search` | video ID, playlist ID, search text |
| `stremio_movie`, `stremio_series` | Stremio ID such as `tt0133093` |
| `stremio_episode` | JSON: `{"series_id": "...", "video_id": "..."}` |
| `flimmer_channel` | channel ID from media browsing |
| `couchside_now_playing`, `couchside_search` | empty, search text |
| `couchside_track`, `couchside_album`, `couchside_artist`, `couchside_playlist` | Music Assistant URI |
| `bigscreen_uri` | a `bigscreen://` deep link |

```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room_tv_youtube
data:
  media_content_type: youtube_video
  media_content_id: M7lc1UVf-VE
```

## Status

Version 0.2.1. Tested with Home Assistant 2026.2.3 through automated tests and a
temporary Home Assistant instance against a real TV. The minimum version in
`hacs.json` (2024.11) is the oldest release that has the APIs used; it has not been
tested there.

## Security

The token is a bearer secret for full control of the TV's apps, volume and display.
The connection is plain WebSocket unless you put the bridge behind TLS, so use it on
a trusted network only.

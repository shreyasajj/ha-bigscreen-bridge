"""Native active-app and dedicated video players with negotiated capabilities."""
import json
import re

from homeassistant.util import dt as dt_util
from homeassistant.components.media_player import (
    BrowseMedia, MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState, MediaType,
)
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


_BROWSE_ID = re.compile(r"(couchside|stremio|flimmer)(?:/([a-z_]{1,32}))?(?::([0-9]{1,7}))?")
_MEDIA_CLASSES = {"channel": "channel", "movie": "movie", "series": "tv_show", "album": "album",
                  "artist": "artist", "playlist": "playlist", "track": "track"}


# Playback controls a Music Assistant player offers that the Couchside view passes on to it.
_FORWARDED = (MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE | MediaPlayerEntityFeature.STOP
              | MediaPlayerEntityFeature.NEXT_TRACK | MediaPlayerEntityFeature.PREVIOUS_TRACK
              | MediaPlayerEntityFeature.SEEK)
_MUSIC_SERVICES = {"play": "media_play", "pause": "media_pause", "stop": "media_stop", "seek": "media_seek",
                   "next": "media_next_track", "previous": "media_previous_track"}
_PLAYABLE_MUSIC = ("couchside_track", "couchside_album", "couchside_artist", "couchside_playlist")


def music_assistant_entity_id(hass, player_id):
    """Home Assistant's Music Assistant integration registers each player under its MA player ID."""
    return er.async_get(hass).async_get_entity_id("media_player", "music_assistant", player_id)


def _browsable(app):
    """Bridges before the shared library contract only knew the Flimmer catalogue."""
    return bool(app.get("browse", app.get("id") == "flimmer" and app.get("hook_installed", False)))


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    players = [BigscreenPlayer(coordinator)]
    for app_id in ("stremio", "flimmer", "vacuumtube"):
        if any(a["id"] == app_id and a["installed"] for a in coordinator.data["apps"]):
            players.append(BigscreenPlayer(coordinator, app_id))
    async_add_entities(players)


class BigscreenPlayer(CoordinatorEntity, MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:television"
    _attr_supported_features = (MediaPlayerEntityFeature.SELECT_SOURCE
                                | MediaPlayerEntityFeature.PLAY_MEDIA
                                | MediaPlayerEntityFeature.BROWSE_MEDIA)

    def __init__(self, coordinator, app_id=None):
        super().__init__(coordinator)
        self._app_id = app_id
        if app_id:
            self._attr_name = {"stremio": "Stremio TV", "flimmer": "Flimmer", "vacuumtube": "YouTube"}[app_id]
        device_id = coordinator.data["device_id"]
        self._attr_unique_id = device_id + ("_" + app_id if app_id else "_active")
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)},
                                           name=coordinator.data["name"], manufacturer="KDE",
                                           model="Plasma Bigscreen")

    @property
    def _target(self):
        return self._app_id or self.coordinator.data.get("active_app")

    @property
    def _application(self):
        return next((a for a in self.coordinator.data["apps"] if a["id"] == self._target), {})

    @property
    def _media(self):
        return self._application.get("media", {}) if self._target in ("stremio", "flimmer", "vacuumtube") else {}

    def _couchside_music(self):
        """The Music Assistant player that owns Couchside's playback, if Home Assistant has it and it works."""
        if self._app_id or self.hass is None:
            return None
        couchside = next((a for a in self.coordinator.data["apps"] if a["id"] == "couchside"), {})
        player_id = couchside.get("ma_player_id")
        entity_id = player_id and music_assistant_entity_id(self.hass, player_id)
        state = entity_id and self.hass.states.get(entity_id)
        if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state

    @property
    def _music(self):
        """Couchside's Music Assistant player while the main player shows Couchside."""
        return self._couchside_music() if self._target == "couchside" else None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self._app_id:
            return

        @callback
        def relevant(event_data):
            music = self._music
            return music is not None and event_data.get("entity_id") == music.entity_id

        @callback
        def changed(_event):
            self.async_write_ha_state()

        # Music Assistant's player changes on its own; show those changes here at once.
        self.async_on_remove(self.hass.bus.async_listen(EVENT_STATE_CHANGED, changed, event_filter=relevant))

    @property
    def available(self):
        available = super().available and self.coordinator.data.get("available", True)
        if self._app_id:
            app = self._application
            return available and app.get("installed", False) and app.get("hook_installed", False) and (
                not app.get("running") or app.get("control_available", False))
        return available

    @property
    def _audio(self):
        """System audio belongs to the device player; app players keep their own volume."""
        return {} if self._app_id else self.coordinator.data.get("audio") or {}

    @property
    def _power(self):
        return {} if self._app_id else self.coordinator.data.get("power") or {}

    @property
    def supported_features(self):
        flags = (MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.TURN_ON) if self._app_id else self._attr_supported_features
        if self._app_id == "flimmer" or (self._app_id and self._application.get("browse")):
            flags |= MediaPlayerEntityFeature.BROWSE_MEDIA
        for capability, source, feature in (
                ("set_volume", self._audio, MediaPlayerEntityFeature.VOLUME_SET),
                ("mute", self._audio, MediaPlayerEntityFeature.VOLUME_MUTE),
                ("screen_on", self._power, MediaPlayerEntityFeature.TURN_ON),
                ("screen_off", self._power, MediaPlayerEntityFeature.TURN_OFF)):
            if capability in source.get("capabilities", []):
                flags |= feature
        if self._target in ("stremio", "flimmer", "vacuumtube"):
            capabilities = self._application.get("capabilities", [])
            for command, feature in (("play", MediaPlayerEntityFeature.PLAY), ("pause", MediaPlayerEntityFeature.PAUSE),
                                     ("stop", MediaPlayerEntityFeature.STOP), ("seek", MediaPlayerEntityFeature.SEEK),
                                     ("volume_set", MediaPlayerEntityFeature.VOLUME_SET), ("volume_mute", MediaPlayerEntityFeature.VOLUME_MUTE)):
                if command.startswith("volume_") and not self._app_id:
                    continue
                if command in capabilities:
                    flags |= feature
        if music := self._music:
            flags |= MediaPlayerEntityFeature(int(music.attributes.get("supported_features", 0))) & _FORWARDED
        return flags

    @property
    def state(self):
        if (self._power.get("display") or {}).get("display_on") is False:
            return MediaPlayerState.OFF
        if music := self._music:
            return MediaPlayerState(music.state) if music.state in set(MediaPlayerState) else MediaPlayerState.IDLE
        if self._media.get("state") == "buffering":
            return MediaPlayerState.BUFFERING
        if self._media.get("state") in ("playing", "paused"):
            return MediaPlayerState(self._media["state"])
        if self._app_id:
            return MediaPlayerState.IDLE if self._application.get("running") else MediaPlayerState.OFF
        return MediaPlayerState.IDLE if self._target else MediaPlayerState.OFF

    @property
    def media_title(self):
        if music := self._music:
            return music.attributes.get("media_title")
        if self._target == "flimmer":
            channel = self._media.get("channel", {})
            return channel.get("current", {}).get("title") or channel.get("name") or None
        return self._media.get("title") or None

    @property
    def media_artist(self):
        return music.attributes.get("media_artist") if (music := self._music) else None

    @property
    def media_album_name(self):
        return music.attributes.get("media_album_name") if (music := self._music) else None

    @property
    def entity_picture(self):
        """Couchside's artwork is Music Assistant's: reuse its image proxy."""
        if (music := self._music) and music.attributes.get("entity_picture"):
            return music.attributes["entity_picture"]
        return super().entity_picture

    @property
    def media_channel(self):
        return self._media.get("channel", {}).get("name") if self._target == "flimmer" else None

    @property
    def media_image_url(self):
        return self._media.get("poster") or None

    @property
    def volume_level(self):
        return self._media.get("volume") if self._app_id else self._audio.get("volume")

    @property
    def is_volume_muted(self):
        return self._media.get("muted") if self._app_id else self._audio.get("muted")

    @property
    def media_position(self):
        if music := self._music:
            return music.attributes.get("media_position")
        return self._media.get("position")

    @property
    def media_duration(self):
        if music := self._music:
            return music.attributes.get("media_duration")
        return self._media.get("duration")

    @property
    def media_position_updated_at(self):
        if music := self._music:
            return music.attributes.get("media_position_updated_at")
        value = self._media.get("updated_at")
        return dt_util.parse_datetime(value) if value else None

    @property
    def media_content_id(self):
        if self._target == "flimmer":
            return self._media.get("channel", {}).get("id") or None
        return self._media.get("content_id") or None

    @property
    def media_content_type(self):
        if self._music:
            return MediaType.MUSIC
        if self._target == "flimmer" and self.media_content_id:
            return "channel"
        return {"series": "tvshow", "movie": "movie", "video": "video"}.get(self._media.get("type"))

    @property
    def media_series_title(self):
        return self.media_title if self._media.get("type") == "series" else None

    def _episode_numbers(self):
        return re.match(r"S(\d+)E(\d+)", self._media.get("episode", ""))

    @property
    def media_season(self):
        match = self._episode_numbers()
        return int(match[1]) if match else None

    @property
    def media_episode(self):
        match = self._episode_numbers()
        return int(match[2]) if match else None

    async def async_turn_on(self):
        if self._app_id:
            await self.coordinator.command("focus", app=self._app_id)
        else:
            await self.coordinator.command("screen_on")

    async def async_turn_off(self):
        if self._app_id:
            raise HomeAssistantError("Turn off the display on the main Bigscreen player")
        await self.coordinator.command("screen_off")

    async def _forward(self, music, service, **data):
        await self.hass.services.async_call("media_player", service, {"entity_id": music.entity_id, **data},
                                            blocking=True)

    async def _player_command(self, command, **kwargs):
        if music := self._music:
            data = {"seek_position": kwargs["position"]} if command == "seek" else {}
            await self._forward(music, _MUSIC_SERVICES[command], **data)
            return
        if command in ("next", "previous"):
            raise HomeAssistantError("Only Couchside, through Music Assistant, has next and previous track")
        if self._target not in ("stremio", "flimmer", "vacuumtube"):
            raise HomeAssistantError("The active app does not support playback control")
        await self.coordinator.command(command, app=self._target, **kwargs)

    async def async_media_play(self):
        await self._player_command("play")

    async def async_media_pause(self):
        await self._player_command("pause")

    async def async_media_stop(self):
        await self._player_command("stop")

    async def async_media_next_track(self):
        await self._player_command("next")

    async def async_media_previous_track(self):
        await self._player_command("previous")

    async def async_media_seek(self, position):
        await self._player_command("seek", position=position)

    async def async_set_volume_level(self, volume):
        if self._app_id:
            await self._player_command("volume_set", volume_level=volume)
        else:
            await self.coordinator.command("set_volume", volume_level=volume)

    async def async_mute_volume(self, mute):
        if self._app_id:
            await self._player_command("volume_mute", muted=mute)
        else:
            await self.coordinator.command("mute" if mute else "unmute")

    @property
    def source_list(self):
        if self._app_id:
            return None
        return [a["name"] for a in self.coordinator.data["apps"] if a["installed"]]

    @property
    def source(self):
        if self._app_id:
            return self._application.get("name")
        return next((a["name"] for a in self.coordinator.data["apps"]
                     if a["id"] == self.coordinator.data.get("active_app")), None)

    @property
    def extra_state_attributes(self):
        music = next((a for a in self.coordinator.data["apps"] if a["id"] == "couchside"), {})
        return {"youtube_view": self._application.get("view") if self._target == "vacuumtube" else None,
                "flimmer_channel": self._media.get("channel") if self._target == "flimmer" else None,
                "couchside_content_types": music.get("content_types", []),
                "music_assistant_player_id": music.get("ma_player_id"),
                "music_assistant_entity_id": (state := self._couchside_music()) and state.entity_id,
                "couchside_playback_owner": music.get("playback_owner")}

    async def async_select_source(self, source):
        if self._app_id:
            raise HomeAssistantError("Select sources on the main Bigscreen player")
        app = next((a for a in self.coordinator.data["apps"]
                    if a["name"] == source and a["installed"]), None)
        if not app:
            raise HomeAssistantError("Unknown or uninstalled source")
        await self.coordinator.command("focus", app=app["id"])

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_type == "bigscreen_uri":
            target = {"app": self._app_id} if self._app_id else {}
            await self.coordinator.command("open_uri", uri=media_id, **target)
            return
        if self._app_id:
            if media_type == "app":
                if media_id != self._app_id:
                    raise HomeAssistantError("Unsupported app for this player")
            elif media_type not in self._application.get("content_types", []):
                raise HomeAssistantError("Unsupported media type for this app player")
        if isinstance(media_type, str) and media_type.startswith("youtube_"):
            app = next((a for a in self.coordinator.data["apps"] if a["id"] == "vacuumtube"), {})
            if media_type not in app.get("content_types", []):
                raise HomeAssistantError("VacuumTube does not advertise this navigation capability")
            await self.coordinator.command("open", app="vacuumtube", content_type=media_type.removeprefix("youtube_"),
                                           content_id=media_id)
            return
        if media_type == "flimmer_channel":
            app = next((a for a in self.coordinator.data["apps"] if a["id"] == "flimmer"), {})
            if media_type not in app.get("content_types", []):
                raise HomeAssistantError("Flimmer does not advertise channel control")
            await self.coordinator.command("open", app="flimmer", content_type="channel", content_id=media_id)
            return
        if isinstance(media_type, str) and media_type.startswith("stremio_"):
            app = next((a for a in self.coordinator.data["apps"] if a["id"] == "stremio"), {})
            if media_type not in app.get("content_types", []):
                raise HomeAssistantError("Stremio does not advertise this navigation capability")
            content_id = media_id
            if media_type == "stremio_episode":
                try:
                    content_id = json.loads(media_id)
                except (ValueError, TypeError) as exc:
                    raise HomeAssistantError("Episode ID must be JSON with series_id and video_id") from exc
            extra = kwargs.get("extra") or {}
            await self.coordinator.command("open", app="stremio", content_type=media_type.removeprefix("stremio_"),
                                           content_id=content_id, resume=extra.get("resume", False))
            return
        if self._app_id and (media_type != "app" or media_id != self._app_id):
            raise HomeAssistantError("Unsupported media type for this app player")
        if isinstance(media_type, str) and media_type.startswith("couchside_"):
            app = next((a for a in self.coordinator.data["apps"] if a["id"] == "couchside"), {})
            if media_type not in app.get("content_types", []):
                raise HomeAssistantError("Couchside does not advertise this navigation capability")
            if media_type in _PLAYABLE_MUSIC and (music := self._couchside_music()):
                # Play it through Music Assistant, then show it playing.
                await self._forward(music, "play_media", media_content_id=media_id, media_content_type="music")
                if "couchside_now_playing" in app.get("content_types", []):
                    await self.coordinator.command("open", app="couchside", content_type="now_playing", content_id="")
                return
            await self.coordinator.command("open", app="couchside",
                                           content_type=media_type.removeprefix("couchside_"),
                                           content_id=media_id)
            return
        if media_type != "app":
            raise HomeAssistantError("Unsupported media content type")
        app = next((a for a in self.coordinator.data["apps"]
                    if a["id"] == media_id and a["installed"]), None)
        if not app:
            raise HomeAssistantError("Unknown or uninstalled app")
        await self.coordinator.command("focus", app=app["id"])

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        apps = {a["id"]: a for a in self.coordinator.data["apps"]}
        if media_content_id in (None, "", "apps") and self._app_id and (
                self._app_id == "flimmer" or apps.get(self._app_id, {}).get("browse")):
            media_content_id = self._app_id  # an app player opens straight into its own library
        if media_content_id in (None, "", "apps"):
            result = await self.coordinator.command("browse")
            return BrowseMedia(title="Bigscreen apps", media_class="directory", media_content_id="apps",
                               media_content_type=MediaType.APP, can_play=False, can_expand=True,
                               children=[BrowseMedia(title=item["title"], media_class="app",
                                                     media_content_type="app", media_content_id=item["id"],
                                                     can_play=True, can_expand=_browsable(apps.get(item["id"], {})))
                                         for item in result["items"]])
        page = _BROWSE_ID.fullmatch(media_content_id)
        if not page:
            raise HomeAssistantError("Unsupported media catalogue")
        app_id, path, offset = page[1], page[2], int(page[3] or 0)
        if self._app_id not in (None, app_id):
            raise HomeAssistantError("Unsupported catalogue for this app player")
        result = await self.coordinator.command("browse", app=app_id, offset=offset, limit=50,
                                                **({"path": path} if path else {}))
        if not result["items"] and result.get("loading"):
            raise HomeAssistantError("Flimmer is loading its channel catalogue")
        channels = app_id == "flimmer"
        section = "flimmer_channels" if channels else app_id + "_library"
        here = app_id + ("/" + path if path else "")
        children = []
        for item in result["items"]:
            if item.get("path"):
                children.append(BrowseMedia(title=item["name"], media_class="directory", media_content_type=section,
                                            media_content_id=f"{app_id}/{item['path']}", can_play=False, can_expand=True))
                continue
            kind = item.get("media_content_type") or "flimmer_channel"
            children.append(BrowseMedia(title=item["name"], media_class=_MEDIA_CLASSES.get(kind.split("_", 1)[-1], "video"),
                                        media_content_type=kind, media_content_id=item["id"],
                                        can_play=True, can_expand=False))
        if result.get("next_offset") is not None:
            children.append(BrowseMedia(title="More channels" if channels else "More", media_class="directory",
                                        media_content_type=section,
                                        media_content_id=f"{here}:{result['next_offset']}",
                                        can_play=False, can_expand=True))
        title = "Flimmer channels" if channels else apps.get(app_id, {}).get("name", app_id) + " library"
        return BrowseMedia(title=title, media_class="directory", media_content_id=f"{here}:{offset}",
                           media_content_type=section, can_play=False, can_expand=True, children=children)

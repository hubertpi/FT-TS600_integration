"""Home Assistant host for a directly connected Crestron touchpanel."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .protocol import ACCEPT, HELLO, INIT, PING, READY, UPDATE, digital_feedback
from .protocol import digital_joins, read_frame, signon_matches

DOMAIN = "ft_ts600"
ENTITY = "binary_sensor.ft_ts600_connected"
_LOGGER = logging.getLogger(__name__)
_BUTTONS = {
    95: "options",
    100: "start",
    101: "power",
    105: "presentation",
    107: "settings_or_phone",
    110: "airmedia",
    111: "blu_ray",
    112: "room_pc",
    113: "showcase_left",
    114: "showcase_right",
    115: "table_input_1",
    116: "table_input_2",
    117: "table_input_3",
    118: "table_input_4",
    120: "volume_up",
    121: "volume_down",
    122: "mute",
}
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({
        vol.Required("listen_host"): cv.string,
        vol.Optional("listen_port", default=41805): cv.port,
        vol.Required("panel_host"): cv.string,
        vol.Optional("ip_id", default=5): vol.All(vol.Coerce(int), vol.Range(min=1, max=254)),
    })},
    extra=vol.ALLOW_EXTRA,
)


class PanelHost:
    def __init__(self, hass: HomeAssistant, panel_host: str, ip_id: int) -> None:
        self.hass = hass
        self.panel_host = panel_host
        self.ip_id = ip_id
        self.writer: asyncio.StreamWriter | None = None
        self.server: asyncio.Server | None = None
        self.connected = False
        self.sessions = 0
        self.heartbeats = 0
        self.feedback: dict[int, bool] = {}

    def publish(self) -> None:
        self.hass.states.async_set(ENTITY, "on" if self.connected else "off", {
            "friendly_name": "FT-TS600 CIP connection",
            "device_class": "connectivity",
            "ip_id": self.ip_id,
            "sessions": self.sessions,
            "heartbeat_frames": self.heartbeats,
        })

    async def start(self, host: str, port: int) -> None:
        self.server = await asyncio.start_server(self.handle, host, port)
        self.publish()

    async def stop(self, _event) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if self.writer:
            self.writer.close()

    async def send(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        writer.write(data)
        await asyncio.wait_for(writer.drain(), 5)

    async def heartbeat(self, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                await asyncio.sleep(10)
                await self.send(writer, PING)
        except (OSError, TimeoutError):
            writer.close()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        if not peer or peer[0] != self.panel_host or self.writer is not None:
            writer.close()
            return
        self.writer = writer
        heartbeat = None
        try:
            async with asyncio.timeout(12):
                await self.send(writer, HELLO)
                if not signon_matches(await read_frame(reader), self.ip_id):
                    raise ValueError("Unexpected panel registration or IP ID")
                await self.send(writer, ACCEPT)
                if await read_frame(reader) != UPDATE:
                    raise ValueError("Missing panel startup update request")
                await self.send(writer, UPDATE)
                await self.send(writer, INIT)
                if await read_frame(reader) != READY:
                    raise ValueError("Missing panel initialization acknowledgement")
            self.connected = True
            self.sessions += 1
            self.publish()
            for join, value in self.feedback.items():
                await self.send(writer, digital_feedback(join, value))
            heartbeat = asyncio.create_task(self.heartbeat(writer))
            levels: dict[int, bool] = {}
            while True:
                frame = await asyncio.wait_for(read_frame(reader), 45)
                if frame[0] in (0x0D, 0x0E):
                    if frame[0] == 0x0D:
                        await self.send(writer, b"\x0e" + frame[1:])
                    self.heartbeats += 1
                    self.publish()
                elif frame == UPDATE:
                    for join, value in self.feedback.items():
                        await self.send(writer, digital_feedback(join, value))
                else:
                    for join, pressed in digital_joins(frame):
                        previous = levels.get(join)
                        levels[join] = pressed
                        if previous == pressed or (previous is None and not pressed):
                            continue
                        self.hass.bus.async_fire("ft_ts600_button", {
                            "join": join, "pressed": pressed,
                            "action": _BUTTONS.get(join, f"join_{join}"),
                        })
        except (OSError, TimeoutError, ValueError, asyncio.IncompleteReadError) as err:
            _LOGGER.debug("FT-TS600 connection ended: %s", err)
        finally:
            if heartbeat:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            writer.close()
            self.writer = None
            self.connected = False
            self.publish()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    settings = config.get(DOMAIN)
    if settings is None:
        return True
    panel = PanelHost(hass, settings["panel_host"], settings["ip_id"])
    try:
        await panel.start(settings["listen_host"], settings["listen_port"])
    except OSError as err:
        _LOGGER.error("Could not open FT-TS600 listener: %s", err)
        return False

    async def set_digital(call: ServiceCall) -> None:
        join, value = call.data["join"], call.data["value"]
        panel.feedback[join] = value
        writer = panel.writer
        if writer and panel.connected:
            try:
                await panel.send(writer, digital_feedback(join, value))
            except (OSError, TimeoutError) as err:
                writer.close()
                raise HomeAssistantError("Could not send panel feedback") from err

    async def reconnect(_call: ServiceCall) -> None:
        if panel.writer:
            panel.writer.close()

    hass.services.async_register(DOMAIN, "set_digital", set_digital, schema=vol.Schema({
        vol.Required("join"): vol.All(vol.Coerce(int), vol.Range(min=1, max=32768)),
        vol.Required("value"): cv.boolean,
    }))
    hass.services.async_register(DOMAIN, "reconnect", reconnect)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, panel.stop)
    return True

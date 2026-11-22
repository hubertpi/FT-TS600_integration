# FT-TS600 integration

Home Assistant acts as the CIP host for a Crestron FT-TS600. The touchpanel connects directly and the integration emits button events. Create HA automations for device control and use digital feedback for the panel's indicators.

## Setup

Copy `custom_components/ft_ts600` into Home Assistant's `custom_components` directory. Add this configuration with the addresses for your installation, then restart Core.

```yaml
ft_ts600:
  listen_host: 192.168.1.10
  listen_port: 41805
  panel_host: 192.168.1.32
  ip_id: 5
```

Set the panel's master entry to the HA address and port with CIP ID `05`. Keep the original settings for rollback. The listener accepts the configured panel address and registration ID. Keep the unencrypted CIP listener on the control LAN.

Connection status and counters are available at `binary_sensor.ft_ts600_connected`. Listen for `ft_ts600_button` in Developer Tools to see `join`, `pressed`, and `action` values. For example:

```yaml
triggers:
  - trigger: event
    event_type: ft_ts600_button
    event_data:
      join: 115
      pressed: true
actions:
  - action: scene.turn_on
    target:
      entity_id: scene.table_input
```

Use `ft_ts600.set_digital` with `join` and `value` to send indicator feedback. Explicit feedback is replayed after registration during the current HA process. `ft_ts600.reconnect` closes the panel's current socket so you can check that it signs on again.

The connection uses the observed FT-TS600 sign-on and initialization exchange. The existing panel project determines the pages, logo and joins.

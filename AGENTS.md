# FT-TS600 project handoff

Pull the latest changes before starting work on another machine. Read this file and the [integration README](README.md) for setup. Update this file in the same commit when you verify a deployment detail or change the intended behavior. Keep credentials and site-specific connection settings in the deployment environment.

## FT-TS600 and Home Assistant

- Home Assistant is the CIP host. The panel connects directly to HA on the control LAN using the standard TCP port 41794 and panel master ID `05`. See the README for setup and rollback details.
- Check `binary_sensor.ft_ts600_connected` and listen for `ft_ts600_button` events in Developer Tools to confirm registration and physical button presses. HA sends indicator feedback using `ft_ts600.set_digital`. The panel project owns the pages, graphics, and join assignments.
- The documented installation copies `custom_components/ft_ts600` into HA. Use an authenticated checkout for future deploys from this private repository. Verify the running HA configuration and panel version before changing live behavior.

## Boardroom behavior to preserve

These are the prior project requirements. Check them against the live HA automations and panel project when making changes.

- The presentation page has four display buttons. Source selection routes only displays that are on. A display turned on later follows the current presentation source.
- Turning either Sony display off from the panel returns that display to its corresponding left or right Showcase source. The regular HA power controls can still shut the displays down.
- The side power button ends the presentation and returns to the start screen. Home returns to Presentation, the bulb button opens the lighting scenes, and the volume buttons adjust QSC volume in 5 percentage-point steps. The volume bar reflects actual volume, and lighting scene highlights follow the current scene.
- The original source page used `TableInput 1` through `TableInput 4`. The next design under discussion restores four individually selectable table inputs and adds Auto while retaining Room PC. Confirm port mapping before wiring the buttons. The previously shared preview was a local prototype.

## DM 8×1 Auto feedback

- Keep configured source selection, actual routed input in Auto, and input signal presence distinct. The HA selector is `select.crestron_dm_8x1_source`. The factory XPanel's active-low digital join `1521` on ID `05` indicates Auto mode. The route command numbers for HDMI 1–4 are 3, 5, 7, and 9, with 0 for Auto. Confirm the physical table-to-HDMI mapping.
- The provisional sensor is `sensor.crestron_dm_8x1_xpanel_source_feedback`. It polls every 15 seconds through `/config/packages/dm8x1_xpanel_feedback.yaml` and `/config/scripts/dm8x1_xpanel_source.py` on HA. Device Tools associates the sensor with the 8×1 device. The feedback code lives in the site configuration.
- Auto with no live source was observed as `No Source`. The actual routed-source feedback and per-input signal presence still need a live signal test. Move a live source between two known table ports in Auto and compare the sensor with the route shown by the switcher before using it for the panel highlight.

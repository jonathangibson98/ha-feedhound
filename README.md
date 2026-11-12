# Feedhound

![Feedhound](custom_components/feedhound/brand/logo.png)

Pull any RSS/Atom feed into a Home Assistant sensor. The sensor state is the number of
entries, and every entry lives in the `entries` attribute so you can show them with a
Lovelace list card.

Based on the MIT-licensed [sensor.feedparser](https://github.com/custom-components/feedparser)
by Ian Richardson and Ondrej Gajdusek.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/jonathangibson98/ha-feedhound`, category **Integration**
3. Install **Feedhound**, then **restart Home Assistant**

Manual install: copy `custom_components/feedhound` into your HA `config/custom_components/` folder and restart.

The icon and logo show up in the UI on Home Assistant 2026.3 or newer.

## Configure

You can set feeds up either way. Both work at the same time.

### Option A: the UI

**Settings → Devices & services → Add integration → Feedhound.** Fill in the form
(Feedhound test-downloads the feed before it saves, so typos get caught right away).
To change anything later, open the Feedhound entry and hit the **cog / Configure**
button. Changes apply instantly, no restart.

### Option B: YAML

Add to `configuration.yaml`, then restart:

```yaml
sensor:
  - platform: feedhound
    name: Engineering Feed
    unique_id: feedhound_engineering   # optional, see note below
    feed_url: "https://www.sciencedaily.com/rss/matter_energy/engineering.xml"
    date_format: "%a, %d %b %Y %H:%M:%S %Z"
    scan_interval:
      hours: 3
    inclusions:
      - title
      - link
      - description
      - image
      - published
    exclusions:
      - language

  - platform: feedhound
    name: Algemeen
    feed_url: https://www.nu.nl/rss/Algemeen
    local_time: true
    show_topn: 1
```

YAML feeds are edited in YAML. UI feeds are edited in the UI. They don't overwrite each other.
Add a `unique_id` to a YAML feed if you also want to rename it, change its icon/area or
entity ID from the UI.

| Key | Description |
|---|---|
| `platform` (required) | Always `feedhound` |
| `name` (required) | Name of the sensor |
| `feed_url` (required) | The RSS/Atom feed URL |
| `date_format` | strftime format. Default `%a, %b %d %I:%M %p` |
| `local_time` | Convert dates to local time. Default `false` |
| `show_topn` | Max number of entries to keep. Default: all |
| `inclusions` | Only keep these fields |
| `exclusions` | Drop these fields |
| `scan_interval` | How often to refresh. Default 1 hour (UI: minutes) |
| `unique_id` | YAML only, optional. Lets you edit the entity in the UI |

Add `image` to `inclusions` if you want Feedhound to dig out an image per entry. If none is
found it falls back to a default thumbnail. Don't use `enclosure`.

If you see a `ModuleNotFoundError` on first boot, restart Home Assistant once more.

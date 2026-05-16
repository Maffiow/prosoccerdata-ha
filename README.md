# ProSoccerData – Home Assistant Integration

Track your kids' soccer matches from [app.prosoccerdata.com](https://app.prosoccerdata.com) directly in Home Assistant.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

## Features

- One sensor per player showing the **date of their last played match**
- Attributes on each sensor:
  - Opponent, score, home/away, competition
  - Venue (full address)
  - Meeting time and meeting location
  - Attendance state
  - List of the 10 most recent matches
- Updates every 30 minutes

## Installation via HACS

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/janmeermans/prosoccerdata-ha`, category **Integration**
3. Click **Install** on *ProSoccerData*
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration** and search for *ProSoccerData*

## Manual Installation

Copy the `custom_components/prosoccerdata` folder into your HA `config/custom_components/` directory, then restart HA.

## Configuration

The setup wizard will ask for:
1. Your **email** and **password** for app.prosoccerdata.com
2. Which **players (kids)** you want to track

## Sensor

| Property | Value |
|----------|-------|
| State | `YYYY-MM-DD` of last match |
| Icon | `mdi:soccer` |
| `team` | Player's team name |
| `opponent` | Opponent team |
| `score` | Match score (e.g. `2-1`) |
| `home_away` | `Home` or `Away` |
| `competition` | Competition name |
| `location` | Venue address |
| `meeting_hour` | Assembly time |
| `meeting_location` | Assembly location address |
| `attendance_state` | e.g. `PRESENT` |
| `full_title` | Full match title (e.g. `Home FC - Away FC`) |
| `recent_matches` | List of last 10 matches |

## Troubleshooting

Run `test_api.py` (at the repo root) with your credentials to verify the API calls work before adding to HA:

```powershell
pip install aiohttp
$env:PSD_EMAIL='your@email.com'
$env:PSD_PASSWORD='yourpassword'
python test_api.py
```

The script prints every HTTP status and response body so you can confirm the API is reachable.

## API Notes

Authentication against `psd.prosoccerdata.com`:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v2/login/oauth/token?platform=` | Central login → JWT |
| `GET /api/v2/central-users/current/possible-users` | List players |

Then on the club subdomain (e.g. `kskmeeuwen.prosoccerdata.com`):

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v2/central-users/select` | Create platform session → UUID token |
| `GET /api/v2/schedule/dashboard/games/previous?size=20&page=0&sort=date,desc` | Previous matches |

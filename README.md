# ⚽ ProSoccerData for Home Assistant

Track your ProSoccerData players, matches, payments, team information and account details directly in Home Assistant.

Besides match tracking, the integration also exposes financial, profile, team, mailbox and account sensors.

---

## ✨ Features

* Multi-player support
* A calendar per player with matches, trainings and other events
* Next match and next training as timestamp sensors
* Previous match tracking with match history attributes
* Payment request tracking and total-paid calculation
* Team, member profile and account information
* Mailbox integration with inbox and unread message tracking
* Reconfigurable players and polling interval, without reinstalling
* Re-authentication prompt when your ProSoccerData password changes
* Diagnostics download with credentials and personal data redacted
* Installed and updated through HACS

---

## 🎯 Supported functionality

| Platform | Per player | What it does |
| --- | --- | --- |
| `calendar` | 1 entity | Matches, trainings and other events, as a real calendar you can automate on and show in the calendar panel. |
| `sensor` | 17 entities | Next match and next training, the last match with its season history, payments, team and profile details, and the mailbox. |

Three actions are registered: `prosoccerdata.open_message`,
`prosoccerdata.mark_message_read` and `prosoccerdata.get_attendance`. They are
described under [Actions](#-actions).

Each tracked player becomes its own device, so the entities group per child and
can be assigned to an area. The integration is cloud polling: it reads from
ProSoccerData and writes back only the read flag of a mailbox message, through
`prosoccerdata.mark_message_read`.

Not supported, because ProSoccerData does not offer it to a parent account:
confirming or declining attendance, entering match results, and anything to do
with other clubs' teams.

---

## ✅ Requirements

* Home Assistant **2026.3** or newer (needed for the integration's own icon)
* HACS **2.0** or newer
* A ProSoccerData account with at least one linked player

---

## 📦 Installation via HACS

1. Open **HACS**
2. Click **⋮ → Custom repositories**
3. Add the repository, with type **Integration**:

```text
https://github.com/Maffiow/prosoccerdata-ha
```

4. Search for **ProSoccerData** and download it
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration** and pick **ProSoccerData**

---

## ⬆️ Upgrading

Every version is published as a GitHub release, so HACS picks new ones up on its
own — no removing and reinstalling.

1. HACS shows **Update** on the ProSoccerData card (use **⋮ → Update information**
   to check immediately)
2. Click **Update**
3. Restart Home Assistant

Your account, selected players and options survive the upgrade.

### Upgrading to 0.10.0

The **Account** sensor moves to the device's *Diagnostic* section and is no
longer created for players you add from now on; the ones you already have keep
working and stay enabled. **Profile** moves to *Diagnostic* too, which only
changes where it sits on the device page.

Dropping a player now removes its device as well, instead of leaving it behind.

### Upgrading to 0.4.0

Adds a calendar entity and two timestamp sensors per player. Nothing is removed,
so there is nothing to clean up. If the new entities stay unavailable, the
schedule endpoint did not answer for your club — the rest of the integration
keeps working, and `custom_components.prosoccerdata` on debug level says why.

### Upgrading to 0.3.0

`sensor.<player>_unread_messages` has been removed: it always reported exactly the
same number as `sensor.<player>_unread_message_count`, which now carries the unread
list in its attributes. After updating, delete the leftover entity under
**Settings → Devices & Services → Entities** (it will show as *restored*), and point
any automation that used it at `sensor.<player>_unread_message_count` instead.

---

## ⚙️ Configuration

### Installation parameters

The setup form asks for these; nothing is configured in YAML.

| Field | Required | Description |
| --- | --- | --- |
| Email address | yes | The email address you sign in to ProSoccerData with. Checked against ProSoccerData before the entry is created. |
| Password | yes | Your ProSoccerData password. It is stored in the config entry so the integration can sign in again on its own, and is redacted from diagnostics. |
| Players | yes | Which of the players on the account to follow. Each one becomes a device with its own sensors and calendar. At least one is required. |

An account can be added once. Adding the same email a second time is refused.

### Configuration parameters

**Settings → Devices & Services → ProSoccerData → Configure** changes these
afterwards:

| Option | Default | Description |
| --- | --- | --- |
| Players | as chosen at setup | Add or drop tracked players. Dropping one removes its device and entities as well. |
| Update interval | 30 minutes | How often ProSoccerData is polled, between 5 and 1440 minutes. |

Saving reloads the integration straight away.

### Reconfiguring the account

**Settings → Devices & Services → ProSoccerData → ⋮ → Reconfigure** re-enters
the credentials and the player selection in one pass. It is the place to go
after a password change you want to apply yourself, rather than waiting for the
integration to notice. It has to stay the same ProSoccerData account — a
different email address is refused, because the account is what tells two
entries apart; add the other account as a second entry instead.


### Password changes

When ProSoccerData starts refusing the stored password, Home Assistant asks you
to sign in again through a repair notification. Nothing has to be removed, and
the tracked players and options are kept.

---

## 🔄 Data updates

The integration polls; nothing is pushed to it. One coordinator refresh covers
every tracked player, **every 30 minutes** by default (configurable between 5
minutes and a day). A refresh makes roughly seven calls per player: previous
matches, payment requests, team and profile, the inbox page, the unread list,
the squad list and the schedule window.

The schedule window the coordinator keeps is **yesterday to 120 days ahead**.
That window feeds the Next Match, Next Training and Upcoming Events sensors.
The calendar panel asks for whatever range it is showing, so scrolling back a
season fetches that range on demand instead of from the cached window.

Two things do not wait for the next poll:

* `prosoccerdata.open_message` fetches the message body there and then.
* `prosoccerdata.mark_message_read` writes the flag and asks for a refresh
  straight away, so the unread count catches up within seconds.

A refresh that fails keeps the previous values rather than blanking the
sensors, and a player whose data cannot be fetched at all goes unavailable on
its own without taking the other players down. The failure is logged once when
it starts and once when it recovers, not on every cycle.

---

## 🗑️ Removal

**Settings → Devices & Services → ProSoccerData → ⋮ → Delete** removes the
entry, its devices and all of its entities. Nothing is left in Home Assistant
afterwards, and nothing is changed in your ProSoccerData account.

To remove the integration itself as well, delete it in **HACS** and restart
Home Assistant.

---

# 📊 Available Entities

> **Entity IDs follow your Home Assistant language.** Home Assistant builds an
> entity ID from the translated entity name the first time it sees an entity, so
> on a Dutch installation `sensor.<player>_next_match` is created as
> `sensor.<player>_volgende_wedstrijd` and the calendar as
> `calendar.<player>_planning`. Entities that already existed keep the ID they
> were created with. The names below are the English ones; check
> **Settings → Devices & Services → Entities** for what your install actually
> used, and rename there if you want them to match.

## 📅 Schedule (calendar)

**Entity**

```text
calendar.<player>_schedule
```

| Property    | Value                                                       |
| ----------- | ----------------------------------------------------------- |
| State       | `on` while an event is running, otherwise `off`              |
| Icon        | mdi:calendar-clock                                          |
| summary     | Event title                                                 |
| location    | Venue, or the meeting point when no venue is set            |
| description | Opponent, home/away, team, competition, meeting time, attendance |

Matches, trainings and other club events, all in one calendar. Opening a month
in the calendar panel fetches that range from ProSoccerData directly, so you can
look further ahead than the 30-day window the sensors use. Cancelled events are
left out.

---

## ⏭️ Next Match

**Entity**

```text
sensor.<player>_next_match
```

| Property         | Value                          |
| ---------------- | ------------------------------ |
| State            | Start time (timestamp)         |
| Icon             | mdi:soccer-field               |
| title            | Full match title               |
| event_type       | `game`                         |
| opponent         | Opponent team                  |
| home_away        | Home or Away                   |
| team             | Player's team                  |
| competition      | Competition name               |
| location         | Venue address                  |
| meeting_hour     | Assembly time                  |
| meeting_location | Assembly address               |
| match_end        | End time                       |
| attendance_state | Attendance status              |

Because the state is a real timestamp, a reminder is a one-line trigger:

```yaml
triggers:
  - trigger: time
    at:
      entity_id: sensor.<player>_next_match
      offset: "-02:00:00"
```

---

## 🏃 Next Training

**Entity**

```text
sensor.<player>_next_training
```

Same attributes as Next Match, minus `opponent` and `home_away`. Icon
mdi:whistle.

---

## ⚽ Last Match

**Entity**

```text
sensor.<player>_last_match
```

| Property         | Value                    |
| ---------------- | ------------------------ |
| State            | Date of the last match   |
| Icon             | mdi:soccer               |
| team             | Player's team name       |
| opponent         | Opponent team            |
| score            | Match score (e.g. 2-1)   |
| home_away        | Home or Away             |
| competition      | Competition name         |
| location         | Venue address            |
| meeting_hour     | Assembly time            |
| attendance_state | Attendance status        |
| full_title       | Full match title         |
| recent_matches   | List of last 10 matches  |
| season_matches   | Every match since 1 July, including return legs, with the player's attendance |

---

## 💰 Last Payment Amount

**Entity**

```text
sensor.<player>_last_payment_amount
```

| Property | Value                 |
| -------- | --------------------- |
| State    | Latest payment amount |
| Unit     | EUR                   |
| Icon     | mdi:cash              |

---

## ✅ Last Payment Status

**Entity**

```text
sensor.<player>_last_payment_status
```

| Property    | Value                             |
| ----------- | --------------------------------- |
| State       | paid / pending / overdue / unpaid |
| Icon        | mdi:cash-check                    |
| id          | Payment request ID                |
| description | Payment description               |
| amount      | Requested amount                  |
| sent_date   | Request creation date             |
| due_date    | Due date                          |
| paid        | Payment status information        |

---

## 💸 Total Paid

**Entity**

```text
sensor.<player>_total_paid
```

| Property | Value             |
| -------- | ----------------- |
| State    | Total paid amount |
| Unit     | EUR               |
| Icon     | mdi:cash-multiple |

---

## 🔢 Payment Count

**Entity**

```text
sensor.<player>_payment_count
```

| Property         | Value                              |
| ---------------- | ---------------------------------- |
| State            | Number of fetched payment requests |
| Icon             | mdi:counter                        |
| payment_requests | List of payment requests           |

---

## 👤 Profile

A *diagnostic* entity: it sits under **Diagnostic** on the device page
rather than with the match and payment sensors. It is enabled, and works
exactly as before.

**Entity**

```text
sensor.<player>_profile
```

| Property            | Value               |
| ------------------- | ------------------- |
| State               | Full player name    |
| Icon                | mdi:account         |
| member_id           | PSD member ID       |
| first_name          | First name          |
| last_name           | Last name           |
| nickname            | Nickname            |
| local_name          | Local name          |
| birth_date          | Date of birth       |
| age                 | Player age          |
| status              | Member status       |
| active              | Active flag         |
| gender              | Gender              |
| keeper              | Goalkeeper flag     |
| foot                | Preferred foot      |
| shirt_number        | Shirt number        |
| language            | PSD language        |
| uuid                | Member UUID         |
| central_psd_id      | PSD central ID      |
| profile_picture_url | Profile picture URL |

---

## 🏆 Team

**Entity**

```text
sensor.<player>_team
```

| Property                       | Value                  |
| ------------------------------ | ---------------------- |
| State                          | Current team name      |
| Icon                           | mdi:account-group      |
| team_id                        | Team ID                |
| team_ids                       | Team IDs               |
| team_name                      | Team name              |
| team_subcategory               | Team subgroup          |
| team_international             | International team     |
| team_international_subcategory | International subgroup |
| club_id                        | Club ID                |
| club_international             | International club     |
| role_name                      | Role name              |
| function_title                 | Function title         |
| main_sportive_role             | Main sportive role     |
| main_sportive_role_id          | Main sportive role ID  |

---

## 📨 Message Count

**Entity**

```text
sensor.<player>_message_count
```

| Property | Value                          |
| -------- | ------------------------------ |
| State    | Total number of inbox messages |
| Icon     | mdi:email                      |

---

## 📬 Unread Message Count

**Entity**

```text
sensor.<player>_unread_message_count
```

| Property       | Value                                            |
| -------------- | ------------------------------------------------ |
| State          | Number of unread mailbox messages, however old   |
| Icon           | mdi:email-alert                                  |
| latest_subject | Subject of the newest unread message             |
| messages       | List of unread messages (max 15)                 |
| messages_text  | The same list as one ready-to-notify text block  |

> Replaces the former `sensor.<player>_unread_messages`, which reported the
> same number. See [Upgrading](#-upgrading).

---
## 📩 Last Message

**Entity**

```text
sensor.<player>_last_message
```

| Property         | Value                               |
| ---------------- | ----------------------------------- |
| State            | Subject of the latest inbox message |
| Icon             | mdi:email-open-outline              |
| id               | Message ID                          |
| sender           | Sender name                         |
| date             | Message date                        |
| first_sentence   | Message preview                     |
| unread           | Unread flag                         |
| attachment_count | Number of attachments               |
| receiver_count   | Number of receivers                 |
| deleted          | Deleted flag                        |
| draft            | Draft flag                          |
| attachments      | List of attachments                 |
| receivers        | Receiver information                |

Only this sensor carries the full `attachments` and `receivers` detail; the
list sensors keep counts instead, to stay out of the recorder database.

---
## 📥 Messages

**Entity**

```text
sensor.<player>_messages
```

| Property           | Value                              |
| ------------------ | ---------------------------------- |
| State              | Number of fetched inbox messages   |
| Icon               | mdi:email-multiple-outline         |
| total_elements     | Total mailbox messages             |
| number_of_elements | Number of fetched messages         |
| total_pages        | Mailbox pages                      |
| messages           | List of mailbox messages (max 15)  |

### Message Attributes

Each message in a list attribute contains:

| Property         | Value                 |
| ---------------- | --------------------- |
| id               | Message ID            |
| subject          | Message subject       |
| sender           | Sender name           |
| date             | Message date          |
| first_sentence   | Message preview       |
| unread           | Read status           |
| attachment_count | Number of attachments |
| receiver_count   | Number of receivers   |

---
## 🗓️ Upcoming Events

**Entity**

```text
sensor.<player>_upcoming_events
```

| Property | Value                                                       |
| -------- | ----------------------------------------------------------- |
| State    | Number of scheduled events that have not finished yet       |
| Icon     | mdi:calendar-clock                                          |
| events   | Up to 40 events, soonest first (kept out of the recorder)   |

Each event carries `uid`, `type` (`game`, `training` or `other`), `title`,
`start`, `end`, `team`, `opponent`, `home_away`, `competition`, `location`,
`meeting_hour`, `meeting_location` and `attendance`, so a dashboard can show
the full details of an event without going through the calendar.

---
## 👥 Team Members

**Entity**

```text
sensor.<player>_team_members
```

| Property | Value                                                    |
| -------- | -------------------------------------------------------- |
| State    | Number of players in the player's team                   |
| Icon     | mdi:account-group                                        |
| players  | The squad: `name`, `keeper`, `shirt_number`, `position`  |

Birth dates and contact details of teammates are deliberately left out.

---
## 📖 Selected Message

**Entity**

```text
sensor.<player>_selected_message
```

Shows the message last opened with the `prosoccerdata.open_message` action,
so a dashboard can display its full text.

| Property        | Value                                 |
| --------------- | ------------------------------------- |
| State           | Subject of the opened message         |
| Icon            | mdi:email-open                        |
| id              | Message ID                            |
| member_id       | Player the mailbox belongs to         |
| sender          | Sender name                           |
| sender_function | Sender's function at the club         |
| date            | Message date                          |
| unread          | Whether the message is still unread   |
| body_html       | Full message body as HTML             |
| body_text       | Full message body as plain text       |
| attachments     | List of attachments                   |

The body and attachment attributes are kept out of the recorder.

---
## 🔐 Account

A *diagnostic* entity, and the one entity that is **disabled by default**:
it describes the login rather than the player, and reads the same for every
player on the account. Switch it on under the device's entities if you want
it. Players configured before 0.10.0 keep theirs enabled.

**Entity**

```text
sensor.<player>_account
```

| Property                | Value                     |
| ----------------------- | ------------------------- |
| State                   | Username                  |
| Icon                    | mdi:account-key           |
| user_id                 | User ID                   |
| username                | Username                  |
| email                   | Account email             |
| central_user_id         | PSD central user ID       |
| is_active               | Active account            |
| first_login_date        | First login               |
| last_login_date         | Last login                |
| notifications_view      | Last notifications view   |
| accepted_terms_of_use   | Terms accepted            |
| has_profile_picture     | Profile picture available |
| profile_picture_version | Profile picture version   |
| creation_date           | Account creation date     |
| last_modified_date      | Last modification date    |
| link_status             | PSD link status           |
| external                | External account flag     |
| uid                     | Internal UID              |

---


# 🎬 Actions

| Action | Fields | Effect |
| --- | --- | --- |
| `prosoccerdata.open_message` | `message_id` (required), `member_id` | Fetches the full message, shows it on the Selected Message sensor and returns it as a response. |
| `prosoccerdata.mark_message_read` | `message_id`, `member_id`, `read` | Marks a message read, or unread again with `read: false`. Without `message_id` it uses the message last opened. |
| `prosoccerdata.get_attendance` | `event` (required), `member_id`, `status` | Returns who is down to attend an event, as a response. |

`member_id` is only needed when more than one player is configured. Every
action reports a problem as an error rather than returning an empty answer: an
unknown player or a missing message id is a validation error, and a refusal
from ProSoccerData is raised as such.

```yaml
action: prosoccerdata.mark_message_read
data:
  message_id: 1349
```

`event` takes a calendar uid such as `game-6963` or the bare number. `status`
is `ALL` (the default), `PRESENT` or `ABSENT`; in practice only `ALL` is
accepted by the endpoint that answers.

```yaml
action: prosoccerdata.get_attendance
data:
  event: game-6963
response_variable: attendance
```

Reading an attendance list is the club's own staff view. It works for the
account this integration was set up with, but another club may refuse it; the
action then says so.

---

# 💡 Use Cases

* **Get the family out of the door on time.** The Next Match sensor carries the
  meeting hour and the meeting location, which is usually earlier and elsewhere
  than the kick-off. Announce it, or set a reminder off it.
* **Put the season on a dashboard.** The Last Match sensor carries the season's
  competition matches with their results in `season_matches`, so a single
  template card can show the whole campaign and the record so far.
* **Never miss a club mail again.** The Unread Message Count sensor goes above
  zero, a notification fires with the subject, and `open_message` pulls the
  body into the notification or onto a dashboard.
* **Keep the training week visible.** The calendar entity drops into the
  calendar panel next to school and work, so a moved training shows up where
  the rest of the week already is.
* **Stay on top of the invoices.** Last Payment Status and Total Paid make an
  unpaid request visible without logging in to the club's portal.
* **Track more than one child.** Each player is a separate device with its own
  calendar and sensors, from one ProSoccerData login.

---

# 🧪 Examples

**Announce the meeting time the evening before a match**

```yaml
automation:
  - alias: ProSoccerData - match tomorrow
    triggers:
      - trigger: time
        at: "19:00:00"
    conditions:
      - condition: template
        value_template: >
          {{ as_timestamp(states('sensor.tiziano_perrone_next_match'), 0)
             | timestamp_custom('%Y-%m-%d') == (now() + timedelta(days=1))
             | as_timestamp | timestamp_custom('%Y-%m-%d') }}
    actions:
      - action: notify.family
        data:
          message: >
            {% set m = 'sensor.tiziano_perrone_next_match' %}
            Tomorrow against {{ state_attr(m, 'opponent') }}
            ({{ state_attr(m, 'home_away') }}).
            Be at {{ state_attr(m, 'meeting_location') }}
            at {{ state_attr(m, 'meeting_hour') }}.
```

**Remind everyone an hour before training**

```yaml
automation:
  - alias: ProSoccerData - training in an hour
    triggers:
      - trigger: template
        value_template: >
          {{ 0 < (as_timestamp(states('sensor.tiziano_perrone_next_training'), 0)
                  - as_timestamp(now())) <= 3600 }}
    actions:
      - action: notify.family
        data:
          message: >
            Training at {{ state_attr('sensor.tiziano_perrone_next_training', 'location') }}
            in an hour.
```

**Notify on a new club message, with its text**

```yaml
automation:
  - alias: ProSoccerData - new message
    triggers:
      - trigger: numeric_state
        entity_id: sensor.tiziano_perrone_unread_message_count
        above: 0
    actions:
      - action: prosoccerdata.open_message
        data:
          message_id: >
            {{ state_attr('sensor.tiziano_perrone_unread_message_count',
                          'messages')[0].id }}
        response_variable: mail
      - action: notify.mobile_app_phone
        data:
          title: "{{ mail.subject }}"
          message: "{{ mail.body_html | striptags | truncate(400) }}"
```

**Warn about a payment request that is still open**

```yaml
template:
  - binary_sensor:
      - name: ProSoccerData payment open
        state: >
          {{ states('sensor.tiziano_perrone_last_payment_status') not in
             ['paid', 'unknown', 'unavailable'] }}
        attributes:
          amount: "{{ states('sensor.tiziano_perrone_last_payment_amount') }}"
          due: "{{ state_attr('sensor.tiziano_perrone_last_payment_status', 'due_date') }}"
```

**Read the attendance list for the next match**

```yaml
script:
  prosoccerdata_next_match_attendance:
    sequence:
      - action: prosoccerdata.get_attendance
        data:
          event: >
            {{ state_attr('sensor.tiziano_perrone_upcoming_events', 'games')[0].uid }}
        response_variable: attendance
      - action: persistent_notification.create
        data:
          title: "{{ attendance.count }} players down to attend"
          message: >
            {{ attendance.players | map(attribute='name') | join(', ') }}
```

Entity IDs above are examples — use your own, which follow your Home Assistant
language (see the note under [Available Entities](#-available-entities)).

---

# 🔌 API Data Sources

This integration retrieves data from:

* Schedule (matches, trainings and other events in a date range)
* Previous Matches
* Payment Requests
* Team Information
* Member Profile Information
* Account Information
* Mailbox Inbox Messages
* Unread Mailbox Messages
* Message Detail (on demand, through the open_message action)

---

# ⚠️ Known Limitations

* **Read-mostly.** The only thing written back to ProSoccerData is the read
  flag of a mailbox message. Confirming or declining attendance, entering
  results and editing the schedule are not possible from Home Assistant:
  ProSoccerData does not offer those to a parent account.
* **Attendance lists depend on your club.** `prosoccerdata.get_attendance`
  reads the club's own staff view. It works for some accounts and is refused
  for others; the action says which.
* **No push.** ProSoccerData has no webhook or subscription, so a change shows
  up on the next poll, up to the update interval later.
* **Players are chosen by hand.** An account can see a whole squad, so the
  players to follow are picked in the config flow. A child added to the account
  later shows up after you add them under **Configure** or **Reconfigure**.
* **One entry per account.** The email address is the entry's unique id. A
  second ProSoccerData account is a second entry.
* **Total Paid is not the full history.** It sums the payment requests the
  integration fetched (the ten most recent), not everything ever invoiced.
* **The API is private.** ProSoccerData does not publish or support these
  endpoints, so a change on their side can break a sensor without warning.
  Field names, payment statuses and the shape of an attendance record are all
  taken from what the web client sends.
* **Entity IDs follow your language.** Home Assistant builds an entity ID from
  the translated name the first time it sees an entity, so a Dutch install gets
  `sensor.<player>_volgende_wedstrijd`. Entities that already exist keep the ID
  they were created with.

---

# 🩺 Troubleshooting

**Turn on debug logging first.** Every problem below says more with it on:

```yaml
logger:
  default: info
  logs:
    custom_components.prosoccerdata: debug
```

Or **Settings → Devices & Services → ProSoccerData → ⋮ → Enable debug logging**,
which also gives you a log file to attach to an issue.

| Symptom | What it means | What to do |
| --- | --- | --- |
| Setup fails with *Invalid email or password* | ProSoccerData refused the login. | Sign in at [app.prosoccerdata.com](https://app.prosoccerdata.com) to check the password. The email is the one you sign in with, not a club address. |
| Setup fails with *no players were found* | The login worked but the account has no linked member. | Ask the club to link your account to your child. |
| A repair notification asks you to sign in again | The stored password stopped working. | Click it and enter the new password, or use **Reconfigure**. Nothing has to be removed. |
| Every entity of one player is *unavailable* | That player's refresh fails while the others work. | The log names the call that failed. Other players keep working; it usually clears on its own. |
| Calendar and the two next-event sensors are unavailable, the rest work | The schedule endpoint did not answer for your club. | Nothing to fix locally — the log says why. The match, payment and mailbox sensors are unaffected by design. |
| Team Members is empty | Your account may not be allowed to read the squad, or the member has no team id yet. | Check the `team_id` attribute on the Team sensor. An empty list is the deliberate fallback. |
| `get_attendance` raises *will not let this account read attendance lists* | Your club does not grant a parent account the staff view. | Nothing to fix; the endpoint is the club's own. |
| Entities named in Dutch, or not matching the docs | Entity IDs come from the translated name at creation time. | Rename under **Settings → Devices & Services → Entities**, or use the IDs your install actually made. |
| A dropped player's device is still there | Devices from before 0.10.0 were left behind. | Delete it under the entry's devices; from 0.10.0 on it goes on the reload after the change. |
| No *Update* on the HACS card | HACS has not refreshed its release list. | **⋮ → Update information** on the ProSoccerData card. |

Still stuck: download the diagnostics from the entry's **⋮ → Download
diagnostics** (the password and the account email are redacted) and open an
issue with it and the debug log.

---

# 📝 Notes

* Payment descriptions depend on the data ProSoccerData returns.
* Total paid is calculated from the fetched payment requests, not the full history.
* ProSoccerData's API endpoints are private and may change without notice.
* List attributes (`recent_matches`, `messages`, `payment_requests`) are excluded
  from the recorder, so they never grow your database.
* Entity names follow your Home Assistant language; English and Dutch are shipped.

---

# 🛠️ Releasing

Home Assistant and HACS compare the newest GitHub release tag against what is
installed, so a release is what makes an update appear.

1. Bump `version` in `custom_components/prosoccerdata/manifest.json`
2. Commit and push to `main`

The **Release** workflow then tags `v<version>` and publishes the release. The
**Validate** workflow runs hassfest and the HACS action on every push, pull
request and weekly, so a broken manifest is caught before it ships.

---

# 📄 Project

Repository:

https://github.com/Maffiow/prosoccerdata-ha

Issues and feature requests:

https://github.com/Maffiow/prosoccerdata-ha/issues

ProSoccerData is a product of ProSoccerData NV. This integration is community-built and is not
affiliated with, endorsed by, or supported by ProSoccerData.

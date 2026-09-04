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

The integration asks for:

* ProSoccerData email
* ProSoccerData password
* Which players to track

### Options

**Settings → Devices & Services → ProSoccerData → Configure** lets you change:

| Option          | Default    | Notes                          |
| --------------- | ---------- | ------------------------------ |
| Players         | –          | Add or remove tracked players  |
| Update interval | 30 minutes | Between 5 and 1440 minutes     |

Changing an option reloads the integration straight away.

### Password changes

When ProSoccerData starts refusing the stored password, Home Assistant raises a
repair notification asking you to sign in again. Nothing has to be removed.

---

# 📊 Available Entities

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
| State          | Number of unread inbox messages                  |
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
## 🔐 Account

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


# 🔌 API Data Sources

This integration retrieves data from:

* Schedule (matches, trainings and other events in a date range)
* Previous Matches
* Payment Requests
* Team Information
* Member Profile Information
* Account Information
* Mailbox Inbox Messages (unread state is derived from these)

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

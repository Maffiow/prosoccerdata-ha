# ⚽ ProSoccerData for Home Assistant

Track your ProSoccerData players, matches, payments, team information and account details directly in Home Assistant.

This fork extends the original integration with additional financial, profile, team and account sensors.

---

## ✨ Features

* Multi-player support
* Previous match tracking
* Match history attributes
* Payment request tracking
* Total paid calculation
* Team information
* Member profile information
* Account information
* Mailbox integration
* Inbox and unread message tracking
* HACS compatible

---

## 📦 Installation via HACS

1. Open **HACS**
2. Go to **Integrations**
3. Click **⋮ → Custom repositories**
4. Add:

```text
https://github.com/Maffiow/prosoccerdata-ha
```

5. Select **Integration**
6. Install **ProSoccerData**
7. Restart Home Assistant
8. Add the integration via:

```text
Settings → Devices & Services → Add Integration
```

---

## ⚙️ Configuration

The integration will ask for:

* ProSoccerData email
* ProSoccerData password
* Player selection

---

# 📊 Available Sensors

## ⚽ Last Match

**Entity**

```text
sensor.<player>_last_match
```

| Property         | Value                    |
| ---------------- | ------------------------ |
| State            | YYYY-MM-DD of last match |
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

| Property | Value                           |
| -------- | ------------------------------- |
| State    | Number of unread inbox messages |
| Icon     | mdi:email-alert                 |

---

## 📩 Last Message

**Entity**

```text
sensor.<player>_last_message
```

| Property        | Value                               |
| --------------- | ----------------------------------- |
| State           | Subject of the latest inbox message |
| Icon            | mdi:email-open-outline              |
| id              | Message ID                          |
| sender          | Sender name                         |
| date            | Message date                        |
| first_sentence  | Message preview                     |
| unread          | Unread flag                         |
| has_attachments | Indicates attachments               |
| attachments     | List of attachments                 |
| receivers       | Receiver information                |

---

## 📥 Messages

**Entity**

```text
sensor.<player>_messages
```

| Property           | Value                            |
| ------------------ | -------------------------------- |
| State              | Number of fetched inbox messages |
| Icon               | mdi:email-multiple-outline       |
| total_elements     | Total mailbox messages           |
| number_of_elements | Number of fetched messages       |
| total_pages        | Mailbox pages                    |
| messages           | List of mailbox messages         |

### Message Attributes

Each message contains:

| Property        | Value                |
| --------------- | -------------------- |
| id              | Message ID           |
| subject         | Message subject      |
| sender          | Sender name          |
| date            | Message date         |
| first_sentence  | Message preview      |
| unread          | Read status          |
| deleted         | Deleted flag         |
| draft           | Draft flag           |
| has_attachments | Attachment indicator |
| attachments     | Attachment details   |
| receivers       | Receiver details     |

---

## 📭 Unread Messages

**Entity**

```text
sensor.<player>_unread_messages
```

| Property | Value                        |
| -------- | ---------------------------- |
| State    | Number of unread messages    |
| Icon     | mdi:email-alert-outline      |
| messages | List of unread messages only |

### Unread Message Attributes

Each unread message contains:

| Property        | Value                |
| --------------- | -------------------- |
| id              | Message ID           |
| subject         | Message subject      |
| sender          | Sender name          |
| date            | Message date         |
| first_sentence  | Message preview      |
| unread          | Always true          |
| has_attachments | Attachment indicator |
| attachments     | Attachment details   |
| receivers       | Receiver details     |

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

* Previous Matches
* Payment Requests
* Team Information
* Member Profile Information
* Account Information
* Mailbox Inbox Messages
* Mailbox Unread Messages

---

# 📝 Notes

* Payment descriptions depend on data returned by ProSoccerData.
* Total paid is calculated from fetched payment requests.
* ProSoccerData API endpoints are private and may change without notice.

---

# 🙏 Credits

Original project:

https://github.com/janmeermans/prosoccerdata-ha

Extended fork:

https://github.com/Maffiow/prosoccerdata-ha

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

**State**

* Last played match date

**Attributes**

```yaml
match_start:
match_end:
team:
opponent:
score:
home_away:
competition:
location:
meeting_hour:
attendance_state:
full_title:
recent_matches:
```

---

## 💰 Last Payment Amount

**Entity**

```text
sensor.<player>_last_payment_amount
```

**State**

Latest payment request amount.

**Unit**

```text
EUR
```

---

## ✅ Last Payment Status

**Entity**

```text
sensor.<player>_last_payment_status
```

**Possible states**

```text
paid
pending
overdue
unpaid
```

**Attributes**

```yaml
id:
description:
amount:
sent_date:
due_date:
paid:
```

---

## 💸 Total Paid

**Entity**

```text
sensor.<player>_total_paid
```

**State**

Total amount of all fetched payment requests with status `paid`.

**Unit**

```text
EUR
```

---

## 🔢 Payment Count

**Entity**

```text
sensor.<player>_payment_count
```

**Attributes**

```yaml
payment_requests:
```

---

## 👤 Profile

**Entity**

```text
sensor.<player>_profile
```

**State**

Player full name.

### Attributes

```yaml
member_id:
first_name:
last_name:
nickname:
local_name:
birth_date:
age:
status:
active:
gender:
keeper:
foot:
shirt_number:
language:
uuid:
central_psd_id:
profile_picture_url:
```

---

## 🏆 Team

**Entity**

```text
sensor.<player>_team
```

**State**

Current team name.

### Attributes

```yaml
team_id:
team_ids:
team_name:
team_subcategory:
team_international:
team_international_subcategory:
club_id:
club_international:
role_name:
function_title:
main_sportive_role:
main_sportive_role_id:
```

---

## 🔐 Account

**Entity**

```text
sensor.<player>_account
```

**State**

Username.

### Attributes

```yaml
user_id:
username:
email:
central_user_id:
is_active:
first_login_date:
last_login_date:
notifications_view:
accepted_terms_of_use:
has_profile_picture:
profile_picture_version:
creation_date:
last_modified_date:
link_status:
external:
uid:
```

---

# 🧾 Example Entities

For a player called **Tiziano Perrone**:

```text
sensor.tiziano_perrone_last_match
sensor.tiziano_perrone_last_payment_amount
sensor.tiziano_perrone_last_payment_status
sensor.tiziano_perrone_total_paid
sensor.tiziano_perrone_payment_count
sensor.tiziano_perrone_profile
sensor.tiziano_perrone_team
sensor.tiziano_perrone_account
```

---

# 📋 Example Dashboard

```yaml
type: entities
title: ProSoccerData
entities:
  - sensor.tiziano_perrone_last_match
  - sensor.tiziano_perrone_team
  - sensor.tiziano_perrone_profile
  - sensor.tiziano_perrone_last_payment_amount
  - sensor.tiziano_perrone_last_payment_status
  - sensor.tiziano_perrone_total_paid
  - sensor.tiziano_perrone_payment_count
```

---

# 🔌 API Data Sources

This integration retrieves data from:

* Previous Matches
* Payment Requests
* Team Information
* Member Profile Information
* Account Information

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

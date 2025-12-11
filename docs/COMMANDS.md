# Bot Commands Reference

Complete reference for all MX Player Bot commands and features.

## Table of Contents

- [User Commands](#user-commands)
- [Admin Commands](#admin-commands)
- [Owner Commands](#owner-commands)
- [Interactive Features](#interactive-features)
- [Settings](#settings)

---

## User Commands

### /start

Displays the welcome message and quick start guide.

**Usage:**
```
/start
```

**Response:**
- Welcome message with feature overview
- Quick action buttons (Upload Cookies, Settings, Help)

---

### /help

Shows detailed help information and usage instructions.

**Usage:**
```
/help
```

**Response:**
- Step-by-step usage guide
- Cookie export instructions
- Troubleshooting tips

---

### /auth

Initiates the cookie authentication process.

**Usage:**
```
/auth
```

**Flow:**
1. Bot prompts for cookies.txt file
2. User uploads the file
3. Bot validates Netscape format
4. Cookies are saved for the user

**Requirements:**
- File must be `.txt` extension
- File must be in Netscape cookie format
- Maximum file size: 100KB

**How to Get Cookies:**
1. Install "Get cookies.txt LOCALLY" browser extension
2. Visit mxplayer.in and log in
3. Click the extension icon
4. Export cookies for the site
5. Send the file to the bot

---

### /settings

Opens the user settings menu with inline buttons.

**Usage:**
```
/settings
```

**Options:**

| Setting | Description |
|---------|-------------|
| Output Format | Choose MP4 or MKV container |
| Gofile Token | Set API token for large file uploads |
| Custom Thumbnail | Upload a custom thumbnail image |

---

### /cancel

Cancels the current operation.

**Usage:**
```
/cancel
```

**Cancels:**
- Cookie upload in progress
- Quality selection
- Download confirmation

---

## Admin Commands

Admin commands are available to users listed in `ADMINS` environment variable and the bot owner.

### /stats

Displays bot statistics.

**Usage:**
```
/stats
```

**Shows:**
- Total registered users
- Users active today (last 24 hours)
- Number of banned users
- Server status

**Example Response:**
```
Bot Statistics

Users:
- Total users: 1,234
- Active today: 156
- Banned users: 12

Server:
- Status: Online
- Pyrogram: Running
```

---

### /broadcast

Sends a message to all bot users.

**Usage:**
```
/broadcast <message>
```

Or reply to a message:
```
/broadcast
(as reply to another message)
```

**Parameters:**
- `<message>` - Text message to broadcast

**Example:**
```
/broadcast Hello everyone! New features have been added.
```

**Progress:**
- Shows real-time broadcast progress
- Reports success/failure counts
- Identifies blocked/deactivated users

**Example Response:**
```
Broadcast Complete

Total: 1,234
Success: 1,180
Failed: 24
Blocked/Deactivated: 30
```

---

### /ban

Bans a user from using the bot.

**Usage:**
```
/ban <user_id> [reason]
```

**Parameters:**
- `<user_id>` - Telegram user ID to ban (required)
- `[reason]` - Ban reason (optional)

**Examples:**
```
/ban 123456789
/ban 123456789 Spamming the bot
```

**Notes:**
- Cannot ban admins or owner
- Banned user is notified
- User is silently ignored after ban

---

### /unban

Unbans a previously banned user.

**Usage:**
```
/unban <user_id>
```

**Parameters:**
- `<user_id>` - Telegram user ID to unban

**Example:**
```
/unban 123456789
```

**Notes:**
- User is notified of unban
- User can immediately use the bot again

---

### /banlist

Shows all banned users.

**Usage:**
```
/banlist
```

**Shows:**
- User ID
- Ban reason (truncated)
- Ban date

**Example Response:**
```
Banned Users

- 123456789 | Spamming | 2024-01-15
- 987654321 | No reason | 2024-01-10
- 111222333 | Abuse | 2024-01-08
```

---

### /admins

Lists all bot administrators.

**Usage:**
```
/admins
```

**Example Response:**
```
Bot Admins

Owner: 123456789

Admins:
- 111111111
- 222222222
```

---

## Owner Commands

Owner commands are only available to the user specified in `OWNER_ID`.

### /users

Shows total user count.

**Usage:**
```
/users
```

---

### /addadmin

Adds a new admin (runtime only).

**Usage:**
```
/addadmin <user_id>
```

**Parameters:**
- `<user_id>` - Telegram user ID to promote

**Example:**
```
/addadmin 123456789
```

**Note:** This change is temporary and will reset when the bot restarts. For permanent admins, add to `ADMINS` in `.env`.

---

### /removeadmin

Removes an admin (runtime only).

**Usage:**
```
/removeadmin <user_id>
```

**Parameters:**
- `<user_id>` - Telegram user ID to demote

**Example:**
```
/removeadmin 123456789
```

---

## Interactive Features

### Link Processing

When a user sends an MX Player link, the bot initiates an interactive download flow.

**Supported URL Patterns:**
- `https://www.mxplayer.in/show/...`
- `https://www.mxplayer.in/movie/...`
- `https://mxplayer.in/...`

**Flow:**

1. **Metadata Fetch**
   - Bot shows "Fetching metadata..." status
   - Extracts title, thumbnail, duration, etc.

2. **Quality Selection**
   - Displays available resolutions (1080p, 720p, etc.)
   - User selects preferred quality
   - "Best Quality" option always available

3. **Confirmation**
   - Shows selected options
   - "Start Download" button
   - "Back" to change selection
   - "Cancel" to abort

4. **Download Progress**
   - Visual progress bar
   - Download speed
   - Elapsed time
   - Estimated time remaining

5. **Upload Progress**
   - Visual progress bar
   - Upload speed
   - File size info

6. **Completion**
   - Video sent to chat (if under 2GB)
   - Or Gofile.io link (if over 2GB)

### Quality Selection Keyboard

```
[📺 1080p] [📺 720p]
[📺 480p]  [📺 360p]
[🏆 Best Quality]
[❌ Cancel]
```

### Confirmation Keyboard

```
[⬇️ Start Download]
[⬅️ Back] [❌ Cancel]
```

---

## Settings

### Output Format

Choose the video container format.

**Options:**
- **MP4** - Better compatibility, smaller file size, widely supported
- **MKV** - Better quality preservation, supports multiple audio tracks

**Access:** `/settings` > Output Format

---

### Gofile Token

Set your Gofile.io API token for large file uploads.

**Why needed:**
- Files over 2GB cannot be uploaded to Telegram
- These files are uploaded to Gofile.io instead
- With your token, files go to your account

**How to get token:**
1. Visit [gofile.io](https://gofile.io)
2. Create an account
3. Go to [My Profile](https://gofile.io/myProfile)
4. Copy your API token

**Access:** `/settings` > Gofile Token > Add Token

---

### Custom Thumbnail

Upload a custom thumbnail that will be used for all your video uploads.

**Requirements:**
- Image format: JPG or PNG
- Size: Under 200KB
- Orientation: Square or landscape recommended

**Access:** `/settings` > Thumbnail > Set Thumbnail

---

## Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| "Authentication required" | No cookies uploaded | Use /auth to upload cookies |
| "Video stream not found" | DRM protected or invalid | Try different content |
| "Session expired" | Took too long to respond | Send the link again |
| "Download failed" | Network or server issue | Try again later |
| "Upload failed" | Telegram API issue | Try again |
| "File too large" | Over 2GB without Gofile | Set Gofile token in settings |

---

## Rate Limits

- Progress updates: Every 2-3 seconds
- One active download per user at a time
- Broadcast: 0.05s delay between messages

---

## Tips

1. **Fresh Cookies:** Re-export cookies if downloads fail
2. **Quality:** Lower quality = faster download and smaller file
3. **Large Files:** Set up Gofile token for files over 2GB
4. **Custom Thumbnails:** Set once, applies to all videos
5. **Cancel:** Use /cancel or the Cancel button to stop operations

# MX Player Telegram Bot

A production-ready Telegram bot for downloading videos from MX Player with quality selection, real-time progress tracking, and fast uploads.

## Features

- **Per-User Authentication** - Each user uploads their own cookies for secure access
- **Quality Selection** - Interactive wizard to choose video resolution
- **All Audio Languages** - Automatically downloads all available audio tracks
- **Real-Time Progress** - Visual progress bars with speed and ETA
- **Fast Uploads** - tgcrypto-accelerated uploads via Pyrogram
- **Large File Support** - Files over 2GB automatically upload to Gofile.io
- **User Settings** - Configurable output format, upload mode, custom thumbnails, Gofile API token
- **Admin Panel** - Broadcast messages, view stats, ban/unban users
- **MongoDB Storage** - Persistent user data and settings
- **Show Browser** - Browse and batch download episodes from TV shows
- **File Re-upload** - Upload your own video/document files with Gofile support
- **Detailed Captions** - Rich captions with audio languages, quality, episode info
- **Download Queue** - Smart queue system with max 2 concurrent downloads per user
- **MediaInfo Integration** - Detailed media information with Telegraph links

## New Features

### Download Queue System

The bot now includes a sophisticated download queue system:

- **Per-User Limits** - Maximum 2 concurrent downloads per user
- **Fair Queuing** - Downloads are processed fairly across all users
- **Task IDs** - Each download gets a unique ID (e.g., `DL-A3X9`)
- **Queue Status** - View your queue and task IDs with `/queue`
- **Cancel by ID** - Cancel specific tasks with `/canceltask DL-XXXX`
- **Cancel All** - Cancel all pending downloads with `/cancelqueue`
- **Auto-Processing** - Queue automatically processes when slots become available

### MediaInfo in Telegraph

Each uploaded video includes a link to a Telegraph page containing:

- Raw mediainfo output text
- Complete technical details (codecs, bitrates, streams)
- Audio track information
- Subtitle track information

### Clean Filenames

Files are now named cleanly without URL encoding artifacts:
- Before: `language%20-%20en-IN%20value%20-%20Rummy.mkv`
- After: `Rummy - The Great Gambler (Dual).mkv`

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB
- [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) (download tool)
- FFmpeg/FFprobe (for video metadata)
- MediaInfo CLI (optional, for detailed media information)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/mxdlbot.git
   cd mxdlbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

4. **Run the bot**
   ```bash
   python run.py
   ```

## Configuration

Create a `.env` file with the following variables:

```env
# Telegram API credentials (from https://my.telegram.org)
API_ID=123456
API_HASH=your_api_hash

# Bot token (from @BotFather)
BOT_TOKEN=your_bot_token

# MongoDB connection
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=mxdlbot

# Bot owner (your Telegram user ID)
OWNER_ID=123456789

# Additional admins (comma-separated, optional)
ADMINS=111111,222222
```

## Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and quick start guide |
| `/help` | Detailed help and instructions |
| `/auth` | Upload cookies.txt for authentication |
| `/settings` | Configure output format, upload mode, thumbnail, Gofile token |
| `/cancel` | Cancel current operation |
| `/queue` | View your download queue status with task IDs |
| `/status` | View all active downloads (paginated) |
| `/canceltask <ID>` | Cancel a specific task by ID (e.g., `/canceltask DL-A3X9`) |
| `/cancelqueue` | Cancel all pending downloads in your queue |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/stats` | View bot statistics |
| `/broadcast <message>` | Send message to all users |
| `/ban <user_id> [reason]` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/banlist` | View banned users |
| `/admins` | List all admins |

### Owner Commands

| Command | Description |
|---------|-------------|
| `/users` | View total user count |
| `/addadmin <user_id>` | Add new admin |
| `/removeadmin <user_id>` | Remove admin |

## Usage Guide

### 1. Authentication

Before downloading, users must authenticate with their MX Player cookies:

1. Install a browser extension like "Get cookies.txt LOCALLY"
2. Visit mxplayer.in and log in
3. Export cookies in Netscape format
4. Send `/auth` to the bot and upload the cookies.txt file

### 2. Downloading Videos

1. Send an MX Player video link to the bot
2. Select your preferred video quality
3. Click "Start Download"
4. If you have active downloads, your request is queued automatically
5. Wait for download and upload to complete

### 3. Queue Management

- Each user can have up to 2 concurrent downloads
- Additional downloads are automatically queued
- Each task gets a unique ID (e.g., `DL-A3X9`)
- Use `/queue` to check your queue status and see task IDs
- Use `/canceltask DL-XXXX` to cancel a specific task
- Use `/cancelqueue` to cancel all pending downloads

### 4. Browsing TV Shows

1. Send a show URL (not a specific episode)
2. Browse available seasons
3. Select episodes to download (tap to toggle)
4. Use "Select All" for batch download
5. Click "Download" to queue selected episodes

### 5. Uploading Your Files

- Send any video file (MP4, MKV, AVI, etc.)
- Send documents for re-upload with Gofile support
- Large files (>2GB) automatically go to Gofile.io

### 6. Settings

Use `/settings` to configure:

- **Output Format** - Choose between MP4 and MKV
- **Upload Mode** - Upload as video (with thumbnail) or document (preserves filename)
- **Gofile Token** - Set your Gofile.io API token for large files
- **Custom Thumbnail** - Upload a custom thumbnail for all videos

## Project Structure

```
mxdlbot/
├── run.py              # Main entry point
├── config.py           # Configuration and environment
├── states.py           # FSM state management
├── requirements.txt    # Python dependencies
├── .env.example        # Sample environment file
│
├── core/               # Core components
│   ├── client.py       # Pyrogram client setup
│   ├── database.py     # MongoDB operations
│   └── middlewares.py  # Auth decorators
│
├── plugins/            # Bot command handlers
│   ├── start.py        # /start, /help
│   ├── auth.py         # /auth, cookie handling
│   ├── download.py     # Link processing, quality selection, queue
│   ├── browse.py       # Show browser, episode selection
│   ├── upload.py       # Video/document file uploads
│   ├── settings.py     # User settings
│   └── admin.py        # Admin commands
│
├── services/           # Business logic
│   ├── mx_scraper.py   # MX Player metadata scraping
│   ├── downloader.py   # N_m3u8DL-RE wrapper
│   ├── uploader.py     # Telegram/Gofile uploads
│   ├── thumbnail.py    # Thumbnail management
│   ├── telegraph.py    # Telegraph MediaInfo pages
│   └── queue.py        # Download queue management
│
└── utils/              # Utilities
    ├── formatters.py   # Size/time formatting
    ├── progress.py     # Progress tracking
    ├── mediainfo.py    # MediaInfo extraction
    └── notifications.py # Toast notifications
```

## Dependencies

| Package | Purpose |
|---------|---------|
| pyrogram | Telegram bot framework |
| tgcrypto | Fast upload encryption |
| motor | Async MongoDB driver |
| aiohttp | Async HTTP client |
| aiofiles | Async file operations |
| python-dotenv | Environment variables |
| pymediainfo | Media file analysis |

### System Dependencies

- **N_m3u8DL-RE** - HLS stream downloader ([GitHub](https://github.com/nilaoda/N_m3u8DL-RE))
- **FFmpeg/FFprobe** - Video processing and metadata extraction
- **MediaInfo** - Media file analysis (optional, enhances Telegraph pages)

## Deployment

### Docker (Recommended)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install N_m3u8DL-RE, FFmpeg, and MediaInfo
RUN apt-get update && apt-get install -y ffmpeg mediainfo wget && \
    wget -O /usr/local/bin/N_m3u8DL-RE https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE && \
    chmod +x /usr/local/bin/N_m3u8DL-RE

COPY . .
CMD ["python", "run.py"]
```

### Systemd Service

```ini
[Unit]
Description=MX Player Telegram Bot
After=network.target mongodb.service

[Service]
Type=simple
User=botuser
WorkingDirectory=/path/to/mxdlbot
ExecStart=/usr/bin/python3 run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Common Issues

**"Authentication required" error**
- Upload your cookies.txt using `/auth`
- Make sure cookies are in Netscape format
- Cookies may have expired - re-export from browser

**"Video stream not found" error**
- Content may be DRM protected
- Link may be invalid or expired
- Try a different video

**Download fails or times out**
- Check your internet connection
- N_m3u8DL-RE may not be installed correctly
- Try a lower quality setting

**Upload fails for large files**
- Files over 2GB require Gofile.io
- Set your Gofile API token in `/settings`
- Check available disk space

**Queue not processing**
- Check if you've reached the 2 concurrent download limit
- Use `/queue` to see your queue status
- Use `/cancelqueue` to clear stuck items

### Logs

View logs in the console or configure logging in `run.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for verbose output
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is for educational purposes only. Respect content creators and platform terms of service.

## Acknowledgments

- [Pyrogram](https://pyrogram.org/) - Telegram MTProto API framework
- [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE) - HLS downloader
- [Motor](https://motor.readthedocs.io/) - Async MongoDB driver
- [PyMediaInfo](https://pymediainfo.readthedocs.io/) - MediaInfo wrapper

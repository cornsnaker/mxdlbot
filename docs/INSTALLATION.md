# Installation Guide

Complete guide to setting up MX Player Telegram Bot on various platforms.

## Table of Contents

- [Requirements](#requirements)
- [Step-by-Step Installation](#step-by-step-installation)
- [Platform-Specific Guides](#platform-specific-guides)
- [Configuration](#configuration)
- [Verification](#verification)

---

## Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 1 GB+ |
| Storage | 5 GB | 20 GB+ |
| OS | Linux/Windows/macOS | Ubuntu 22.04 LTS |

### Software Requirements

- **Python 3.10+** - Programming language
- **MongoDB 5.0+** - Database for user data
- **N_m3u8DL-RE** - HLS stream downloader
- **FFmpeg** - Video processing (includes ffprobe)

### Telegram Requirements

- Telegram API credentials from [my.telegram.org](https://my.telegram.org)
- Bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram user ID (use [@userinfobot](https://t.me/userinfobot))

---

## Step-by-Step Installation

### 1. Install Python 3.10+

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip
```

**macOS (with Homebrew):**
```bash
brew install python@3.10
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/)

### 2. Install MongoDB

**Ubuntu/Debian:**
```bash
# Import MongoDB public key
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# Add repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install
sudo apt update
sudo apt install -y mongodb-org

# Start service
sudo systemctl start mongod
sudo systemctl enable mongod
```

**macOS:**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Docker:**
```bash
docker run -d --name mongodb -p 27017:27017 mongo:latest
```

### 3. Install N_m3u8DL-RE

**Linux (x64):**
```bash
# Download latest release
wget https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE_linux-x64.tar.gz

# Extract
tar -xzf N_m3u8DL-RE_linux-x64.tar.gz

# Move to PATH
sudo mv N_m3u8DL-RE /usr/local/bin/
sudo chmod +x /usr/local/bin/N_m3u8DL-RE

# Verify
N_m3u8DL-RE --version
```

**macOS:**
```bash
# Download macOS release
wget https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE_osx-x64.tar.gz

# Extract and install
tar -xzf N_m3u8DL-RE_osx-x64.tar.gz
sudo mv N_m3u8DL-RE /usr/local/bin/
```

**Windows:**
1. Download from [GitHub Releases](https://github.com/nilaoda/N_m3u8DL-RE/releases)
2. Extract to `C:\Program Files\N_m3u8DL-RE\`
3. Add to PATH environment variable

### 4. Install FFmpeg

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract and add to PATH

### 5. Clone and Setup Bot

```bash
# Clone repository
git clone https://github.com/yourusername/mxdlbot.git
cd mxdlbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 6. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your values
nano .env  # or use any text editor
```

### 7. Run the Bot

```bash
python run.py
```

---

## Platform-Specific Guides

### Ubuntu/Debian Server

Complete installation script:

```bash
#!/bin/bash

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.10 python3.10-venv python3-pip ffmpeg wget git

# Install MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl start mongod && sudo systemctl enable mongod

# Install N_m3u8DL-RE
wget https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE_linux-x64.tar.gz
tar -xzf N_m3u8DL-RE_linux-x64.tar.gz
sudo mv N_m3u8DL-RE /usr/local/bin/
sudo chmod +x /usr/local/bin/N_m3u8DL-RE

# Clone and setup bot
git clone https://github.com/yourusername/mxdlbot.git
cd mxdlbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
echo "Edit .env with your credentials, then run: python run.py"
```

### Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install N_m3u8DL-RE
RUN wget -O /usr/local/bin/N_m3u8DL-RE \
    https://github.com/nilaoda/N_m3u8DL-RE/releases/latest/download/N_m3u8DL-RE_linux-x64 \
    && chmod +x /usr/local/bin/N_m3u8DL-RE

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p data/cookies data/downloads data/thumbnails

CMD ["python", "run.py"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    depends_on:
      - mongodb
    volumes:
      - ./data:/app/data

  mongodb:
    image: mongo:7
    restart: unless-stopped
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

**Run with Docker Compose:**
```bash
# Create .env file first
cp .env.example .env
# Edit .env with your values

# Start services
docker-compose up -d

# View logs
docker-compose logs -f bot
```

### Heroku Deployment

**Procfile:**
```
worker: python run.py
```

**runtime.txt:**
```
python-3.11.4
```

Note: Heroku doesn't support N_m3u8DL-RE directly. Use a VPS instead.

### Systemd Service (Linux)

Create `/etc/systemd/system/mxdlbot.service`:

```ini
[Unit]
Description=MX Player Telegram Bot
After=network.target mongodb.service

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/mxdlbot
Environment="PATH=/home/botuser/mxdlbot/venv/bin"
ExecStart=/home/botuser/mxdlbot/venv/bin/python run.py
Restart=always
RestartSec=10

# Security
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/botuser/mxdlbot/data

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable mxdlbot
sudo systemctl start mxdlbot

# Check status
sudo systemctl status mxdlbot

# View logs
sudo journalctl -u mxdlbot -f
```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `API_ID` | Yes | Telegram API ID | `123456` |
| `API_HASH` | Yes | Telegram API Hash | `abc123...` |
| `BOT_TOKEN` | Yes | Bot token from BotFather | `123:ABC...` |
| `MONGO_URI` | Yes | MongoDB connection string | `mongodb://localhost:27017` |
| `DATABASE_NAME` | No | Database name | `mxdlbot` |
| `OWNER_ID` | Yes | Your Telegram user ID | `123456789` |
| `ADMINS` | No | Admin user IDs (comma-separated) | `111,222,333` |
| `BINARY_PATH` | No | Path to N_m3u8DL-RE | `N_m3u8DL-RE` |
| `COOKIES_DIR` | No | Cookies directory | `data/cookies` |
| `DOWNLOAD_DIR` | No | Downloads directory | `data/downloads` |
| `THUMBNAIL_DIR` | No | Thumbnails directory | `data/thumbnails` |

### Getting Telegram Credentials

1. **API_ID and API_HASH:**
   - Visit [my.telegram.org](https://my.telegram.org)
   - Log in with your phone number
   - Go to "API development tools"
   - Create a new application
   - Copy API_ID and API_HASH

2. **BOT_TOKEN:**
   - Message [@BotFather](https://t.me/BotFather)
   - Send `/newbot`
   - Follow the prompts
   - Copy the token

3. **OWNER_ID:**
   - Message [@userinfobot](https://t.me/userinfobot)
   - Copy your user ID

---

## Verification

### Check Installation

```bash
# Check Python version
python3 --version  # Should be 3.10+

# Check MongoDB
mongosh --eval "db.version()"

# Check N_m3u8DL-RE
N_m3u8DL-RE --version

# Check FFmpeg
ffmpeg -version
ffprobe -version
```

### Test Bot Startup

```bash
# Activate virtual environment
source venv/bin/activate

# Run bot
python run.py

# You should see:
# INFO - Starting MX Player Bot...
# INFO - Database connected
# INFO - Bot started as @YourBotUsername
```

### Test Bot Functions

1. Send `/start` to your bot
2. Send `/auth` and upload a test cookies.txt
3. Send an MX Player link
4. Verify quality selection appears

---

## Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
sudo systemctl status mongod

# Check MongoDB logs
sudo tail -f /var/log/mongodb/mongod.log

# Test connection
mongosh --eval "db.adminCommand('ping')"
```

### N_m3u8DL-RE Not Found

```bash
# Check if in PATH
which N_m3u8DL-RE

# If not found, add to PATH
export PATH=$PATH:/path/to/N_m3u8DL-RE

# Or specify in .env
BINARY_PATH=/full/path/to/N_m3u8DL-RE
```

### Permission Issues

```bash
# Fix data directory permissions
chmod -R 755 data/
chown -R $USER:$USER data/
```

### Python Import Errors

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

---

## Next Steps

- Read [COMMANDS.md](COMMANDS.md) for detailed command usage
- Configure [user settings](#configuration)
- Set up [monitoring and logging](#verification)

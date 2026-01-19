FROM python:3.11-slim

WORKDIR /app

# 1. Install system dependencies including 'tar' and 'xz-utils' for extraction
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    wget \
    tar \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Download and Install N_m3u8DL-RE
# We use your specific link provided
RUN wget https://github.com/cornsnaker/N_m3u8DL-RE/releases/download/V0.5.3.1-beta/N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    # Extract the archive
    tar -xzf N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    # Move the binary to the system path
    mv N_m3u8DL-RE /usr/local/bin/ && \
    chmod +x /usr/local/bin/N_m3u8DL-RE && \
    # Clean up the archive to save space
    rm N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz

COPY . .

# Ensure the start script uses the correct command from your example
CMD ["python", "run.py"]

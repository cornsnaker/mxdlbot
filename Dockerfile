FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dependencies, download latest N_m3u8DL-RE, extract, and clean up
RUN apt-get update && apt-get install -y ffmpeg mediainfo wget tar && \
    # Fetch the latest version number from GitHub redirect
    LATEST_VERSION=$(wget -qO- https://github.com/nilaoda/N_m3u8DL-RE/releases/latest | grep -o 'v[0-9.]\+\(-beta\)\?' | head -n 1) && \
    # Download the specific linux-x64 archive
    wget https://github.com/nilaoda/N_m3u8DL-RE/releases/download/${LATEST_VERSION}/N_m3u8DL-RE_${LATEST_VERSION}_linux-x64.tar.gz && \
    # Extract the binary
    tar -xzf N_m3u8DL-RE_${LATEST_VERSION}_linux-x64.tar.gz && \
    # Move the actual binary to bin and make it executable
    mv N_m3u8DL-RE_${LATEST_VERSION}_linux-x64/N_m3u8DL-RE /usr/local/bin/ && \
    chmod +x /usr/local/bin/N_m3u8DL-RE && \
    # Clean up to keep the image small
    rm -rf N_m3u8DL-RE_${LATEST_VERSION}_linux-x64* && \
    apt-get purge -y wget tar && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . .
CMD ["python", "run.py"]

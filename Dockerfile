FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dependencies, download specific N_m3u8DL-RE, extract, and clean up
RUN apt-get update && apt-get install -y ffmpeg mediainfo wget tar && \
    # Using a stable version directly to avoid the 'v2' detection issue
    VERSION="v0.3.0" && \
    wget https://github.com/nilaoda/N_m3u8DL-RE/releases/download/${VERSION}/N_m3u8DL-RE_${VERSION}_linux-x64.tar.gz && \
    tar -xzf N_m3u8DL-RE_${VERSION}_linux-x64.tar.gz && \
    # Move the binary to the system path
    mv N_m3u8DL-RE_${VERSION}_linux-x64/N_m3u8DL-RE /usr/local/bin/ && \
    chmod +x /usr/local/bin/N_m3u8DL-RE && \
    # Cleanup
    rm -rf N_m3u8DL-RE_${VERSION}_linux-x64* && \
    apt-get purge -y wget tar && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . .
CMD ["python", "run.py"]

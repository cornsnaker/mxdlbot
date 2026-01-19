FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dependencies, download specific N_m3u8DL-RE, extract, and clean up
RUN apt-get update && apt-get install -y ffmpeg mediainfo wget tar && \
    wget https://github.com/cornsnaker/N_m3u8DL-RE/releases/download/V0.5.3.1-beta/N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    # Extract the binary from the tar.gz file
    tar -xzf N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    # Move the binary to /usr/local/bin so the system can find it
    mv N_m3u8DL-RE /usr/local/bin/ && \
    chmod +x /usr/local/bin/N_m3u8DL-RE && \
    # Clean up files to keep the image small
    rm N_m3u8DL-RE_V0.5.3.1-beta_linux-x64_20260117.tar.gz && \
    apt-get purge -y wget tar && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY . .
CMD ["python", "run.py"]

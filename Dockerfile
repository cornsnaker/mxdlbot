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

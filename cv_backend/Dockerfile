FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxrender1 libxext6 git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ByteTrack install from source
RUN git clone https://github.com/ifzhang/ByteTrack /tmp/ByteTrack \
    && pip install --no-cache-dir -e /tmp/ByteTrack

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

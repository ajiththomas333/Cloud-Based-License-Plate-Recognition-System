FROM python:3.9-slim

# Force Python logs to stream directly to CloudWatch without buffering
ENV PYTHONUNBUFFERED=1

# 1. Install runtime graphics and multi-threading math libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Download the CPU-only version of PyTorch
RUN pip install --no-cache-dir --prefer-binary torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# 3. Install core application dependencies using pre-compiled binaries
RUN pip install --no-cache-dir --prefer-binary \
    boto3 \
    easyocr \
    opencv-python-headless

# 4. 🔥 Pre-bake the EasyOCR English models into the Docker image layer
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

# 5. Copy your application script
COPY processor.py .

CMD ["python", "processor.py"]

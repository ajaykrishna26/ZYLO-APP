# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libsndfile1 \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create necessary directories and set permissions as root
RUN mkdir -p static/uploads static/selections && chmod -R 777 /app

# Create a user to avoid running as root (Required by HF)
RUN useradd -m -u 1000 user
RUN chown -R user:user /app
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Copy requirements and install dependencies
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY --chown=user . .

# Expose Hugging Face default port
EXPOSE 7860

# Start application using gunicorn
# Calling create_app() as a factory
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "120", "app:create_app()"]

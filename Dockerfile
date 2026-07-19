# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies.
# WeasyPrint (pure-Python PDF renderer) needs Pango + Cairo for font/layout.
# Tesseract is needed for OCR. No binary PDF tool required.
RUN apt-get update && apt-get install -y \
        nginx \
        curl \
        wget \
        tesseract-ocr \
        libtesseract-dev \
        poppler-utils \
        build-essential \
        pkg-config \
        libcairo2 \
        libcairo2-dev \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-liberation \
        fonts-dejavu-core \
        ca-certificates \
        gnupg2 \
        fontconfig \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first to leverage Docker cache
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Copy Nginx configuration
# Ensure we overwrite the default config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy static files to Nginx default directory
COPY frontend /usr/share/nginx/html

# Expose port 80 (Nginx)
EXPOSE 80

# Make the start script executable
RUN chmod +x start.sh

# Start both Nginx and Uvicorn using the start script
CMD ["./start.sh"]
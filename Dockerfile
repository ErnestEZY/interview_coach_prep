# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Nginx, curl, and Tesseract for OCR.
# wkhtmltopdf is not available in some Debian releases via apt, so download
# and install an official .deb if needed (tries several release builds).
RUN apt-get update && apt-get install -y \
        nginx \
        curl \
        tesseract-ocr \
        libtesseract-dev \
        poppler-utils \
        build-essential \
        pkg-config \
        libcairo2-dev \
        ca-certificates \
        gnupg2 \
        fontconfig \
        fonts-liberation \
        xfonts-75dpi \
        xfonts-base \
        libxrender1 \
        libxext6 \
        libx11-6 \
        libfreetype6 \
        && \
        apt-get clean && rm -rf /var/lib/apt/lists/* \
        && \
        set -eux; \
        WKDEB=""; \
        for tag in trixie bookworm bullseye buster; do \
            url="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.${tag}_amd64.deb"; \
            echo "Trying $url"; \
            if curl -fsSL -o /tmp/wkhtml.deb "$url"; then \
                WKDEB=/tmp/wkhtml.deb; break; \
            fi; \
        done; \
        if [ -n "$WKDEB" ]; then \
            dpkg -i "$WKDEB" || apt-get update && apt-get install -y -f; \
            rm -f "$WKDEB"; \
        else \
            echo "Could not find wkhtmltopdf .deb for tried releases; continuing without it."; \
        fi

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
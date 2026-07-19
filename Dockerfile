# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Nginx, curl, and Tesseract for OCR.
# wkhtmltopdf is not available in some Debian releases via apt, so download
# and install the official Linux generic tarball when needed.
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
        libglib2.0-0 \
        libxrandr2 \
        libgdk-pixbuf2.0-0 \
        libnss3 \
        libxcomposite1 \
        libxdamage1 \
        libxss1 \
        libxtst6 \
        libxkbcommon-x11-0 \
        libjpeg-turbo8 \
        libpng16-16 \
        libssl3 \
        xz-utils \
        wget \
        && \
        apt-get clean && rm -rf /var/lib/apt/lists/* \
        && \
        set -eux; \
        command -v curl; \
        command -v nginx; \
        DEB_URL="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb"; \
        wget -q -O /tmp/wkhtml.deb "$DEB_URL"; \
        apt-get install -y /tmp/wkhtml.deb; \
        rm -f /tmp/wkhtml.deb; \
        command -v wkhtmltopdf; \
        wkhtmltopdf --version; \
        if command -v wkhtmltopdf; then ldd "$(command -v wkhtmltopdf)" | grep 'not found' || true; fi

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
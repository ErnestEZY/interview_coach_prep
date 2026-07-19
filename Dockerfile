# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies.
# wkhtmltopdf is NOT in Debian Bookworm's apt repos, so we install the official
# Bookworm .deb from the wkhtmltopdf GitHub releases page.
# Tesseract is needed for OCR. Nginx is the reverse proxy.
RUN apt-get update && apt-get install -y \
        nginx \
        curl \
        wget \
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
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && echo "Base packages installed."

# Install wkhtmltopdf from the official Bookworm .deb package.
# The .deb installs the binary to /usr/local/bin/wkhtmltopdf.
RUN set -eux; \
    DEB_URL="https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb"; \
    wget -q -O /tmp/wkhtml.deb "${DEB_URL}"; \
    apt-get update && apt-get install -y /tmp/wkhtml.deb; \
    rm -f /tmp/wkhtml.deb; \
    apt-get clean && rm -rf /var/lib/apt/lists/*; \
    echo "wkhtmltopdf installed at: $(which wkhtmltopdf)"; \
    wkhtmltopdf --version

# Tell Python exactly where wkhtmltopdf is (the .deb installs to /usr/local/bin).
# This is checked FIRST in pdf_generator.py — no PATH lookup needed.
ENV WKHTMLTOPDF_PATH=/usr/local/bin/wkhtmltopdf

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
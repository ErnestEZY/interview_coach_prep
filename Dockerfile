# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including wkhtmltopdf (available in Bookworm repos),
# Nginx for reverse proxy, and Tesseract for OCR.
RUN apt-get update && apt-get install -y \
        nginx \
        curl \
        wget \
        wkhtmltopdf \
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
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && echo "wkhtmltopdf installed at: $(which wkhtmltopdf)" \
    && wkhtmltopdf --version

# Tell the Python PDF generator exactly where wkhtmltopdf lives.
# This is the standard apt install path on Debian/Ubuntu.
ENV WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf

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
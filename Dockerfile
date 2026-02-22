# Use official Python runtime as a parent image
FROM python:3.9-slim

# Install Nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend requirements first to leverage Docker cache
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project (Backend code)
COPY . .

# Copy Frontend static files to Nginx default directory
RUN rm -rf /usr/share/nginx/html/*
COPY ./frontend/ /usr/share/nginx/html/

# Copy Custom Nginx Configuration
COPY ./nginx.conf /etc/nginx/nginx.conf

# Expose port 80 (Nginx) - Render detects this automatically
EXPOSE 80

# Create a startup script to run both Nginx and Uvicorn
RUN echo "#!/bin/bash" > /start.sh
RUN echo "nginx" >> /start.sh
RUN echo "uvicorn backend.main:app --host 0.0.0.0 --port 8000" >> /start.sh
RUN chmod +x /start.sh

# Run the startup script
CMD ["/start.sh"]

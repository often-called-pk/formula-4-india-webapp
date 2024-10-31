# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install nginx and OpenSSL
RUN apt-get update && apt-get install -y nginx openssl

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Generate a self-signed SSL certificate (for development purposes)
RUN mkdir -p /etc/nginx/ssl \
    && openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/nginx.key -out /etc/nginx/ssl/nginx.crt \
    -subj "/CN=localhost"

# Remove default nginx configuration and copy our custom nginx config
RUN rm /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP (80) and HTTPS (443) ports
EXPOSE 80 443

# Start nginx and the Flask app on port 5000
CMD service nginx start && flask run --host=0.0.0.0 --port=5000

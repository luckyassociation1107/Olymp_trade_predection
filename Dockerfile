FROM python:3.11-slim

WORKDIR /app

# Install DNS tools
RUN apt-get update && apt-get install -y dnsutils && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# CRITICAL: Force the container to use Google DNS
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf

CMD ["python", "bot.py"]

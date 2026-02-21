FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps (safe)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copy requirements first (cache friendly)
COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

# copy project
COPY . .

CMD ["python", "app.py"]

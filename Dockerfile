FROM python:3.11-slim

WORKDIR /app

# Render doesn't need extra DNS tools usually, so keep it lean
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure the app can write to the database
RUN chmod 777 /app

CMD ["python", "bot.py"]

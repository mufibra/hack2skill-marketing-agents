FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize the database
RUN python db/setup.py

EXPOSE 8080

CMD ["python", "api_server.py"]

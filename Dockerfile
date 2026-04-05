FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize the database and load all source data
RUN python db/setup.py && python db/load_data.py

EXPOSE 8080

CMD ["python", "api_server.py"]

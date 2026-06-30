FROM python:3.12-slim

RUN apt-get update -y && \
    apt-get install -y build-essential default-libmysqlclient-dev pkg-config && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8800

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8800"]

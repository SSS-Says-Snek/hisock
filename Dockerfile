# syntax=docker/dockerfile:1

FROM python:3.9-slim-buster
WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN pip install -e .

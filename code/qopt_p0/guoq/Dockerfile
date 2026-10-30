FROM python:3.12-slim-trixie
RUN apt-get update -qq && apt-get install -y -qq git gcc g++ make openjdk-21-jre-headless && rm -rf /var/lib/apt/lists/*
RUN git clone -q https://github.com/qqq-wisc/wisq /wisq && cd /wisq && git checkout -q 97c12a5 && git rev-parse HEAD
WORKDIR /wisq
RUN pip install -q . 2>&1 | tail -20
RUN wisq --help | head -20

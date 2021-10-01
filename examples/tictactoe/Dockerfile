# syntax=docker/dockerfile:1

FROM python:3.9-slim-buster

WORKDIR /serv

RUN pwd
RUN pip3 install hisock

COPY . ./

CMD ["tictactoe_server.py", "Default"]
ENTRYPOINT ["python3", "-u"]
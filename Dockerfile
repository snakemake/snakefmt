FROM python:3.8-alpine
MAINTAINER Michael Hall <michael@mbh.sh>

COPY . /snakefmt
WORKDIR /snakefmt
RUN apk add build-base libffi-dev libressl-dev
RUN wget https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py
RUN python get-poetry.py --yes
RUN source "${HOME}/.poetry/env"
RUN python -m pip install . -v
WORKDIR /
RUN rm -rf /snakefmt

CMD ["python", "-m", "snakefmt"]
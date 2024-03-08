FROM python:3.9
MAINTAINER openHPI Team <openhpi-info@hpi.de>

ENV PYTHONFAULTHANDLER=1 \
PYTHONUNBUFFERED=1 \
PYTHONHASHSEED=random \
PIP_NO_CACHE_DIR=off \
PIP_DISABLE_PIP_VERSION_CHECK=on \
PIP_DEFAULT_TIMEOUT=100 \
POETRY_VERSION=1.8.2


# Install dependencies for opencv
RUN apt-get update \
    && apt-get install -y python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Use eventlet 0.30.2 for now, since wsgi.ALREADY_HANDLED was removed in 0.30.3
RUN pip install "poetry==$POETRY_VERSION"

ENV APP_HOME /transpipe
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

# create the app user
RUN adduser --disabled-password --gecos Transpipe transpipe

# Copy only requirements to cache them in docker layer
COPY poetry.lock pyproject.toml /transpipe/

RUN poetry config virtualenvs.create false \
&& poetry install $(test "$BUILD_TYPE" = production && echo "--no-dev") --no-interaction --no-ansi

COPY pipeline $APP_HOME/

# chown all the files to the app user
RUN chown -R transpipe $APP_HOME

# change to the app user
USER transpipe


ENTRYPOINT ["./entrypoint.sh"]

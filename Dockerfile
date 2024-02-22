FROM python:3.12
MAINTAINER openHPI Team <openhpi-info@hpi.de>

# Install dependencies for opencv
RUN apt-get update \
    && apt-get install -y python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Use eventlet 0.30.2 for now, since wsgi.ALREADY_HANDLED was removed in 0.30.3
RUN pip install --no-cache pipenv gunicorn greenlet eventlet==0.30.2 gunicorn[eventlet]

ENV APP_HOME /transpipe
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

# create the app user
RUN adduser --disabled-password --gecos Transpipe transpipe

COPY Pipfile Pipfile.lock entrypoint.sh $APP_HOME/

RUN pipenv requirements > requirements.txt
RUN pip install --no-cache -r requirements.txt

COPY pipeline $APP_HOME/

# chown all the files to the app user
RUN chown -R transpipe $APP_HOME

# change to the app user
USER transpipe


ENTRYPOINT ["./entrypoint.sh"]

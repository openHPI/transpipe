#!/bin/bash

python manage.py collectstatic --clear --no-input
python manage.py migrate
# Do not overwrite languages saved in Database
# python manage.py loaddata languages
python manage.py createcachetable

# No --preload, as this will cause issues with eventlet
exec gunicorn --workers=3 --worker-class=eventlet --threads=5 pipeline.wsgi -b 0.0.0.0:8080

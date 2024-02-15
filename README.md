# Transcription and Translation Pipeline

## Initial setup
### Database
* Create user ```django_user``` 
* PostgreSQL version 12.3
* Create a database named after the project: ```pipeline```
```
-- Database: pipeline

-- DROP DATABASE pipeline;

CREATE DATABASE pipeline
    WITH 
    OWNER = django_user
    ENCODING = 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;
```

### nginx
* Proxy requests to Django
* Check headers, i.e., `X-Forwarded-Proto` and `Host`
* Validate `ALLOWED_HOST` setting
* Failure might lead to `400 Bad Request` otherwise

### Dependencies
This project uses [Pipenv](https://pipenv.pypa.io/en/latest/) to manage dependencies. 

### Create environment
```
pipenv install
``` 

### Activate environment
```
pipenv shell 
```

## Server administration
### Create Django superuser
```
pipenv run python manage.py createsuperuser
```

### Before you start the server:
```
python manage.py collectstatic --clear --no-input
python manage.py makemigrations
python manage.py migrate
python manage.py loaddata languages
```

### Run the server
```
pipenv run python manage.py runserver 
```

In a local development environment, the serer is available at <http://localhost:8000>

### Platform integration
This project is implemented to integrate deeply with the HPI MOOC platform, and directly uses its internal APIs. Visit https://open.hpi.de/pages/open_source to find out more about the source code of the platform (and other, related Open Source projects).

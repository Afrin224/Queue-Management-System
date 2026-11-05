# Django backend

From this directory:

```sh
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

The frontend in `../frontend/` and JSON API are both served at
**http://127.0.0.1:8000/**. Configuration loads from this directory's `.env`.
`DATABASE_URL` selects Supabase PostgreSQL; leaving it empty selects local
SQLite in `data/`.

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py check_supabase
DATABASE_URL= .venv/bin/python manage.py test queues.tests --noinput
```

`config/` holds Django settings and URL routing. `queues/` contains models,
authentication, API endpoints, queue operations, analytics, migrations, and
integration tests. The legacy password hasher remains necessary for existing
accounts imported from the original application.

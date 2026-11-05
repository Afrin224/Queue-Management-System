# Queueflow

Queue management with an HTML/CSS/JavaScript frontend, a Django backend,
and Supabase PostgreSQL storage.

```text
frontend/                  HTML, CSS, JavaScript, and branding
backend/
  manage.py                Django commands
  config/                  Settings and URL routing
  queues/                  Models, API, queue logic, migrations, and tests
  requirements.txt         Python dependencies
  .env                     Local configuration and database credentials
```

The prepared checkout keeps its Python environment and interpreter in
`backend/.venv/` and `backend/.python/`. These local runtime files are excluded
from Git.

Start from the project root:

```sh
backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000
```

Open **http://127.0.0.1:8000/**. Django serves both the frontend and the API.
The backend saves to Supabase using `DATABASE_URL` in `backend/.env`.

For a fresh checkout, use Python 3.12 or newer:

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

Set the PostgreSQL connection string in `backend/.env`, then run:

```sh
backend/.venv/bin/python backend/manage.py migrate
backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000
```

Check the Supabase connection:

```sh
backend/.venv/bin/python backend/manage.py check_supabase
```

Run backend tests against a separate local SQLite database:

```sh
DATABASE_URL= backend/.venv/bin/python backend/manage.py test queues.tests --noinput
```

MIT licensed.

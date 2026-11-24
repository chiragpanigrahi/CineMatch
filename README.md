# CineMatch — Movie Recommendation Web App

A content-based movie recommender built with Django, pandas, scikit-learn and
Redis. Pick a movie you like and it suggests similar ones by comparing genres
and plot summaries with TF-IDF + cosine similarity — with Redis caching the
result of each lookup.

## Project structure

```
movie_project/
│
├── manage.py
├── requirements.txt
│
├── movie_project/              # Django project config
│   ├── settings.py             # Apps, templates, static files, Redis cache
│   ├── urls.py                 # Root routing → recommender app
│   └── wsgi.py
│
├── recommender/                # The recommendation app
│   ├── views.py                # Handles the search form, calls engine.py
│   ├── urls.py                 # App routing
│   ├── engine.py                # TF-IDF + cosine similarity engine, Redis caching
│   ├── dataset/movies.csv      # 75-movie catalogue (title, year, genres, overview)
│   └── templates/recommender/index.html
│
└── static/css/style.css        # Green & white themed stylesheet
```

## How the recommendations work

1. `engine.py` loads `movies.csv` into a pandas DataFrame once per process.
2. Each movie's genres + overview are combined into a "tags" string (genres
   weighted more heavily than the free-text overview).
3. `TfidfVectorizer` turns those tags into vectors; `cosine_similarity` scores
   every pair of movies against each other.
4. Looking up a title returns the highest-scoring other movies as a ranked
   list, each with a similarity score (0–100%).
5. Each result list is cached in Redis for 6 hours under a `reco:<title>`
   key, so repeat searches skip the recomputation. If Redis isn't reachable,
   the app still works — it just always computes fresh (see
   `IGNORE_EXCEPTIONS` in `settings.py`).

## Setup

**1. Create a virtual environment and install dependencies**

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**2. Start Redis**

```bash
redis-server
```

If you don't want to install Redis locally, Docker works too:

```bash
docker run -d -p 6379:6379 redis
```

(The app still runs without Redis — it just won't cache recommendations
between requests.)

**3. Run migrations** (only needed for Django's built-in admin/auth tables —
the movie catalogue itself is not stored in the database)

```bash
python manage.py migrate
```

**4. Start the dev server**

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/**.

## Configuration

Environment variables (all optional, sensible defaults are baked in):

| Variable             | Default                        | Purpose                          |
|-----------------------|---------------------------------|-----------------------------------|
| `REDIS_URL`           | `redis://127.0.0.1:6379/1`     | Redis connection for the cache    |
| `DJANGO_SECRET_KEY`   | dev key baked into settings.py | Django secret key                 |
| `DJANGO_DEBUG`        | `True`                         | Debug mode toggle                 |
| `DJANGO_ALLOWED_HOSTS`| `*`                             | Comma-separated allowed hosts     |

## Extending it

- **Bigger dataset**: swap `recommender/dataset/movies.csv` for a larger one
  (e.g. MovieLens) — just keep the `title,year,genres,overview` columns, with
  genres pipe-separated (`Action|Sci-Fi`).
- **Posters**: the poster tile is currently a styled initial letter; wiring
  up a real poster API just means swapping the `.selected-card__poster`
  markup in `index.html` for an `<img>`.
- **Persistence**: if you want to store user ratings/watchlists later, that's
  where Django models + the SQLite/Postgres database would come in — the
  current app deliberately keeps the movie catalogue out of the database
  since it's read-only reference data.

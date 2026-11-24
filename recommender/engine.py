"""
recommender/engine.py
======================
A small content-based recommendation engine.

How it works
------------
1. movies.csv is loaded once into a pandas DataFrame.
2. Each movie's genres + overview are combined into a single "tags" string.
3. scikit-learn's TfidfVectorizer turns those tags into vectors.
4. Cosine similarity between every pair of movies gives a similarity matrix.
5. To recommend movies similar to X, we look up X's row in that matrix and
   return the highest-scoring other movies.

The DataFrame and similarity matrix are built once per process (module-level
cache) since recomputing them on every request would be wasteful for a
dataset that never changes at runtime. The *results* of individual
recommendation lookups are additionally cached in Redis via Django's cache
framework, so repeated searches for the same movie skip the similarity
lookup entirely.
"""

import os

import pandas as pd
from django.conf import settings
from django.core.cache import cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATASET_PATH = os.path.join(settings.BASE_DIR, 'recommender', 'dataset', 'movies.csv')

CACHE_TIMEOUT_SECONDS = 60 * 60 * 6  # 6 hours
CACHE_KEY_PREFIX = 'reco'

# Module-level "model" state, built lazily on first use.
_movies_df = None
_cosine_sim = None
_title_to_index = None


def _load_engine():
    """Load the dataset and build the TF-IDF cosine-similarity matrix.

    Runs once per process; subsequent calls are a no-op.
    """
    global _movies_df, _cosine_sim, _title_to_index

    if _movies_df is not None:
        return

    df = pd.read_csv(DATASET_PATH)
    df['genres'] = df['genres'].fillna('')
    df['overview'] = df['overview'].fillna('')

    # Genres carry more signal than free-text overview, so repeat them to
    # give them extra weight in the TF-IDF vocabulary.
    df['tags'] = (
        (df['genres'].str.replace('|', ' ', regex=False) + ' ') * 2
        + df['overview']
    ).str.lower()

    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(df['tags'])

    _cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
    _movies_df = df
    _title_to_index = pd.Series(df.index, index=df['title']).drop_duplicates()


def get_all_movies():
    """Return the full catalogue as a list of dicts, sorted by title."""
    _load_engine()
    records = _movies_df.sort_values('title').to_dict('records')
    return records


def get_all_titles():
    """Return just the titles, sorted alphabetically (for the picker)."""
    _load_engine()
    return sorted(_movies_df['title'].tolist())


def get_movie_details(title):
    """Look up a single movie's details by exact title."""
    _load_engine()
    idx = _title_to_index.get(title)
    if idx is None:
        return None
    row = _movies_df.iloc[idx]
    return _row_to_dict(row)


def get_recommendations(title, top_n=8):
    """Return up to top_n movies most similar to `title`.

    Returns a tuple: (list_of_recommendation_dicts, served_from_cache).
    """
    _load_engine()

    cache_key = f"{CACHE_KEY_PREFIX}:{title.strip().lower()}:{top_n}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True

    idx = _title_to_index.get(title)
    if idx is None:
        return [], False

    sim_scores = list(enumerate(_cosine_sim[idx]))
    sim_scores.sort(key=lambda pair: pair[1], reverse=True)
    # Drop the movie itself (always the highest score, similarity == 1.0)
    sim_scores = [pair for pair in sim_scores if pair[0] != idx][:top_n]

    recommendations = []
    for movie_index, score in sim_scores:
        row = _movies_df.iloc[movie_index]
        rec = _row_to_dict(row)
        rec['score'] = round(float(score) * 100, 1)
        recommendations.append(rec)

    # Best-effort cache write — if Redis is unreachable, IGNORE_EXCEPTIONS
    # in settings.py means this silently does nothing instead of raising.
    cache.set(cache_key, recommendations, timeout=CACHE_TIMEOUT_SECONDS)

    return recommendations, False


def _row_to_dict(row):
    genres = [g for g in row['genres'].split('|') if g]
    year = row.get('year', '')
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = ''
    return {
        'title': row['title'],
        'year': year,
        'genres': genres,
        'overview': row['overview'],
    }

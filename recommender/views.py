from django.shortcuts import render

from . import engine


def index(request):
    """Show the search page, and — once a movie is picked — its recommendations."""
    titles = engine.get_all_titles()
    selected_title = request.GET.get('movie', '').strip()

    context = {
        'titles': titles,
        'selected_title': selected_title,
        'total_movies': len(titles),
    }

    if selected_title:
        selected_movie = engine.get_movie_details(selected_title)
        if selected_movie is None:
            context['error'] = f'"{selected_title}" isn\'t in the catalogue yet. Try picking one from the list.'
        else:
            recommendations, from_cache = engine.get_recommendations(selected_title, top_n=8)
            context.update({
                'selected_movie': selected_movie,
                'recommendations': recommendations,
                'from_cache': from_cache,
            })

    return render(request, 'recommender/index.html', context)

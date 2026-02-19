from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Q
from .models import Movie
from booking.models import Show

def movie_list(request):
    movies = Movie.objects.all()
    
    search_query = request.GET.get('search', '')
    if search_query:
        movies = movies.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(cast__icontains=search_query)
        )
    
    genre = request.GET.get('genre', '')
    if genre:
        movies = movies.filter(genre__iexact=genre)
    
    language = request.GET.get('language', '')
    if language:
        movies = movies.filter(language__iexact=language)
    
    return render(request, 'movies/movie_list.html', {
        'movies': movies
    })


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    shows = Show.objects.filter(movie=movie)

    return render(request, 'movies/movie_detail.html', {
        'movie': movie,
        'shows': shows
    })

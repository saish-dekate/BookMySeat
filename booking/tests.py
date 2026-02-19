from django.test import TestCase
from django.contrib.auth.models import User
from movies.models import Movie
from booking.models import Theatre, Screen, Seat, Show, ShowSeat, Booking
from datetime import date, time, timedelta
from django.utils import timezone

class MovieFilterTestCase(TestCase):
    def setUp(self):
        self.movie1 = Movie.objects.create(
            name="Action Movie",
            rating=4.5,
            cast="Actor A, Actor B",
            description="An action packed movie",
            genre="Action",
            language="English"
        )
        self.movie2 = Movie.objects.create(
            name="Comedy Movie",
            rating=4.0,
            cast="Actor C, Actor D",
            description="A funny comedy",
            genre="Comedy",
            language="Hindi"
        )

    def test_search_filter(self):
        from movies.views import movie_list
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/movies/', {'search': 'Action'})
        response = movie_list(request)
        self.assertEqual(response.status_code, 200)

    def test_genre_filter(self):
        from movies.views import movie_list
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/movies/', {'genre': 'Action'})
        response = movie_list(request)
        self.assertEqual(response.status_code, 200)

    def test_language_filter(self):
        from movies.views import movie_list
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/movies/', {'language': 'Hindi'})
        response = movie_list(request)
        self.assertEqual(response.status_code, 200)


class SeatReservationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.movie = Movie.objects.create(
            name="Test Movie",
            rating=4.5,
            cast="Test Cast",
            genre="Action",
            language="English"
        )
        
        self.theatre = Theatre.objects.create(
            name="Test Theatre",
            city="Test City",
            address="Test Address"
        )
        
        self.screen = Screen.objects.create(
            theatre=self.theatre,
            screen_number=1,
            total_seats=100
        )
        
        self.show = Show.objects.create(
            movie=self.movie,
            screen=self.screen,
            date=date.today(),
            time=time(14, 0),
            price=200
        )
        
        self.seat = ShowSeat.objects.create(
            show=self.show,
            row="A",
            number=1,
            is_booked=False
        )

    def test_seat_reservation(self):
        self.assertFalse(self.seat.is_reserved)
        
        self.seat.reserve(self.user)
        self.assertTrue(self.seat.is_reserved)
        self.assertEqual(self.seat.reserved_by, self.user)
        
    def test_seat_release(self):
        self.seat.reserve(self.user)
        self.seat.release()
        
        self.assertFalse(self.seat.is_reserved)
        self.assertIsNone(self.seat.reserved_by)
        self.assertIsNone(self.seat.reserved_at)

    def test_seat_expiration(self):
        self.seat.reserve(self.user)
        
        past_time = timezone.now() - timedelta(minutes=10)
        self.seat.reserved_at = past_time
        self.seat.save()
        
        self.assertFalse(self.seat.is_reserved)


class TrailerEmbedTestCase(TestCase):
    def test_youtube_watch_url(self):
        movie = Movie.objects.create(
            name="Test Movie",
            rating=4.0,
            cast="Test Cast",
            trailer_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        self.assertIn("embed", movie.trailer_embed_url)
        self.assertIn("dQw4w9WgXcQ", movie.trailer_embed_url)

    def test_youtube_short_url(self):
        movie = Movie.objects.create(
            name="Test Movie 2",
            rating=4.0,
            cast="Test Cast",
            trailer_url="https://youtu.be/dQw4w9WgXcQ"
        )
        self.assertIn("embed", movie.trailer_embed_url)
        self.assertIn("dQw4w9WgXcQ", movie.trailer_embed_url)

    def test_youtube_url_with_params(self):
        movie = Movie.objects.create(
            name="Test Movie 3",
            rating=4.0,
            cast="Test Cast",
            trailer_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=123456"
        )
        self.assertIn("embed", movie.trailer_embed_url)
        self.assertIn("dQw4w9WgXcQ", movie.trailer_embed_url)
        self.assertNotIn("si=", movie.trailer_embed_url)

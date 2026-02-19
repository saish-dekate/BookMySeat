from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from movies.models import Movie


RESERVATION_TIMEOUT_MINUTES = 5


class Theatre(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=50)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return self.name


class Screen(models.Model):
    theatre = models.ForeignKey(Theatre, on_delete=models.CASCADE)
    screen_number = models.IntegerField()
    total_seats = models.IntegerField()

    def __str__(self):
        return f"{self.theatre.name} - Screen {self.screen_number}"


class Seat(models.Model):
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE)
    row = models.CharField(max_length=1)
    seat_number = models.IntegerField()

    def __str__(self):
        return f"{self.row}{self.seat_number}"


class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    screen = models.ForeignKey(Screen, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    price = models.DecimalField(max_digits=6, decimal_places=2)

    def __str__(self):
        return f"{self.movie.name} - {self.date} {self.time}"


class ShowSeat(models.Model):
    show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="seats")
    row = models.CharField(max_length=2)         
    number = models.IntegerField()                
    is_booked = models.BooleanField(default=False)
    reserved_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    reserved_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_reserved(self):
        if self.is_booked:
            return True
        if self.reserved_by and self.reserved_at:
            expiry_time = self.reserved_at + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
            return timezone.now() < expiry_time
        return False
    
    @property
    def reservation_expires_at(self):
        if self.reserved_at:
            return self.reserved_at + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
        return None

    def reserve(self, user):
        self.reserved_by = user
        self.reserved_at = timezone.now()
        self.save()

    def release(self):
        self.reserved_by = None
        self.reserved_at = None
        self.save()

    def __str__(self):
        return f"{self.row}{self.number}"

class Booking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('FAILED', 'Failed'),
    )

    user = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name='ticket_bookings'
)
    show = models.ForeignKey(Show, on_delete=models.CASCADE)
    seats = models.ManyToManyField(ShowSeat)
    total_amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    is_paid = models.BooleanField(default=False)

    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def movie(self):
        return self.show.movie

    @property
    def theater(self):
        return self.show.screen.theatre

    @property
    def show_date(self):
        return self.show.date

    @property
    def show_time(self):
        return self.show.time

    def __str__(self):
        return f"Booking {self.id} - {self.user.username}"

from django.contrib import admin
from .models import Theatre, Screen, Seat, Show, ShowSeat, Booking

admin.site.register(Theatre)
admin.site.register(Screen)
admin.site.register(Seat)
admin.site.register(Show)
admin.site.register(ShowSeat)
admin.site.register(Booking)

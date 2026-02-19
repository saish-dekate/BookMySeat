from django.core.management.base import BaseCommand
from booking.models import Show, ShowSeat, Seat

class Command(BaseCommand):
    help = "Create ShowSeat entries for each show"

    def handle(self, *args, **kwargs):
        for show in Show.objects.all():
            if ShowSeat.objects.filter(show=show).exists():
                self.stdout.write(f"ShowSeats already exist for Show {show.id}")
                continue

            seats = Seat.objects.filter(screen=show.screen)
            for seat in seats:
                ShowSeat.objects.create(
                    show=show,
                    row=seat.row,
                    number=seat.seat_number,
                    is_booked=False
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"ShowSeats created for Show {show.id}")
            )

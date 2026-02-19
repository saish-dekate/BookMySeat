from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from booking.models import ShowSeat, RESERVATION_TIMEOUT_MINUTES

class Command(BaseCommand):
    help = "Release expired seat reservations (runs automatically to clean up stale reservations)"

    def handle(self, *args, **kwargs):
        current_time = timezone.now()
        expired_seats = []
        
        # Find all reserved but not booked seats
        reserved_seats = ShowSeat.objects.filter(
            reserved_by__isnull=False,
            is_booked=False
        )
        
        for seat in reserved_seats:
            expiry_time = seat.reserved_at + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
            if current_time > expiry_time:
                seat.release()
                expired_seats.append(f"{seat.row}{seat.number} (Show: {seat.show.id})")
        
        if expired_seats:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Released {len(expired_seats)} expired reservations:\n" + 
                    "\n".join(f"  - {seat}" for seat in expired_seats)
                )
            )
        else:
            self.stdout.write("No expired reservations found.")
from django.db import transaction
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
from .models import Show, ShowSeat, Booking

import pkg_resources
import razorpay

def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def send_booking_confirmation(booking):
    seats_list = ", ".join([f"{s.row}{s.number}" for s in booking.seats.all()])
    
    subject = f'Booking Confirmed - {booking.show.movie.name} | BookMySeat'
    
    message = f"""
Dear {booking.user.username},

Your booking has been confirmed!

BOOKING DETAILS
===============
Booking ID: #{booking.id}
Movie: {booking.show.movie.name}
Theatre: {booking.show.screen.theatre.name}
Address: {booking.show.screen.theatre.city}

Show Date: {booking.show.date.strftime('%A, %d %B %Y')}
Show Time: {booking.show.time.strftime('%I:%M %p')}

Seats Booked: {seats_list}
Total Amount: ₹{booking.total_amount}

Payment ID: {booking.razorpay_payment_id}

IMPORTANT
=========
- Please arrive at least 15 minutes before the show
- Carry a valid ID proof along with this confirmation
- Seats will be allocated on a first-come, first-served basis

Thank you for choosing BookMySeat!

Happy Watching!

Best Regards,
BookMySeat Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [booking.user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


@login_required
def select_seats(request, show_id):
    from django.utils import timezone
    from datetime import timedelta
    from booking.models import RESERVATION_TIMEOUT_MINUTES
    
    show = get_object_or_404(Show, id=show_id)
    
    all_seats = ShowSeat.objects.filter(show=show).order_by('row', 'number')
    
    current_time = timezone.now()
    for seat in all_seats:
        if seat.reserved_by and not seat.is_booked:
            expiry_time = seat.reserved_at + timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
            if current_time > expiry_time:
                seat.release()
    
    show_seats = ShowSeat.objects.filter(show=show).order_by('row', 'number')

    if request.method == 'POST':
        selected_ids = request.POST.getlist('seats')

        if not selected_ids:
                messages.error(request, "Please select at least one seat.")
                return redirect('select_seats', show_id=show.id)

        with transaction.atomic():
            seats = ShowSeat.objects.select_for_update().filter(
                id__in=selected_ids,
                show=show
            )
            
            for seat in seats:
                if seat.is_booked:
                    messages.error(request, f"Seat {seat.row}{seat.number} is already booked.")
                    return redirect(request.path)
                
                if seat.is_reserved and seat.reserved_by != request.user:
                    messages.error(request, f"Seat {seat.row}{seat.number} is reserved by another user. Please select different seats.")
                    return redirect(request.path)

            if seats.count() != len(selected_ids):
                messages.error(request, "Some seats are no longer available.")
                return redirect('select_seats', show_id=show.id)

            total_amount = seats.count() * show.price

            booking = Booking.objects.create(
                user=request.user,
                show=show,
                total_amount=total_amount,
                status='PENDING',
                is_paid=False
            )

            booking.seats.set(seats)
            
            for seat in seats:
                seat.reserve(request.user)

            request.session['booking_id'] = booking.id
            request.session['booking_created_at'] = timezone.now().isoformat()

            amount_in_paise = int(total_amount * 100)

            razorpay_client = get_razorpay_client()
            razorpay_order = razorpay_client.order.create({
                'amount': amount_in_paise,
                'currency': 'INR',
                'receipt': f'booking_{booking.id}',
                'payment_capture': 1
            })

            booking.razorpay_order_id = razorpay_order.get('id')
            booking.save()

            return render(request, 'booking/payment.html', {
                'booking': booking,
                'razorpay_order': razorpay_order,
                'razorpay_key': settings.RAZORPAY_KEY_ID
            })

    return render(request, 'booking/select_seats.html', {
        'show': show,
        'show_seats': show_seats,
        'reservation_timeout': RESERVATION_TIMEOUT_MINUTES
    })


@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        try:
            payment_id = request.POST.get('razorpay_payment_id')
            order_id = request.POST.get('razorpay_order_id')
            signature = request.POST.get('razorpay_signature')

            booking_id = request.session.get('booking_id')
            if not booking_id:
                messages.error(request, "Invalid booking session.")
                return redirect('movies:movie_list')

            booking = Booking.objects.get(id=booking_id, user=request.user)

            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            }

            try:
                razorpay_client = get_razorpay_client()
                razorpay_client.utility.verify_payment_signature(params_dict)
                booking.is_paid = True
                booking.status = 'CONFIRMED'
                booking.razorpay_payment_id = payment_id
                booking.razorpay_signature = signature
                booking.save()

                for seat in booking.seats.all():
                    seat.is_booked = True
                    seat.reserved_by = None
                    seat.reserved_at = None
                    seat.save()

                send_booking_confirmation(booking)

                if 'booking_id' in request.session:
                    del request.session['booking_id']
                if 'booking_created_at' in request.session:
                    del request.session['booking_created_at']

                messages.success(request, "Payment successful! Your booking is confirmed. Check your email for details.")
                return redirect('profile')

            except Exception as e:
                booking.status = 'FAILED'
                booking.save()
                messages.error(request, f"Payment verification failed: {str(e)}")
                return redirect('select_seats', show_id=booking.show.id)

        except Exception as e:
            messages.error(request, f"Error processing payment: {str(e)}")
            return redirect('movies:movie_list')

    return redirect('movies:movie_list')


@csrf_exempt
def payment_failure(request):
    if request.method == 'POST':
        booking_id = request.session.get('booking_id')
        if booking_id:
            try:
                booking = Booking.objects.get(id=booking_id, user=request.user)
                booking.status = 'FAILED'
                booking.save()
                
                for seat in booking.seats.all():
                    seat.release()
                
                if 'booking_id' in request.session:
                    del request.session['booking_id']
                if 'booking_created_at' in request.session:
                    del request.session['booking_created_at']
            except Booking.DoesNotExist:
                pass

    messages.error(request, "Payment failed. Please try again.")
    return redirect('movies:movie_list')

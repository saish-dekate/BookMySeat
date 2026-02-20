from django.db import transaction
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from .models import Show, ShowSeat, Booking

import razorpay
import qrcode
import io
import base64
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

def run_migrations(request):
    try:
        result = subprocess.run(
            [sys.executable, 'manage.py', 'migrate', '--run-syncdb'],
            capture_output=True,
            text=True,
            cwd='.'
        )
        return HttpResponse(f"Migrations run: {result.stdout}<br>{result.stderr}")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

def test_email(request):
    try:
        send_mail(
            'Test Email from BookMySeat',
            'This is a test email to verify email configuration.',
            settings.DEFAULT_FROM_EMAIL,
            [settings.EMAIL_HOST_USER],
            fail_silently=False,
        )
        return HttpResponse("Test email sent successfully!")
    except Exception as e:
        logger.error(f"Test email failed: {str(e)}")
        return HttpResponse(f"Test email failed: {str(e)}", status=500)


def get_razorpay_client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def send_booking_confirmation(booking, request=None):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        try:
            if not booking.ticket_reference:
                booking.save()
        except Exception as e:
            logger.error(f"Error saving booking: {e}")
            booking.ticket_reference = f"BMS{booking.id}"
            booking.save()
        
        user_email = booking.user.email
        if not user_email:
            logger.error(f"User {booking.user.username} has no email address")
            return False
        
        movie_name = booking.show.movie.name or "Movie"
        theatre_name = booking.show.screen.theatre.name or "Theatre"
        show_date = booking.show.date.strftime('%d %B %Y')
        show_time = booking.show.time.strftime('%I:%M %p')
        
        seats_list = list(booking.seats.all().order_by('row', 'number'))
        seats_display = ", ".join([f"{s.row}{s.number}" for s in seats_list])
        
        subject = f'Booking Confirmed - {movie_name} | BookMySeat'
        
        text_content = f"""Dear {booking.user.username},

Your booking is confirmed!

BOOKING ID: {booking.ticket_reference}

MOVIE: {movie_name}
DATE: {show_date}
TIME: {show_time}

THEATRE: {theatre_name}
SCREEN: {booking.show.screen.screen_number}

SEATS: {seats_display}
TOTAL: Rs. {booking.total_amount}

Payment: Successful

Important: Please arrive 15 minutes before the show and carry valid ID proof.

Thank you for choosing BookMySeat!
"""
        
        html_content = f"""
<html>
<body>
<h1>BOOK MY SEAT</h1>
<h2>Booking Confirmed!</h2>
<p><strong>Booking ID:</strong> {booking.ticket_reference}</p>
<p><strong>Movie:</strong> {movie_name}</p>
<p><strong>Date:</strong> {show_date}</p>
<p><strong>Time:</strong> {show_time}</p>
<p><strong>Theatre:</strong> {theatre_name}</p>
<p><strong>Screen:</strong> {booking.show.screen.screen_number}</p>
<p><strong>Seats:</strong> {seats_display}</p>
<p><strong>Total:</strong> Rs. {booking.total_amount}</p>
<p><strong>Payment:</strong> Successful</p>
<br>
<p><strong>Important:</strong> Please arrive 15 minutes before the show and carry valid ID proof.</p>
<p>Thank you for choosing BookMySeat!</p>
</body>
</html>
"""
        
        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Email sent successfully to {user_email} for booking {booking.ticket_reference}")
        return True
        
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        print(f"Email error: {e}")
        import traceback
        traceback.print_exc()
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

                email_result = send_booking_confirmation(booking)
                
                logger.info(f"Booking {booking.id} - Email function called, result: {email_result}")

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


@csrf_exempt
def check_payment_status(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            order_id = data.get('order_id')
            
            if not order_id:
                return JsonResponse({'status': 'error', 'message': 'No order ID provided'})
            
            booking = Booking.objects.filter(razorpay_order_id=order_id).first()
            
            if not booking:
                return JsonResponse({'status': 'error', 'message': 'Booking not found'})
            
            if booking.is_paid:
                return JsonResponse({
                    'status': 'paid',
                    'payment_id': booking.razorpay_payment_id,
                    'booking_id': booking.id
                })
            else:
                return JsonResponse({'status': 'pending'})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

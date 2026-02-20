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
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
                <div style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); padding: 20px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: bold;">BOOK MY SEAT</h1>
                    <p style="color: #ffffff; margin: 5px 0 0 0; font-size: 14px;">Your Ticket Confirmation</p>
                </div>
                
                <div style="padding: 20px;">
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 20px; border-left: 4px solid #eb3349;">
                        <p style="margin: 0; color: #28a745; font-weight: bold; font-size: 16px;">✓ Booking Confirmed</p>
                        <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 14px;">Thank you for booking with us!</p>
                    </div>
                    
                    <div style="margin-bottom: 20px;">
                        <p style="margin: 0; color: #6c757d; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Booking ID</p>
                        <p style="margin: 5px 0 0 0; color: #212529; font-size: 24px; font-weight: bold;">{booking.ticket_reference}</p>
                    </div>
                    
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #212529; font-size: 18px; border-bottom: 2px solid #eb3349; padding-bottom: 10px;">Movie Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px; width: 40%;">Movie</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px; font-weight: bold;">{booking.show.movie.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px;">Date</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px;">{booking.show.date.strftime('%A, %d %B %Y')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px;">Time</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px;">{booking.show.time.strftime('%I:%M %p')}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #212529; font-size: 18px; border-bottom: 2px solid #eb3349; padding-bottom: 10px;">Theatre Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px; width: 40%;">Theatre</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px; font-weight: bold;">{booking.show.screen.theatre.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px;">Screen</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px;">Screen {booking.show.screen.screen_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px;">Location</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px;">{booking.show.screen.theatre.city}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #212529; font-size: 18px; border-bottom: 2px solid #eb3349; padding-bottom: 10px;">Seat Information</h3>
                        <p style="margin: 0 0 10px 0; color: #212529; font-size: 16px; font-weight: bold;">{seats_display}</p>
                        <p style="margin: 0; color: #6c757d; font-size: 14px;">Total Seats: {len(seats_list)}</p>
                    </div>
                    
                    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 15px 0; color: #212529; font-size: 18px; border-bottom: 2px solid #eb3349; padding-bottom: 10px;">Payment Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px; width: 40%;">Total Amount</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 20px; font-weight: bold;">₹{booking.total_amount}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px;">Payment ID</td>
                                <td style="padding: 8px 0; color: #212529; font-size: 14px;">{booking.razorpay_payment_id or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6c757d; font-size: 14px;">Payment Status</td>
                                <td style="padding: 8px 0; color: #28a745; font-size: 14px; font-weight: bold;">SUCCESS</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="text-align: center; margin-bottom: 20px;">
                        <p style="margin: 0 0 10px 0; color: #6c757d; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Scan at the theatre</p>
                        <img src="data:image/png;base64,{qr_base64}" alt="QR Code" style="width: 150px; height: 150px; border: 2px solid #dee2e6; border-radius: 8px;">
                    </div>
                    
                    <div style="background-color: #fff3cd; border-radius: 8px; padding: 15px; margin-bottom: 20px; border-left: 4px solid #ffc107;">
                        <h4 style="margin: 0 0 10px 0; color: #856404; font-size: 14px; font-weight: bold;">Important Instructions</h4>
                        <ul style="margin: 0; padding-left: 20px; color: #856404; font-size: 13px;">
                            <li style="margin-bottom: 5px;">Please arrive at least 15 minutes before the show</li>
                            <li style="margin-bottom: 5px;">Carry a valid ID proof along with this ticket</li>
                            <li style="margin-bottom: 5px;">This ticket is non-transferable</li>
                            <li style="margin-bottom: 0;">Outside food and beverages are not allowed</li>
                        </ul>
                    </div>
                </div>
                
                <div style="background-color: #212529; padding: 20px; text-align: center;">
                    <p style="color: #ffffff; margin: 0 0 10px 0; font-size: 16px; font-weight: bold;">BOOK MY SEAT</p>
                    <p style="color: #adb5bd; margin: 0; font-size: 12px;">Thank you for choosing BookMySeat!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
Dear {booking.user.username},

Your booking has been confirmed!

BOOKING DETAILS
===============
Booking ID: {booking.ticket_reference}
Movie: {booking.show.movie.name}
Theatre: {booking.show.screen.theatre.name}
Address: {booking.show.screen.theatre.city}

Show Date: {booking.show.date.strftime('%A, %d %B %Y')}
Show Time: {booking.show.time.strftime('%I:%M %p')}

Seats Booked: {seats_display}
Total Amount: ₹{booking.total_amount}

Payment ID: {booking.razorpay_payment_id}

IMPORTANT
=========
- Please arrive at least 15 minutes before the show
- Carry a valid ID proof along with this confirmation

Thank you for choosing BookMySeat!

Best Regards,
BookMySeat Team
        """
        
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [booking.user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Booking confirmation email sent to {booking.user.email} for booking {booking.ticket_reference}")
        return True
    except Exception as e:
        logger.error(f"Email sending failed for booking {getattr(booking, 'ticket_reference', 'N/A')}: {str(e)}")
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

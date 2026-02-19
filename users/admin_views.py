from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate
from booking.models import Booking, Show, ShowSeat, Theatre
from movies.models import Movie
from django.contrib.auth.models import User
from datetime import datetime, timedelta

@staff_member_required
def admin_dashboard(request):
    today = datetime.now().date()
    last_30_days = today - timedelta(days=30)
    
    total_revenue = Booking.objects.filter(
        status='CONFIRMED'
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    today_revenue = Booking.objects.filter(
        status='CONFIRMED',
        created_at__date=today
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    last_30_days_revenue = Booking.objects.filter(
        status='CONFIRMED',
        created_at__date__gte=last_30_days
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    total_bookings = Booking.objects.filter(status='CONFIRMED').count()
    total_tickets_sold = Booking.objects.filter(
        status='CONFIRMED'
    ).aggregate(total=Count('seats'))['total'] or 0
    
    avg_tickets_per_booking = 0
    if total_bookings > 0:
        avg_tickets_per_booking = total_tickets_sold / total_bookings
    
    pending_bookings = Booking.objects.filter(status='PENDING').count()
    failed_bookings = Booking.objects.filter(status='FAILED').count()
    
    total_users = User.objects.filter(is_active=True).count()
    new_users_today = User.objects.filter(
        date_joined__date=today
    ).count()
    
    popular_movies = Booking.objects.filter(
        status='CONFIRMED'
    ).values(
        'show__movie__id',
        'show__movie__name',
        'show__movie__image'
    ).annotate(
        total_bookings=Count('id'),
        total_revenue=Sum('total_amount'),
        tickets_sold=Count('seats')
    ).order_by('-total_bookings')[:10]
    
    busiest_theaters = Booking.objects.filter(
        status='CONFIRMED'
    ).values(
        'show__screen__theatre__id',
        'show__screen__theatre__name',
        'show__screen__theatre__city'
    ).annotate(
        total_bookings=Count('id'),
        total_revenue=Sum('total_amount'),
        tickets_sold=Count('seats')
    ).order_by('-total_bookings')[:10]
    
    revenue_by_date = Booking.objects.filter(
        status='CONFIRMED',
        created_at__date__gte=last_30_days
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        revenue=Sum('total_amount')
    ).order_by('date')
    
    recent_bookings = Booking.objects.select_related(
        'user', 'show__movie', 'show__screen__theatre'
    ).order_by('-created_at')[:20]
    
    low_stock_shows = Show.objects.annotate(
        available_seats=Count('seats', filter=Q(seats__is_booked=False))
    ).filter(available_seats__lt=20).select_related('movie', 'screen__theatre')[:10]
    
    context = {
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'last_30_days_revenue': last_30_days_revenue,
        'total_bookings': total_bookings,
        'total_tickets_sold': total_tickets_sold,
        'avg_tickets_per_booking': avg_tickets_per_booking,
        'pending_bookings': pending_bookings,
        'failed_bookings': failed_bookings,
        'total_users': total_users,
        'new_users_today': new_users_today,
        'popular_movies': popular_movies,
        'busiest_theaters': busiest_theaters,
        'revenue_by_date': list(revenue_by_date),
        'recent_bookings': recent_bookings,
        'low_stock_shows': low_stock_shows,
    }
    
    return render(request, 'admin/dashboard.html', context)

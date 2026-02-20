from django.urls import path
from . import views

app_name = 'booking'

urlpatterns = [
    path('select-seats/<int:show_id>/', views.select_seats, name='select_seats'),
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/failure/', views.payment_failure, name='payment_failure'),
    path('test-email/', views.test_email, name='test_email'),
]

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'health'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    path('password-reset/', views.DemoPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.DemoPasswordResetDoneView.as_view(), name='password_reset_done'),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('health:password_reset_complete')
        ),
        name='password_reset_confirm'
    ),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('register/', views.register, name='register'),
    path('log-data/', views.log_data, name='log_data'),
    path('edit/<int:record_id>/', views.edit_record, name='edit_record'),
    path('delete/<int:record_id>/', views.delete_record, name='delete_record'),
    path('ai-doctor/', views.ai_doctor, name='ai_doctor'),
    path('ai-doctor/insights/', views.ai_doctor_insights_api, name='ai_doctor_insights_api'),
    path('settings/', views.settings_view, name='settings'),
]


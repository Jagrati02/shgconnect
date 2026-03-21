from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from .views import (
    signup, login_view, dashboard,
    shg_dashboard, buyer_dashboard,
    update_shg_profile, update_buyer_profile,
)

urlpatterns = [

    # ── Auth ──
    path('signup/',  signup,     name='signup'),
    path('login/',   login_view, name='login'),
    path('logout/',  LogoutView.as_view(next_page='home'), name='logout'),

    # ── Dashboards ──
    path('dashboard/',        dashboard,       name='dashboard'),
    path('dashboard/shg/',    shg_dashboard,   name='shg_dashboard'),
    path('dashboard/buyer/',  buyer_dashboard, name='buyer_dashboard'),

    # ── Profile updates ──
    path('profile/shg/update/',   update_shg_profile,   name='update_shg_profile'),
    path('profile/buyer/update/', update_buyer_profile, name='update_buyer_profile'),

    # ── Password reset (templates live at registration/) ──
    path('password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html'
        ),
        name='password_reset',
    ),
    path('password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path('reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),
    path('reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
]
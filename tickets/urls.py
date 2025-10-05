from django.urls import path
from . import views
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path('tickets/new/', views.submit_ticket, name='submit_ticket'),
    path('tickets/', views.user_tickets, name='user_tickets'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('agent-dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('ticket/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:ticket_id>/delete/', views.delete_ticket, name='delete_ticket'),
    path('tickets/mark_all_completed/', views.mark_all_completed, name='mark_all_completed'),
    path('tickets/delete_selected/', views.delete_selected, name='delete_selected'),
    path('login/', views.custom_login, name='login'),
    path('handler-dashboard/', views.handler_dashboard, name='handler_dashboard'),
    path('signup/', views.signup, name='signup'),
    path('after-login/', views.after_login, name='after_login'),
    # endpoint for handler to update a ticket (same handler_dashboard handles post)
    path('logout/', views.logout_view, name='logout'),
    

    path('api/tickets/', views.TicketListCreateView.as_view(), name='api-ticket-list'),
    path('api/tickets/<int:pk>/', views.TicketDetailView.as_view(), name='api-ticket-detail'),
    path('api/tickets/<int:pk>/comments/', views.CommentCreateView.as_view(), name='api-ticket-comments'),
    path('api/token/', obtain_auth_token, name='api_token_auth'),
]

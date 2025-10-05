from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User, Group

from .models import Ticket, Comment, Department


def is_admin(user):
    return user.is_superuser


def is_agent(user):
    return user.groups.filter(name='Agent').exists()


def is_handler(user):
    return user.groups.filter(name='Handler').exists()


@login_required
def user_tickets(request):
    """
    Shows tickets created by the current user.
    Completed tickets are still visible; latest first.
    """
    two_minutes_ago = timezone.now() - timedelta(minutes=2)
    tickets = Ticket.objects.filter(
        created_by=request.user
    ).filter(
        models.Q(status__in=['pending', 'in_progress']) |
        models.Q(status='completed', completed_at__gt=two_minutes_ago)
    ).order_by('-created_at')

    return render(request, 'tickets/user_tickets.html', {'tickets': tickets})


@login_required
def submit_ticket(request):
    """
    When user submits a ticket, assign to first user in 'Handler' group if exists.
    Admin does not get assignment permissions — admin only supervises.
    """
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        department_id = request.POST.get('department')  # optional
        department = None
        if department_id:
            try:
                department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                department = None

        # Try to auto-assign to a handler user if available:
        handler_user = None
        handler_group = Group.objects.filter(name='Handler').first()
        if handler_group:
            handler_user = handler_group.user_set.first()

        ticket = Ticket.objects.create(
            title=title,
            description=description,
            created_by=request.user,
            handler=handler_user,
            department=department
        )
        messages.success(request, "Ticket submitted successfully.")
        return redirect('user_tickets')

    departments = Department.objects.all()
    return render(request, 'tickets/submit_ticket.html', {'departments': departments})


@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """
    Admin acts as supervisor.
    Admin can change priority and view status + SLA (on_time or delayed).
    Admin CANNOT assign to agent/handler from this dashboard.
    """
    if request.method == 'POST':
        # Admin can update priority (and optionally department) for review
        ticket_id = request.POST.get('ticket_id')
        priority = request.POST.get('priority')
        department_id = request.POST.get('department')

        ticket = get_object_or_404(Ticket, id=ticket_id)
        if priority:
            ticket.priority = priority

        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                ticket.department = dept
            except Department.DoesNotExist:
                ticket.department = None

        ticket.save()
        messages.success(request, 'Ticket updated by admin (supervisor).')
        return redirect('admin_dashboard')

    tickets = Ticket.objects.all().order_by('-created_at')
    priority_choices = Ticket.PRIORITY_CHOICES
    status_choices = Ticket.STATUS_CHOICES
    departments = Department.objects.all()

    # Annotate SLA status for template convenience (could also use methods)
    return render(request, 'tickets/admin_dashboard.html', {
        'tickets': tickets,
        'priority_choices': priority_choices,
        'status_choices': status_choices,
        'departments': departments,
    })


@login_required
@user_passes_test(is_agent)
def agent_dashboard(request):
    """
    Kept from earlier — if you want to use agent role later.
    """
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        priority = request.POST.get('priority')
        status = request.POST.get('status')

        ticket = get_object_or_404(Ticket, id=ticket_id)
        # ensure that the ticket is assigned to this agent or currently unassigned
        if ticket.agent is None or ticket.agent == request.user:
            ticket.agent = request.user
            if priority:
                ticket.priority = priority
            if status:
                ticket.status = status

            if status == 'completed':
                ticket.completed_at = timezone.now()
            else:
                ticket.completed_at = None

            ticket.save()
            messages.success(request, 'Task updated successfully!')
        else:
            messages.error(request, "You are not allowed to update this ticket.")
        return redirect('agent_dashboard')

    tickets = Ticket.objects.filter(agent=request.user).order_by('-created_at')
    priority_choices = Ticket.PRIORITY_CHOICES
    status_choices = Ticket.STATUS_CHOICES
    return render(request, 'tickets/agent_dashboard.html', {
        'tickets': tickets,
        'priority_choices': priority_choices,
        'status_choices': status_choices,
    })


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    comments = ticket.comments.all().order_by('created_at')
    if request.method == 'POST':
        # adding comment
        text = request.POST.get('comment')
        if text and text.strip():
            Comment.objects.create(ticket=ticket, user=request.user, text=text.strip())
            messages.success(request, 'Comment added.')
        return redirect('ticket_detail', ticket_id=ticket_id)
    return render(request, 'tickets/ticket_detail.html', {'ticket': ticket, 'comments': comments})


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('after_login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def after_login(request):
    user = request.user
    print(f"User: {user.username}, groups: {[g.name for g in user.groups.all()]}")
    if user.is_superuser:
        return redirect('admin_dashboard')
    elif is_agent(user):
        return redirect('agent_dashboard')
    elif is_handler(user):
        return redirect('handler_dashboard')
    else:
        return redirect('submit_ticket')


@login_required
@user_passes_test(is_admin)
def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if ticket.status != 'completed':
        messages.error(request, "Only completed tickets can be deleted.")
        return redirect('admin_dashboard')
    ticket.delete()
    messages.success(request, "Ticket deleted successfully.")
    return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin)
def mark_all_completed(request):
    Ticket.objects.filter(status__in=['pending', 'in_progress']).update(status='completed', completed_at=timezone.now())
    messages.success(request, "All tickets marked as completed.")
    return redirect('admin_dashboard')


@login_required
@user_passes_test(is_admin)
def delete_selected(request):
    if request.method == 'POST':
        ids = request.POST.getlist('selected_tickets')
        tickets = Ticket.objects.filter(id__in=ids, status='completed')
        count = tickets.count()
        tickets.delete()
        messages.success(request, f"Deleted {count} ticket(s) successfully.")
    else:
        messages.error(request, "No tickets selected.")
    return redirect('admin_dashboard')


from django.contrib.auth.forms import AuthenticationForm


def custom_login(request):
    """
    Custom login that supports a 'handler' special login (as in your prior code).
    For handler real accounts, prefer creating a user and adding to 'Handler' group.
    This special-case remains for backward compatibility.
    """
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        role = request.POST.get('role')

        # Special authentication for simple handler username/password
        if role == 'handler':
            username = request.POST.get('username')
            password = request.POST.get('password')
            if username == 'handler' and password == 'handler123':
                request.session['handler_logged_in'] = True
                # If you want a real user, create/get a 'handler' user and log them in:
                handler_user, created = User.objects.get_or_create(username='handler')
                if created:
                    handler_user.set_password('handler123')
                    handler_user.save()
                    # optionally add to Handler group
                    handler_group, _ = Group.objects.get_or_create(name='Handler')
                    handler_group.user_set.add(handler_user)
                # login the handler_user into Django auth
                user = authenticate(username='handler', password='handler123')
                # If authentication fails (because password not set as we just created),
                # force login via backend-less method:
                if user:
                    login(request, user)
                else:
                    # fallback: manually mark session and redirect to handler dashboard
                    request.session['handler_user'] = 'handler'
                return redirect('handler_dashboard')
            else:
                messages.error(request, "Invalid handler credentials")
                return render(request, 'registration/login.html', {'form': form})

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if role == 'agent':
                return redirect('agent_dashboard')
            elif role == 'admin':
                return redirect('admin_dashboard')
            elif is_handler(user):
                return redirect('handler_dashboard')
            else:
                return redirect('submit_ticket')
        else:
            return render(request, 'registration/login.html', {'form': form, 'error': 'Invalid username or password'})
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


@login_required
def handler_dashboard(request):
    """
    The handler sees tickets assigned to them. They can update status/priority and mark completed.
    If a session-based 'handler_logged_in' is used, allow access (compatibility).
    """
    # session-based fallback for special handler login
    if not (request.session.get('handler_logged_in') or is_handler(request.user)):
        # If user is not actually handler, redirect to login
        return redirect('login')

    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        priority = request.POST.get('priority')
        status = request.POST.get('status')

        ticket = get_object_or_404(Ticket, id=ticket_id)

        # Ensure handler can only update tickets assigned to them or unassigned
        if ticket.handler is None or ticket.handler == request.user or request.session.get('handler_user') == 'handler':
            if priority:
                ticket.priority = priority
            if status:
                ticket.status = status

            # if marking completed, set completed_at
            if status == 'completed':
                ticket.completed_at = timezone.now()
            else:
                ticket.completed_at = None

            # ensure this handler is set as handler for the ticket
            if ticket.handler is None and is_handler(request.user):
                ticket.handler = request.user

            ticket.save()
            messages.success(request, 'Ticket updated successfully.')
        else:
            messages.error(request, "You are not allowed to update this ticket.")
        return redirect('handler_dashboard')

    # Tickets for this handler: assigned to them OR unassigned (so they can claim)
    tickets = Ticket.objects.filter(models.Q(handler=request.user) | models.Q(handler__isnull=True)).order_by('-created_at')
    priority_choices = Ticket.PRIORITY_CHOICES
    status_choices = Ticket.STATUS_CHOICES
    return render(request, 'tickets/handler_dashboard.html', {
        'tickets': tickets,
        'priority_choices': priority_choices,
        'status_choices': status_choices,
    })


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect('login')



from django.shortcuts import render
from datetime import datetime

def dashboard(request):
    return render(request, "dashboard/dashboard.html", {"current_year": datetime.now().year})



from rest_framework import generics, permissions
from .models import Ticket, Comment
from .serializers import TicketSerializer, CommentSerializer
from rest_framework import generics, permissions, filters
from .models import Ticket, Comment
from .serializers import TicketSerializer, CommentSerializer


class TicketListCreateView(generics.ListCreateAPIView):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description', 'comments__body']  # Enables search


class TicketDetailView(generics.RetrieveUpdateAPIView):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

class CommentCreateView(generics.CreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        ticket_id = self.kwargs['pk']
        serializer.save(ticket_id=ticket_id, author=self.request.user)

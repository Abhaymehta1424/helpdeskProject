from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Department(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    # agent field retained (in case you want agents later) but not used by admin for assignment now
    agent = models.ForeignKey(User, related_name='assigned_tickets', null=True, blank=True, on_delete=models.SET_NULL)
    handler = models.ForeignKey(User, related_name='handler_tickets', null=True, blank=True, on_delete=models.SET_NULL)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sla_due = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    def __str__(self):
        return self.title

    def is_completed(self):
        return self.status == 'completed'

    def completed_within_hours(self, hours=4):
        """
        Returns True if ticket was completed within `hours` of creation.
        If not completed -> False.
        """
        if not self.completed_at:
            return False
        return (self.completed_at - self.created_at) <= timedelta(hours=hours)

    def sla_status(self):
        """
        Returns 'on_time' if completed within 4 hours,
                'delayed' if completed but not within 4 hours,
                'open' if still not completed.
        """
        if self.status != 'completed':
            # Not completed
            return 'open'
        if self.completed_within_hours(4):
            return 'on_time'
        return 'delayed'


class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.ticket.title}"

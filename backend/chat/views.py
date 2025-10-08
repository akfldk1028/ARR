"""
Views for chat app
"""

from django.shortcuts import render


def index(request):
    """
    Chat interface view
    """
    return render(request, 'chat/index.html')

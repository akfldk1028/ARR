"""
Views for chat app
"""

from django.shortcuts import render


def index(request):
    """
    Chat interface view
    """
    return render(request, 'chat/index.html')


def law_chat(request):
    """
    Law search chat interface view
    법률 검색 전용 채팅 인터페이스
    """
    return render(request, 'chat/law_chat.html')

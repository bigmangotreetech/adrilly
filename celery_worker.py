#!/usr/bin/env python3
"""
Celery worker entry point for background tasks
"""

from app.app import create_app

app, celery = create_app()

if __name__ == '__main__':
    celery.start() 
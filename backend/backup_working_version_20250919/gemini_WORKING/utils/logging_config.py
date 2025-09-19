"""
Logging configuration for Gemini integration
Production-ready logging with structured output
"""

import logging
import logging.config
import os
from pathlib import Path


def setup_logging():
    """Configure logging for the Gemini application"""

    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).parent.parent.parent / 'logs'
    logs_dir.mkdir(exist_ok=True)

    # Logging configuration
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
            'json': {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
            }
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose'
            },
            'file': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': logs_dir / 'gemini.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 5,
                'formatter': 'verbose'
            },
            'error_file': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': logs_dir / 'gemini_errors.log',
                'maxBytes': 10 * 1024 * 1024,  # 10MB
                'backupCount': 3,
                'formatter': 'verbose'
            },
            'performance_file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': logs_dir / 'gemini_performance.log',
                'maxBytes': 5 * 1024 * 1024,  # 5MB
                'backupCount': 3,
                'formatter': 'json' if os.getenv('LOG_FORMAT') == 'json' else 'verbose'
            }
        },
        'loggers': {
            'gemini': {
                'handlers': ['console', 'file'],
                'level': os.getenv('LOG_LEVEL', 'INFO'),
                'propagate': False,
            },
            'gemini.services': {
                'handlers': ['console', 'file', 'error_file'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'gemini.consumers': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False,
            },
            'gemini.performance': {
                'handlers': ['performance_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.channels': {
                'handlers': ['console', 'file'],
                'level': 'WARNING',
                'propagate': False,
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }

    # Apply configuration
    logging.config.dictConfig(LOGGING_CONFIG)

    # Get logger and log initialization
    logger = logging.getLogger('gemini')
    logger.info("Logging configuration initialized")
    logger.info(f"Log files directory: {logs_dir}")


class PerformanceLogger:
    """Logger for performance metrics and monitoring"""

    def __init__(self):
        self.logger = logging.getLogger('gemini.performance')

    def log_request(self, operation: str, duration: float, success: bool, **kwargs):
        """Log request performance metrics"""
        self.logger.info(
            "Request completed",
            extra={
                'operation': operation,
                'duration': duration,
                'success': success,
                **kwargs
            }
        )

    def log_connection(self, action: str, connection_id: str, **kwargs):
        """Log WebSocket connection events"""
        self.logger.info(
            f"WebSocket {action}",
            extra={
                'action': action,
                'connection_id': connection_id,
                **kwargs
            }
        )

    def log_error(self, operation: str, error: str, **kwargs):
        """Log error events"""
        self.logger.error(
            f"Operation failed: {operation}",
            extra={
                'operation': operation,
                'error': error,
                **kwargs
            }
        )


# Global performance logger instance
performance_logger = PerformanceLogger()


class RequestTimer:
    """Context manager for timing requests"""

    def __init__(self, operation: str, **kwargs):
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
        self.success = False

    def __enter__(self):
        import time
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        duration = time.time() - self.start_time
        self.success = exc_type is None

        performance_logger.log_request(
            self.operation,
            duration,
            self.success,
            **self.kwargs
        )

        if exc_type:
            performance_logger.log_error(
                self.operation,
                str(exc_val),
                **self.kwargs
            )
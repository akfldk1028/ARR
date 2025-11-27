"""
Helper functions and constants for parser views.

Common utility functions shared across all view modules.
"""
import os


# Define directories for file operations (same as score.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MERGED_DIR = os.path.join(BASE_DIR, "merged_files")
CHUNK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunks")


# Helper functions for password encoding/decoding (from score.py)
def decode_password(pwd):
    """Decode base64 encoded password."""
    import base64
    sample_string_bytes = base64.b64decode(pwd)
    decoded_password = sample_string_bytes.decode("utf-8")
    return decoded_password


def encode_password(pwd):
    """Encode password to base64."""
    import base64
    data_bytes = pwd.encode('ascii')
    encoded_pwd_bytes = base64.b64encode(data_bytes)
    return encoded_pwd_bytes


# Helper functions for file operations (from score.py)
def sanitize_filename(filename):
    """
    Sanitize the user-provided filename to prevent directory traversal and remove unsafe characters.
    """
    # Remove path separators and collapse redundant separators
    filename = os.path.basename(filename)
    filename = os.path.normpath(filename)
    return filename


def validate_file_path(directory, filename):
    """
    Construct the full file path and ensure it is within the specified directory.
    """
    file_path = os.path.join(directory, filename)
    abs_directory = os.path.abspath(directory)
    abs_file_path = os.path.abspath(file_path)
    # Ensure the file path starts with the intended directory path
    if not abs_file_path.startswith(abs_directory):
        raise ValueError("Invalid file path")
    return abs_file_path


def convert_neo4j_datetime(obj):
    """
    Recursively convert Neo4j DateTime objects to frontend-compatible format.

    Neo4j DateTime objects cannot be directly serialized to JSON by Django's JSON encoder.
    This function converts them to a structure that the frontend's getParsedDate() expects.

    Frontend expects:
    {
        '_DateTime__date': {'_Date__year': ..., '_Date__month': ..., '_Date__day': ...},
        '_DateTime__time': {'_Time__hour': ..., '_Time__minute': ..., '_Time__second': ...}
    }

    Args:
        obj: Any object (dict, list, Neo4jDateTime, or primitive)

    Returns:
        The same structure with DateTime objects converted to frontend-compatible dicts
    """
    from neo4j.time import DateTime as Neo4jDateTime

    if isinstance(obj, Neo4jDateTime):
        # Convert Neo4j DateTime to frontend-compatible structure
        return {
            '_DateTime__date': {
                '_Date__year': obj.year,
                '_Date__month': obj.month,
                '_Date__day': obj.day
            },
            '_DateTime__time': {
                '_Time__hour': obj.hour,
                '_Time__minute': obj.minute,
                '_Time__second': obj.second
            }
        }
    elif isinstance(obj, dict):
        return {k: convert_neo4j_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_neo4j_datetime(item) for item in obj]
    return obj

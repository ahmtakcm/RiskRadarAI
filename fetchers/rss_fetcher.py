from clients.http_client import http_client

def fetch(url: str) -> str:
    return http_client.get_text(url)

import time

RATE_LIMIT_SECONDS = 0.05


def send(message, client):
    time.sleep(RATE_LIMIT_SECONDS)
    return client.send(message)

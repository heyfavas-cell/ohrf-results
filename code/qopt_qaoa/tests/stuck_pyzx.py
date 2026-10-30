import time


def serve(conn) -> None:
    """A PyZX worker that never answers."""
    conn.send("ready")
    conn.recv()
    time.sleep(600)

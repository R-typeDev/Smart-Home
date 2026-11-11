
import platform
import subprocess
from urllib.parse import urlsplit


def ping(host: str, timeout: float = 3.0) -> bool:
    """Check whether a network host responds to ping."""

    if not host:
        return False

    host = str(host).strip()

    if "://" in host:
        host = urlsplit(host).hostname or ""

    host = host.strip()

    if not host:
        return False

    system = platform.system()

    if system == "Windows":
        command = ["ping", "-n", "1", "-w", "1500", host]
    elif system == "Darwin":
        command = ["ping", "-c", "1", host]
    else:
        command = ["ping", "-c", "1", "-W", "2", host]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


import platform
import re
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
        timeout_ms = max(1, int(timeout * 1000))

        command = [
            "ping",
            "-n", "1",
            "-w", str(timeout_ms),
            host,
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout + 1,
                check=False,
            )

            output = result.stdout + result.stderr

            # Windows may return exit code 0 even when the
            # destination is unreachable. A TTL field confirms
            # an actual ICMP echo reply.
            return bool(
                re.search(rb"\bTTL\s*=\s*\d+", output, re.IGNORECASE)
            )

        except (OSError, subprocess.TimeoutExpired):
            return False

    if system == "Darwin":
        command = ["ping", "-c", "1", host]
    else:
        command = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout + 1,
            check=False,
        )
        return result.returncode == 0

    except (OSError, subprocess.TimeoutExpired):
        return False

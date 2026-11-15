
import secrets
import socket
import struct
from ipaddress import IPv4Address


def _encode_netbios_name(name: bytes) -> bytes:
    """Encode a 16-byte NetBIOS name."""

    if len(name) != 16:
        raise ValueError("NetBIOS name must contain 16 bytes")

    encoded = bytearray([32])

    for value in name:
        encoded.append(ord("A") + (value >> 4))
        encoded.append(ord("A") + (value & 0x0F))

    encoded.append(0)

    return bytes(encoded)


def _skip_dns_name(data: bytes, offset: int) -> int:
    """Skip a DNS-encoded name, including compressed names."""

    while offset < len(data):
        length = data[offset]

        if length == 0:
            return offset + 1

        if length & 0xC0 == 0xC0:
            return offset + 2

        if length & 0xC0:
            raise ValueError("Invalid DNS name encoding")

        offset += length + 1

    raise ValueError("Incomplete DNS name")


def _parse_nbstat_response(
    data: bytes,
    transaction_id: int,
) -> str | None:
    """Extract an active NetBIOS computer name from a response."""

    if len(data) < 12:
        return None

    response_id, flags, questions, answers, _, _ = struct.unpack(
        "!HHHHHH", data[:12]
    )

    if response_id != transaction_id:
        return None

    if not flags & 0x8000 or flags & 0x000F:
        return None

    offset = 12

    for _ in range(questions):
        offset = _skip_dns_name(data, offset)
        offset += 4

    for _ in range(answers):
        offset = _skip_dns_name(data, offset)

        if offset + 10 > len(data):
            return None

        record_type, record_class, _, data_length = struct.unpack(
            "!HHIH", data[offset:offset + 10]
        )
        offset += 10

        record_data = data[offset:offset + data_length]
        offset += data_length

        if record_type != 0x0021 or record_class != 0x0001:
            continue

        if not record_data:
            continue

        name_count = record_data[0]
        position = 1
        candidates = []

        for _ in range(name_count):
            if position + 18 > len(record_data):
                break

            raw_name = record_data[position:position + 15]
            suffix = record_data[position + 15]
            name_flags = struct.unpack(
                "!H", record_data[position + 16:position + 18]
            )[0]

            position += 18

            is_group = bool(name_flags & 0x8000)
            is_active = bool(name_flags & 0x0400)

            name = raw_name.decode(
                "ascii", errors="ignore"
            ).strip()

            if not name or is_group or not is_active:
                continue

            priority = 0 if suffix == 0x00 else 1 if suffix == 0x20 else 2
            candidates.append((priority, name))

        if candidates:
            candidates.sort(key=lambda item: item[0])
            return candidates[0][1]

    return None


def resolve_netbios_name(
    ip_address: str,
    timeout: float = 1.5,
) -> str | None:
    """Resolve a device name using NetBIOS Name Service (UDP 137)."""

    try:
        address = str(IPv4Address(ip_address))

        transaction_id = secrets.randbits(16)

        header = struct.pack(
            "!HHHHHH",
            transaction_id,
            0x0000,
            1,
            0,
            0,
            0,
        )

        wildcard_name = b"*" + b"\x00" * 15

        question = (
            _encode_netbios_name(wildcard_name)
            + struct.pack("!HH", 0x0021, 0x0001)
        )

        request = header + question

        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        ) as client:
            client.settimeout(timeout)
            client.sendto(request, (address, 137))

            response, _ = client.recvfrom(4096)

        return _parse_nbstat_response(
            response,
            transaction_id,
        )

    except (
        OSError,
        ValueError,
        struct.error,
        IndexError,
    ):
        return None

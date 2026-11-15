
import socket
import struct
import time
from dataclasses import dataclass


MDNS_ADDRESS = "224.0.0.251"
MDNS_PORT = 5353

RECORD_TYPES = {
    "A": 1,
    "PTR": 12,
    "TXT": 16,
    "AAAA": 28,
    "SRV": 33,
}


@dataclass(frozen=True, slots=True)
class MdnsRecord:
    name: str
    record_type: str
    value: str
    ttl: int


def _encode_dns_name(name: str) -> bytes:
    encoded = bytearray()

    for label in name.rstrip(".").split("."):
        label_bytes = label.encode("utf-8")

        if not label_bytes or len(label_bytes) > 63:
            raise ValueError("Invalid DNS label")

        encoded.append(len(label_bytes))
        encoded.extend(label_bytes)

    encoded.append(0)
    return bytes(encoded)


def _decode_dns_name(
    data: bytes,
    offset: int,
    depth: int = 0,
) -> tuple[str, int]:
    if depth > 10:
        raise ValueError("DNS compression depth exceeded")

    labels = []
    original_end = None

    while offset < len(data):
        length = data[offset]

        if length == 0:
            offset += 1
            break

        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(data):
                raise ValueError("Incomplete DNS pointer")

            pointer = ((length & 0x3F) << 8) | data[offset + 1]

            if original_end is None:
                original_end = offset + 2

            pointed_name, _ = _decode_dns_name(
                data,
                pointer,
                depth + 1,
            )

            if pointed_name:
                labels.extend(pointed_name.split("."))

            offset = original_end
            break

        if length & 0xC0:
            raise ValueError("Invalid DNS label")

        offset += 1

        if offset + length > len(data):
            raise ValueError("Incomplete DNS label")

        labels.append(
            data[offset:offset + length].decode(
                "utf-8",
                errors="replace",
            )
        )

        offset += length

    return ".".join(labels), original_end or offset


def _build_query(name: str, record_type: int) -> bytes:
    header = struct.pack(
        "!HHHHHH",
        0,
        0,
        1,
        0,
        0,
        0,
    )

    question = (
        _encode_dns_name(name)
        + struct.pack("!HH", record_type, 1)
    )

    return header + question


def _parse_response(data: bytes) -> tuple[MdnsRecord, ...]:
    if len(data) < 12:
        return ()

    _, flags, questions, answers, authorities, additional = (
        struct.unpack("!HHHHHH", data[:12])
    )

    if not flags & 0x8000:
        return ()

    offset = 12
    records = []

    try:
        for _ in range(questions):
            _, offset = _decode_dns_name(data, offset)
            offset += 4

        total_records = answers + authorities + additional

        for _ in range(total_records):
            name, offset = _decode_dns_name(data, offset)

            if offset + 10 > len(data):
                break

            record_type, record_class, ttl, data_length = (
                struct.unpack("!HHIH", data[offset:offset + 10])
            )

            offset += 10
            data_offset = offset

            if offset + data_length > len(data):
                break

            record_data = data[offset:offset + data_length]
            offset += data_length

            if ttl == 0 or (record_class & 0x7FFF) != 1:
                continue

            value = None
            type_name = None

            if record_type == 1 and data_length == 4:
                value = socket.inet_ntoa(record_data)
                type_name = "A"

            elif record_type == 28 and data_length == 16:
                value = socket.inet_ntop(
                    socket.AF_INET6,
                    record_data,
                )
                type_name = "AAAA"

            elif record_type == 12:
                value, _ = _decode_dns_name(data, data_offset)
                type_name = "PTR"

            elif record_type == 33 and data_length >= 6:
                priority, weight, port = struct.unpack(
                    "!HHH",
                    record_data[:6],
                )

                target, _ = _decode_dns_name(
                    data,
                    data_offset + 6,
                )

                value = (
                    f"{target} "
                    f"port={port} "
                    f"priority={priority} "
                    f"weight={weight}"
                )
                type_name = "SRV"

            elif record_type == 16:
                items = []
                position = 0

                while position < len(record_data):
                    item_length = record_data[position]
                    position += 1

                    if position + item_length > len(record_data):
                        break

                    item = record_data[position:position + item_length]
                    position += item_length

                    items.append(
                        item.decode("utf-8", errors="replace")
                    )

                value = "; ".join(items)
                type_name = "TXT"

            if value is not None:
                records.append(
                    MdnsRecord(
                        name=name,
                        record_type=type_name,
                        value=value,
                        ttl=ttl,
                    )
                )

        return tuple(records)

    except (ValueError, struct.error, IndexError):
        return ()


def _collect_records(
    client: socket.socket,
    queries: set[tuple[str, int]],
    timeout: float,
) -> set[MdnsRecord]:
    """Send DNS queries and collect multicast responses."""

    if not queries:
        return set()

    for name, record_type in sorted(queries):
        client.sendto(
            _build_query(name, record_type),
            (MDNS_ADDRESS, MDNS_PORT),
        )

    results = set()
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            response, _ = client.recvfrom(9000)
        except socket.timeout:
            continue

        results.update(_parse_response(response))

    return results


def discover_mdns_records(
    timeout: float = 2.0,
) -> tuple[MdnsRecord, ...]:
    """Discover mDNS services, instances and device addresses."""

    results: set[MdnsRecord] = set()

    try:
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP,
        ) as client:
            client.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1,
            )

            client.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_TTL,
                255,
            )

            client.bind(("", 0))
            client.settimeout(0.25)

            # Stage 1: discover available service types.
            stage1 = _collect_records(
                client,
                {
                    ("_services._dns-sd._udp.local", 12),
                },
                timeout,
            )
            results.update(stage1)

            service_types = {
                record.value
                for record in stage1
                if record.record_type == "PTR"
                and record.name == "_services._dns-sd._udp.local"
            }

            # Stage 2: discover service instances.
            service_queries = {
                (service, 12)
                for service in service_types
            }

            stage2 = _collect_records(
                client,
                service_queries,
                timeout,
            )
            results.update(stage2)

            instances = {
                record.value
                for record in stage2
                if record.record_type == "PTR"
            }

            # Stage 3: discover service details.
            detail_queries = set()

            for instance in instances:
                detail_queries.add((instance, 33))
                detail_queries.add((instance, 16))

            stage3 = _collect_records(
                client,
                detail_queries,
                timeout,
            )
            results.update(stage3)

            # Stage 4: discover addresses of service hosts.
            targets = set()

            for record in stage3:
                if record.record_type == "SRV":
                    target = record.value.split()[0]

                    if target.endswith(".local"):
                        targets.add(target)

            address_queries = set()

            for target in targets:
                address_queries.add((target, 1))
                address_queries.add((target, 28))

            stage4 = _collect_records(
                client,
                address_queries,
                timeout,
            )
            results.update(stage4)

    except OSError:
        return ()

    return tuple(
        sorted(
            results,
            key=lambda record: (
                record.name,
                record.record_type,
                record.value,
            ),
        )
    )

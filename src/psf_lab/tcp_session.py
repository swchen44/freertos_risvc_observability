"""Independent protocol oracle for Z0's fixed two-round zero-copy workload."""


def validate_session(packets, metrics, *, workload=None):
    if workload is not None:
        from psf_lab.tcp_workload import validate_workload

        workload = validate_workload(workload)
    request_size = workload["request_bytes"] if workload else 64
    position = 0

    def expect(direction, seq, ack, flags, payload=b""):
        nonlocal position
        if position >= len(packets):
            raise ValueError("Incomplete TCP session")
        p = packets[position]
        position += 1
        if p["direction"] != direction or p["seq"] != seq or p["flags"] & 0x17 != flags:
            raise ValueError("TCP direction, sequence or flags mismatch")
        if p["ack"] != ack:
            raise ValueError("TCP ACK mismatch")
        if p["payload"] != payload:
            raise ValueError("TCP payload mismatch")

    if len(packets) < 3:
        raise ValueError("Missing handshake")
    expect("rx", 1000, 0, 2)
    server = packets[1]["seq"]
    expect("tx", server, 1001, 18)
    server = (server + 1) % 2**32
    client = 1001
    expect("rx", client, server, 16)
    for round_id in range(2):
        request = bytes((round_id + i) % 256 for i in range(request_size))
        expect("rx", client, server, 16, request)
        client += request_size
        for chunk in range(4):
            payload = bytes((i * 17 + round_id + chunk) % 256 for i in range(1460))
            expect("tx", server, client, 16, payload)
            server = (server + 1460) % 2**32
            expect("rx", client, server, 16)
    expect("rx", client, server, 17)
    expect("tx", server, client + 1, 16)
    expect("tx", server, client + 1, 17)
    expect("rx", client + 1, (server + 1) % 2**32, 16)
    if position != len(packets):
        raise ValueError("Unexpected extra packets")
    required = dict(
        request_bytes=2 * request_size,
        acked_bytes=11680,
        retained_bytes=0,
        peak_retained_bytes=1460,
        peer_closed=True,
        active_pcbs=0,
        timewait_pcbs=0,
    )
    if any(type(metrics.get(k)) is not type(v) or metrics[k] != v for k, v in required.items()):
        raise ValueError("Session completion or buffer ownership mismatch")
    before, after = metrics.get("resources_before"), metrics.get("resources_after")
    if before != [0] * 6 or after != before:
        raise ValueError("Resource cleanup mismatch")
    return {"request_bytes": 2 * request_size, "unique_response_bytes": 11680, "packets": position}


def validate_request_pbufs(metrics, mode, *, workload=None):
    """Require callback-observed chain shape; not a claim about wire fragmentation."""
    if mode == "linear" and workload is None:
        if "request_pbufs" in metrics:
            raise ValueError("Unexpected pbuf chain receipt for linear workload")
        return dict(requests=2, nodes=None, empty_nodes=None)
    if mode != "fragmented" and workload is None:
        raise ValueError("Unknown TCP workload")
    parts = [13, 0, 51]
    if workload is not None:
        from psf_lab.tcp_workload import validate_workload

        parts = validate_workload(workload)["request_segments"]
    expected = [
        dict(lengths=parts, totals=[sum(parts[i:]) for i in range(len(parts))]) for _ in range(2)
    ]
    shapes = metrics.get("request_pbufs")
    if workload is not None and isinstance(shapes, list):
        for shape in shapes:
            if not isinstance(shape, dict):
                raise ValueError("Invalid request shape")
            if "addresses" in shape:
                addresses = shape["addresses"]
                if (
                    not isinstance(addresses, list)
                    or len(addresses) != len(parts)
                    or any(
                        type(a) is not int or not 0x80000000 <= a < 0x88000000 for a in addresses
                    )
                ):
                    raise ValueError("Invalid request addresses")
            if set(shape) - {"lengths", "totals", "addresses"}:
                raise ValueError("Unknown request shape fields")
        shapes = [{k: v for k, v in shape.items() if k != "addresses"} for shape in shapes]
    if shapes != expected or any(
        type(value) is not int for shape in shapes for values in shape.values() for value in values
    ):
        raise ValueError("Guest pbuf chain receipt mismatch")
    return dict(requests=2, nodes=2 * len(parts), empty_nodes=2 * parts.count(0))

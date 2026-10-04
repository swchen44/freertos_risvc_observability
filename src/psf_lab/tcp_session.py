"""Independent protocol oracle for Z0's fixed two-round zero-copy workload."""


def validate_session(packets, metrics):
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
        request = bytes((round_id + i) % 256 for i in range(64))
        expect("rx", client, server, 16, request)
        client += 64
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
        request_bytes=128,
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
    return {"request_bytes": 128, "unique_response_bytes": 11680, "packets": position}

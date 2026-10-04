"""Independent IPv4/TCP packet oracle for this bounded, non-fragmented fixture."""

import struct

from psf_lab.tcp_checksum import internet_checksum


def decode_packet(raw):
    if len(raw) < 40 or raw[0] != 0x45 or raw[9] != 6:
        raise ValueError("expected IPv4 without options carrying TCP")
    if int.from_bytes(raw[2:4], "big") != len(raw) or int.from_bytes(raw[6:8], "big") & 0x3FFF:
        raise ValueError("truncated or fragmented IPv4 packet")
    if internet_checksum(raw[:20]) != 0:
        raise ValueError("IPv4 checksum mismatch")
    tcp = raw[20:]
    header_length = (tcp[12] >> 4) * 4
    if not 20 <= header_length <= len(tcp):
        raise ValueError("invalid TCP header length")
    pseudo = raw[12:20] + bytes([0, 6]) + len(tcp).to_bytes(2, "big")
    if internet_checksum(pseudo + tcp) != 0:
        raise ValueError("TCP checksum mismatch")
    src, dst, seq, ack = struct.unpack("!HHII", tcp[:12])
    return dict(
        src=src,
        dst=dst,
        seq=seq,
        ack=ack,
        flags=tcp[13],
        source_ip=list(raw[12:16]),
        destination_ip=list(raw[16:20]),
        payload=bytes(tcp[header_length:]),
    )

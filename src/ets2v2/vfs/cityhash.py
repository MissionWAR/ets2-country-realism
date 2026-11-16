"""Clean-room pure-Python Google CityHash64 1.0.3 (MIT License, commit 00b9287e).

Implements CityHash64 1.0.3 constants and mixing functions without C extensions
or third-party code, matching SCS HashFS v1/v2 path hashing across all length buckets.
"""

from __future__ import annotations

import struct

from ets2v2.vfs.types import normalize_vfs_path

_MASK64 = 0xFFFFFFFFFFFFFFFF
K0 = 0xC3A5C85C97CB3127
K1 = 0xB492B66FBE98F273
K2 = 0x9AE16A3B2F90404F
K3 = 0xC949D7C7509E6557
_KMUL = 0x9DDFEA08EB382D69


def _fetch64(data: bytes, offset: int) -> int:
    value: int = struct.unpack_from("<Q", data, offset)[0]
    return value


def _fetch32(data: bytes, offset: int) -> int:
    value: int = struct.unpack_from("<I", data, offset)[0]
    return value


def _rotate(val: int, shift: int) -> int:
    if shift == 0:
        return val & _MASK64
    return ((val >> shift) | ((val << (64 - shift)) & _MASK64)) & _MASK64


def _shift_mix(val: int) -> int:
    return (val ^ (val >> 47)) & _MASK64


def _hash_len_16(u: int, v: int) -> int:
    a = ((u ^ v) * _KMUL) & _MASK64
    a ^= a >> 47
    b = ((v ^ a) * _KMUL) & _MASK64
    b ^= b >> 47
    return (b * _KMUL) & _MASK64


def _weak_hash_len_32_with_seeds(
    w: int,
    x: int,
    y: int,
    z: int,
    a: int,
    b: int,
) -> tuple[int, int]:
    a = (a + w) & _MASK64
    b = _rotate((b + a + z) & _MASK64, 21)
    c = a
    a = (a + x) & _MASK64
    a = (a + y) & _MASK64
    b = (b + _rotate(a, 44)) & _MASK64
    return ((a + z) & _MASK64, (b + c) & _MASK64)


def _weak_hash_len_32_from_bytes(
    data: bytes,
    offset: int,
    a: int,
    b: int,
) -> tuple[int, int]:
    return _weak_hash_len_32_with_seeds(
        _fetch64(data, offset),
        _fetch64(data, offset + 8),
        _fetch64(data, offset + 16),
        _fetch64(data, offset + 24),
        a,
        b,
    )


def _hash_len_0_to_16(data: bytes) -> int:
    length = len(data)
    if length > 8:
        a = _fetch64(data, 0)
        b = _fetch64(data, length - 8)
        return _hash_len_16(a, _rotate((b + length) & _MASK64, length)) ^ b
    if length >= 4:
        a = _fetch32(data, 0)
        return _hash_len_16((length + (a << 3)) & _MASK64, _fetch32(data, length - 4))
    if length > 0:
        a = data[0]
        b = data[length >> 1]
        c = data[length - 1]
        y = a + (b << 8)
        z = length + (c << 2)
        return (_shift_mix(((y * K2) ^ (z * K3)) & _MASK64) * K2) & _MASK64
    return K2


def _hash_len_17_to_32(data: bytes) -> int:
    length = len(data)
    a = (_fetch64(data, 0) * K1) & _MASK64
    b = _fetch64(data, 8)
    c = (_fetch64(data, length - 8) * K2) & _MASK64
    d = (_fetch64(data, length - 16) * K0) & _MASK64
    return _hash_len_16(
        (_rotate((a - b) & _MASK64, 43) + _rotate(c, 30) + d) & _MASK64,
        (a + _rotate(b ^ K3, 20) - c + length) & _MASK64,
    )


def _hash_len_33_to_64(data: bytes) -> int:
    length = len(data)
    z = _fetch64(data, 24)
    a = (_fetch64(data, 0) + ((length + _fetch64(data, length - 16)) * K0)) & _MASK64
    b = _rotate((a + z) & _MASK64, 52)
    c = _rotate(a, 37)
    a = (a + _fetch64(data, 8)) & _MASK64
    c = (c + _rotate(a, 7)) & _MASK64
    a = (a + _fetch64(data, 16)) & _MASK64
    vf = (a + z) & _MASK64
    vs = (b + _rotate(a, 31) + c) & _MASK64

    a = (_fetch64(data, 16) + _fetch64(data, length - 32)) & _MASK64
    z = _fetch64(data, length - 8)
    b = _rotate((a + z) & _MASK64, 52)
    c = _rotate(a, 37)
    a = (a + _fetch64(data, length - 24)) & _MASK64
    c = (c + _rotate(a, 7)) & _MASK64
    a = (a + _fetch64(data, length - 16)) & _MASK64
    wf = (a + z) & _MASK64
    ws = (b + _rotate(a, 31) + c) & _MASK64

    r = _shift_mix((((vf + ws) * K2) + ((wf + vs) * K0)) & _MASK64)
    return (_shift_mix(((r * K0) + vs) & _MASK64) * K2) & _MASK64


def cityhash64(data: bytes) -> int:
    """Compute the 64-bit Google CityHash 1.0.3 digest of ``data``."""
    length = len(data)
    if length <= 16:
        return _hash_len_0_to_16(data)
    if length <= 32:
        return _hash_len_17_to_32(data)
    if length <= 64:
        return _hash_len_33_to_64(data)

    x = _fetch64(data, length - 40)
    y = (_fetch64(data, length - 16) + _fetch64(data, length - 56)) & _MASK64
    z = _hash_len_16(
        (_fetch64(data, length - 48) + length) & _MASK64,
        _fetch64(data, length - 24),
    )
    v = _weak_hash_len_32_from_bytes(data, length - 64, length, z)
    w = _weak_hash_len_32_from_bytes(data, length - 32, (y + K1) & _MASK64, x)
    x = (x * K1 + _fetch64(data, 0)) & _MASK64

    pos = 0
    remaining = (length - 1) & ~63
    while remaining > 0:
        x = (_rotate((x + y + v[0] + _fetch64(data, pos + 8)) & _MASK64, 37) * K1) & _MASK64
        y = (_rotate((y + v[1] + _fetch64(data, pos + 48)) & _MASK64, 42) * K1) & _MASK64
        x ^= w[1]
        y = (y + v[0] + _fetch64(data, pos + 40)) & _MASK64
        z = (_rotate((z + w[0]) & _MASK64, 33) * K1) & _MASK64
        v = _weak_hash_len_32_from_bytes(data, pos, (v[1] * K1) & _MASK64, (x + w[0]) & _MASK64)
        w = _weak_hash_len_32_from_bytes(
            data,
            pos + 32,
            (z + w[1]) & _MASK64,
            (y + _fetch64(data, pos + 16)) & _MASK64,
        )
        z, x = x, z
        pos += 64
        remaining -= 64

    return _hash_len_16(
        (_hash_len_16(v[0], w[0]) + _shift_mix(y) * K1 + z) & _MASK64,
        (_hash_len_16(v[1], w[1]) + x) & _MASK64,
    )


def hash_vfs_path(path: str, salt: int = 0) -> int:
    """Normalize a VFS path and compute its SCS HashFS CityHash64 1.0.3 digest."""
    if salt < 0:
        raise ValueError(f"HashFS salt must be non-negative, got {salt}")
    normalized = normalize_vfs_path(path, allow_empty=True)
    payload = normalized.encode("utf-8")
    if salt != 0:
        payload = str(salt).encode("ascii") + payload
    return cityhash64(payload)

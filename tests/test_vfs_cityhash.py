"""Clean-room CityHash64 1.0.3 (MIT) and VFS path-hashing tests."""

from __future__ import annotations

import pytest

from ets2_realism.vfs.cityhash import K0, K1, K2, K3, cityhash64, hash_vfs_path
from ets2_realism.vfs.types import normalize_vfs_path


def test_cityhash64_103_constants() -> None:
    assert K0 == 0xC3A5C85C97CB3127
    assert K1 == 0xB492B66FBE98F273
    assert K2 == 0x9AE16A3B2F90404F
    assert K3 == 0xC949D7C7509E6557
    assert cityhash64(b"") == K2


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        # Length 0
        (b"", 0x9AE16A3B2F90404F),
        # Length 1..3 (uses k3 in 1.0.3)
        (b"a", 0x2420662CD003ACFA),
        (b"ui", 0x9EC7C23EFDBECBE3),
        (b"def", 0x2C6F469EFB31C45A),
        # Length 4..7
        (b"font", 0x35E6BE80983EE96B),
        (b"1234567", 0x9901635F0CDC460F),
        # Length 8..16
        (b"12345678", 0x639BF6EF3EE1EE2F),
        (b"def/country.sii", 0x80FC9D201BD931C8),
        (b"0123456789abcdef", 0x099D21E99DAC3317),
        # Length 17..32 (uses 1.0.3 HashLen17to32 with k3)
        (b"0123456789abcdef0", 0x4C46D90B3F165AEB),
        (b"def/country/iceland.sui", 0xDC84E5A185BC2F78),
        (b"0123456789abcdef0123456789abcdef", 0x186C0E3FFD9476F6),
        # Length 33..64 (uses 1.0.3 HashLen33to64)
        (b"0123456789abcdef0123456789abcdef0", 0xAAC0E9E7A646DFB7),
        (b"def/country/germany/speed_limits.sii", 0x3A6F2927B8118C1E),
        (
            b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            0x265291BF4FC91651,
        ),
        # Length >64
        (
            b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0",
            0xBDD44C77CDCFEBD5,
        ),
        (
            b"def/vehicle/truck_company_uk/oversize/scania_r2016_8x4_high_730.sii",
            0x1BFE430F9BDD743E,
        ),
        (b"x" * 129, 0x2E395A81134A3366),
    ],
)
def test_cityhash64_all_length_buckets(payload: bytes, expected: int) -> None:
    digest = cityhash64(payload)
    assert digest == expected
    assert 0 <= digest <= 0xFFFFFFFFFFFFFFFF


def test_cityhash64_differs_from_cityhash11_on_1_to_32_buckets() -> None:
    # CityHash 1.1 replaced k3 in HashLen0to16(1..3) and rewrote HashLen17to32;
    # confirm our implementation stays locked to 1.0.3 (00b9287e) SCS HashFS vectors.
    assert cityhash64(b"def") == 0x2C6F469EFB31C45A
    assert cityhash64(b"def/country/iceland.sui") == 0xDC84E5A185BC2F78


def test_hash_vfs_path_normalization_and_utf8() -> None:
    assert hash_vfs_path("") == K2
    assert hash_vfs_path("/") == K2
    assert hash_vfs_path("\\") == K2

    expected = 0xDC84E5A185BC2F78
    assert hash_vfs_path("def/country/iceland.sui") == expected
    assert hash_vfs_path("/def/country/iceland.sui") == expected
    assert hash_vfs_path("\\def\\\\country\\iceland.sui") == expected
    assert hash_vfs_path("def//country/./iceland.sui") == expected

    utf8_path = "/def\\café//tést.sui"
    assert normalize_vfs_path(utf8_path) == "def/café/tést.sui"
    assert hash_vfs_path(utf8_path) == 0x5555B2A22E0124DC


def test_hash_vfs_path_salted() -> None:
    assert hash_vfs_path("def/country.sii", salt=42) == 0x4315D8B40DAEA27F
    assert hash_vfs_path("/def\\country.sii", salt=42) == cityhash64(b"42def/country.sii")
    assert hash_vfs_path("", salt=7) == 0x4D3FEE42FEEE34F3
    with pytest.raises(ValueError, match="salt"):
        hash_vfs_path("def/country.sii", salt=-1)


@pytest.mark.parametrize("bad_path", ["../secret.sii", "def/../secret.sii", "def/foo\x00bar.sii"])
def test_normalize_vfs_path_rejects_traversal_and_nul(bad_path: str) -> None:
    with pytest.raises(ValueError):
        normalize_vfs_path(bad_path)
    with pytest.raises(ValueError):
        hash_vfs_path(bad_path)

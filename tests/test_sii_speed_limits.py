"""Red-first tests for interleaved country_speed_limit parsing and surgical patching."""

from __future__ import annotations

import pytest

from ets2_realism.sii.hygiene import serialize_sii_text
from ets2_realism.sii.speed_limits import (
    LaneSpeedRule,
    SpeedLimitsFile,
    VehicleSpeedLimitBlock,
    parse_speed_limits,
    patch_speed_limits,
)

GERMANY_LIKE_SPEED_LIMITS = (
    "SiiNunit\n"
    "{\n"
    "country_speed_limit : .speed_limit.car {\n"
    "\n"
    "\tvehicle_speed_class: car\n"
    "\n"
    "\tlane_speed_class[]: local_road\n"
    "\tlimit[]: 100\n"
    "\turban_limit[]: 50\n"
    "\tmax_limit[]: 100\n"
    "\n"
    "\tlane_speed_class[]: divided_road\n"
    "\tlimit[]: 100\n"
    "\turban_limit[]: 50\n"
    "\tmax_limit[]: 120\n"
    "\n"
    "\tlane_speed_class[]: motorway\n"
    "\tlimit[]: 130\t# advisory\n"
    "\turban_limit[]: 80\n"
    "}\n"
    "\n"
    "country_speed_limit : .speed_limit.truck {\n"
    "\tvehicle_speed_class: truck\n"
    "\n"
    "\tlane_speed_class[]: local_road\n"
    "\tlimit[]: 60\n"
    "\turban_limit[]: 50\n"
    "\n"
    "\tlane_speed_class[]: motorway\n"
    "\tlimit[]: 80\n"
    "\turban_limit[]: 50\n"
    "}\n"
    "\n"
    "country_speed_limit : .speed_limit.bus {\n"
    "\tvehicle_speed_class: bus\n"
    "\n"
    "\tlane_speed_class[]: local_road\n"
    "\tlimit[]: 80\n"
    "\turban_limit[]: 50\n"
    "}\n"
    "\n"
    "country_speed_limit : .speed_limit.train {\n"
    "\tvehicle_speed_class: train\n"
    "\n"
    "\tlane_speed_class[]: local_road\n"
    "\turban_limit[]: 50\t# combined rail+road\n"
    "}\n"
    "\n"
    "country_speed_limit : .speed_limit.tram {\n"
    "\tvehicle_speed_class: tram\n"
    "\n"
    "\tlane_speed_class[]: local_road\n"
    "\turban_limit[]: 40\n"
    "}\n"
    "}\n"
)

BULGARIA_LIKE_SPEED_LIMITS = (
    "SiiNunit\n"
    "{\n"
    "country_speed_limit : .speed_limit.car {\n"
    "\tvehicle_speed_class: car\n"
    "\n"
    "\tlane_speed_class[]: local_road\n"
    "\tlimit[]: 90\n"
    "\turban_limit[]: 50\n"
    "\n"
    "\tlane_speed_class[]: slow_road\n"
    "\tlimit[]: 70\n"
    "\turban_limit[]: 50\n"
    "\tuncommon[]: true\n"
    "}\n"
    "}\n"
)


def test_parse_speed_limits_parses_interleaved_lanes_train_tram_and_uncommon() -> None:
    parsed = parse_speed_limits(GERMANY_LIKE_SPEED_LIMITS)
    assert isinstance(parsed, SpeedLimitsFile)
    assert parsed.vehicle_classes == ["car", "truck", "bus", "train", "tram"]

    car = parsed.get_block("car")
    assert isinstance(car, VehicleSpeedLimitBlock)
    assert car.unit_name == ".speed_limit.car"
    assert car.lanes == [
        LaneSpeedRule(lane_speed_class="local_road", limit=100, urban_limit=50, max_limit=100),
        LaneSpeedRule(lane_speed_class="divided_road", limit=100, urban_limit=50, max_limit=120),
        LaneSpeedRule(lane_speed_class="motorway", limit=130, urban_limit=80, max_limit=None),
    ]

    train = parsed.get_block("train")
    assert train is not None
    assert train.lanes == [
        LaneSpeedRule(lane_speed_class="local_road", limit=None, urban_limit=50),
    ]

    bg = parse_speed_limits(BULGARIA_LIKE_SPEED_LIMITS)
    assert bg.vehicle_classes == ["car"]
    bg_car = bg.get_block("car")
    assert bg_car is not None
    assert bg_car.lanes[1] == LaneSpeedRule(
        lane_speed_class="slow_road",
        limit=70,
        urban_limit=50,
        uncommon=True,
    )


def test_patch_speed_limits_preserves_train_tram_comments_and_handles_lane_changes() -> None:
    updated = patch_speed_limits(
        GERMANY_LIKE_SPEED_LIMITS,
        {
            "car": [
                LaneSpeedRule(
                    lane_speed_class="local_road", limit=100, urban_limit=50, max_limit=100
                ),
                LaneSpeedRule(
                    lane_speed_class="divided_road", limit=100, urban_limit=50, max_limit=130
                ),
                LaneSpeedRule(
                    lane_speed_class="motorway", limit=130, urban_limit=80, max_limit=130
                ),
            ],
            "truck": [
                LaneSpeedRule(lane_speed_class="local_road", limit=80, urban_limit=50),
                LaneSpeedRule(lane_speed_class="motorway", limit=80, urban_limit=50),
            ],
        },
    )

    assert "\tlimit[]: 130\t# advisory\n" in updated
    assert "\tmax_limit[]: 130\n" in updated
    assert "\tlimit[]: 80\n" in updated

    # Untouched bus, train, and tram blocks remain verbatim including inline comment.
    train_pos_orig = GERMANY_LIKE_SPEED_LIMITS.index("country_speed_limit : .speed_limit.train")
    train_pos_new = updated.index("country_speed_limit : .speed_limit.train")
    assert updated[train_pos_new:] == GERMANY_LIKE_SPEED_LIMITS[train_pos_orig:]

    # Pass 2 idempotency
    pass1_bytes = serialize_sii_text(updated)
    pass2 = patch_speed_limits(
        pass1_bytes,
        {
            "car": [
                LaneSpeedRule(
                    lane_speed_class="local_road", limit=100, urban_limit=50, max_limit=100
                ),
                LaneSpeedRule(
                    lane_speed_class="divided_road", limit=100, urban_limit=50, max_limit=130
                ),
                LaneSpeedRule(
                    lane_speed_class="motorway", limit=130, urban_limit=80, max_limit=130
                ),
            ],
            "truck": [
                LaneSpeedRule(lane_speed_class="local_road", limit=80, urban_limit=50),
                LaneSpeedRule(lane_speed_class="motorway", limit=80, urban_limit=50),
            ],
        },
    )
    assert serialize_sii_text(pass2) == pass1_bytes

    # Structural lane expansion (adding slow_road with uncommon[])
    expanded = patch_speed_limits(
        BULGARIA_LIKE_SPEED_LIMITS,
        {
            "car": [
                LaneSpeedRule(lane_speed_class="local_road", limit=90, urban_limit=50),
                LaneSpeedRule(lane_speed_class="motorway", limit=140, urban_limit=80),
                LaneSpeedRule(
                    lane_speed_class="slow_road",
                    limit=70,
                    urban_limit=50,
                    uncommon=True,
                ),
            ]
        },
    )
    reparsed = parse_speed_limits(expanded)
    reparsed_car = reparsed.get_block("car")
    assert reparsed_car is not None
    assert len(reparsed_car.lanes) == 3
    assert reparsed_car.lanes[1].limit == 140
    assert reparsed_car.lanes[2].uncommon is True

    with pytest.raises(ValueError):
        patch_speed_limits(BULGARIA_LIKE_SPEED_LIMITS, {"train": []})

    # Removing an optional max_limit[] in place preserves surrounding lanes/comments
    cleared = patch_speed_limits(
        GERMANY_LIKE_SPEED_LIMITS,
        {
            "car": [
                LaneSpeedRule(
                    lane_speed_class="local_road", limit=100, urban_limit=50, max_limit=None
                ),
                LaneSpeedRule(
                    lane_speed_class="divided_road", limit=100, urban_limit=50, max_limit=120
                ),
                LaneSpeedRule(lane_speed_class="motorway", limit=130, urban_limit=80),
            ]
        },
    )
    reparsed_cleared = parse_speed_limits(cleared).get_block("car")
    assert reparsed_cleared is not None
    assert reparsed_cleared.lanes[0].max_limit is None
    assert reparsed_cleared.lanes[1].max_limit == 120
    assert "\tlimit[]: 130\t# advisory\n" in cleared


def test_patch_speed_limits_single_line_and_shared_brace_units() -> None:
    empty_single = "SiiNunit\n{\ncountry_speed_limit : .speed_limit.car { }\n}\n"
    patched_empty = patch_speed_limits(
        empty_single,
        {
            "car": [
                LaneSpeedRule(lane_speed_class="local_road", limit=90, urban_limit=50),
                LaneSpeedRule(lane_speed_class="motorway", limit=130, urban_limit=80),
            ]
        },
    )
    assert patched_empty.startswith("SiiNunit\n{\ncountry_speed_limit : .speed_limit.car {\n")
    reparsed = parse_speed_limits(patched_empty)
    car = reparsed.get_block("car")
    assert car is not None
    assert [lane.lane_speed_class for lane in car.lanes] == ["local_road", "motorway"]
    assert car.lanes[0].limit == 90

    shared_braces = (
        "SiiNunit\n"
        "{\n"
        "country_speed_limit : .speed_limit.car { lane_speed_class[]: local_road\n"
        "\tlimit[]: 90 }\n"
        "}\n"
    )
    patched_shared = patch_speed_limits(
        shared_braces,
        {"car": [LaneSpeedRule(lane_speed_class="motorway", limit=130, urban_limit=80)]},
    )
    reparsed_shared = parse_speed_limits(patched_shared)
    car_shared = reparsed_shared.get_block("car")
    assert car_shared is not None
    assert car_shared.lanes == [
        LaneSpeedRule(lane_speed_class="motorway", limit=130, urban_limit=80)
    ]

    cleared_shared = patch_speed_limits(shared_braces, {"car": []})
    assert parse_speed_limits(cleared_shared).get_block("car") == VehicleSpeedLimitBlock(
        unit_name=".speed_limit.car",
        vehicle_speed_class="car",
        lanes=[],
    )

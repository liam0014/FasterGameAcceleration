#!/usr/bin/env python3
"""Remove legacy FasterGameAcceleration bindings from a Caribbean Legend save.

The input is never modified. The converter removes only:

* FGA_LastTimeScaleCounter
* the FGA_UpdateLogTiming saved frame handler

It preserves the save's extended data (metadata and screenshot) verbatim.
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import struct
import sys
import zlib


LEGACY_VARIABLES = {"FGA_LastTimeScaleCounter"}
LEGACY_HANDLER = "FGA_UpdateLogTiming"


class SaveFormatError(RuntimeError):
    pass


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        result = self.data[self.pos : self.pos + size]
        if len(result) != size:
            raise SaveFormatError(
                f"Unexpected end of script state at offset {self.pos}"
            )
        self.pos += size
        return result

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def vdword(self) -> int:
        first = self.take(1)[0]
        if first < 0xFE:
            return first
        if first == 0xFE:
            return struct.unpack("<H", self.take(2))[0]
        return self.u32()

    def string(self) -> bytes | None:
        size = self.vdword()
        if size == 0:
            return None
        value = self.take(size)
        if not value.endswith(b"\0"):
            raise SaveFormatError(f"Unterminated string at offset {self.pos - size}")
        return value[:-1]


class Writer:
    def __init__(self):
        self.data = bytearray()

    def bytes(self, value: bytes) -> None:
        self.data.extend(value)

    def u32(self, value: int) -> None:
        self.bytes(struct.pack("<I", value))

    def u64(self, value: int) -> None:
        self.bytes(struct.pack("<Q", value))

    def f32(self, value: float) -> None:
        self.bytes(struct.pack("<f", value))

    def i32(self, value: int) -> None:
        self.bytes(struct.pack("<i", value))

    def vdword(self, value: int) -> None:
        if value < 0 or value > 0xFFFFFFFF:
            raise SaveFormatError(f"VDWORD out of range: {value}")
        if value < 0xFE:
            self.bytes(bytes((value,)))
        elif value <= 0xFFFF:
            self.bytes(b"\xFE")
            self.bytes(struct.pack("<H", value))
        else:
            self.bytes(b"\xFF")
            self.u32(value)

    def string(self, value: bytes | None) -> None:
        if value is None:
            self.vdword(0)
            return
        self.vdword(len(value) + 1)
        self.bytes(value + b"\0")


def text(value: bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace")


def string_code(string_value: bytes, counts: dict[int, int]) -> int:
    hash_value = 0
    for character in string_value.lower():
        hash_value = ((hash_value << 4) + character) & 0xFFFFFFFF
        high = hash_value & 0xF0000000
        if high:
            hash_value ^= high >> 24
            hash_value ^= high
    table_index = hash_value & 511
    element_index = counts.get(table_index, 0)
    counts[table_index] = element_index + 1
    return (table_index << 16) | element_index


@dataclasses.dataclass
class Attribute:
    name_code: int
    value: bytes | None
    children: list["Attribute"]


@dataclasses.dataclass
class Reference:
    variable_index: int
    array_index: int | None
    variable_name: bytes | None = None
    attribute: bytes | None = None


@dataclasses.dataclass
class ObjectValue:
    entity_id: int
    attributes: Attribute


@dataclasses.dataclass
class Variable:
    name: bytes
    value_type: int
    values: list[object]


@dataclasses.dataclass
class ScriptState:
    program_directory: bytes | None
    codec_strings: list[bytes]
    codec: dict[int, str]
    segments: list[bytes | None]
    variables: list[Variable]


def read_attribute(reader: Reader) -> Attribute:
    child_count = reader.vdword()
    name_code = reader.vdword()
    value = reader.string()
    children = [read_attribute(reader) for _ in range(child_count)]
    return Attribute(name_code, value, children)


def write_attribute(writer: Writer, attribute: Attribute) -> None:
    writer.vdword(len(attribute.children))
    writer.vdword(attribute.name_code)
    writer.string(attribute.value)
    for child in attribute.children:
        write_attribute(writer, child)


def read_value(reader: Reader, value_type: int) -> object:
    if value_type == 6:  # integer / bool
        return reader.i32()
    if value_type == 7:  # float
        return reader.f32()
    if value_type == 8:  # string
        return reader.string()
    if value_type == 9:  # object
        return ObjectValue(reader.u64(), read_attribute(reader))
    if value_type in (10, 11):  # reference / attribute reference
        variable_index = reader.vdword()
        if variable_index == 0xFFFFFFFF:
            return Reference(variable_index, None)
        array_index = reader.vdword()
        variable_name = None
        if variable_index == 0xFFFFFFAA:
            variable_name = reader.string()
        attribute = reader.string() if value_type == 11 else None
        return Reference(variable_index, array_index, variable_name, attribute)
    if value_type == 12:  # pointer
        return reader.u64()
    raise SaveFormatError(f"Unsupported script variable type {value_type}")


def write_value(writer: Writer, value_type: int, value: object) -> None:
    if value_type == 6:
        writer.i32(value)  # type: ignore[arg-type]
    elif value_type == 7:
        writer.f32(value)  # type: ignore[arg-type]
    elif value_type == 8:
        writer.string(value)  # type: ignore[arg-type]
    elif value_type == 9:
        assert isinstance(value, ObjectValue)
        writer.u64(value.entity_id)
        write_attribute(writer, value.attributes)
    elif value_type in (10, 11):
        assert isinstance(value, Reference)
        writer.vdword(value.variable_index)
        if value.variable_index != 0xFFFFFFFF:
            assert value.array_index is not None
            writer.vdword(value.array_index)
            if value.variable_index == 0xFFFFFFAA:
                writer.string(value.variable_name)
            if value_type == 11:
                writer.string(value.attribute)
    elif value_type == 12:
        writer.u64(value)  # type: ignore[arg-type]
    else:
        raise SaveFormatError(f"Unsupported script variable type {value_type}")


def parse_script_state(raw: bytes) -> ScriptState:
    reader = Reader(raw)
    program_directory = reader.string()
    codec_strings = []
    for _ in range(reader.vdword()):
        codec_string = reader.string()
        if codec_string is None:
            raise SaveFormatError("Null entry in string codec")
        codec_strings.append(codec_string)

    codec_counts: dict[int, int] = {}
    codec = {
        string_code(value, codec_counts): text(value) for value in codec_strings
    }
    segments = [reader.string() for _ in range(reader.vdword())]
    variables = []
    for _ in range(reader.vdword()):
        name = reader.string()
        if name is None:
            raise SaveFormatError("Missing variable name")
        value_type = reader.u32()
        element_count = reader.u32()
        values = [read_value(reader, value_type) for _ in range(element_count)]
        variables.append(Variable(name, value_type, values))

    if reader.pos != len(raw):
        raise SaveFormatError(
            f"Unparsed script data: {len(raw) - reader.pos} bytes remain"
        )
    return ScriptState(program_directory, codec_strings, codec, segments, variables)


def serialise_script_state(state: ScriptState) -> bytes:
    writer = Writer()
    writer.string(state.program_directory)
    writer.vdword(len(state.codec_strings))
    for codec_string in state.codec_strings:
        writer.string(codec_string)
    writer.vdword(len(state.segments))
    for segment in state.segments:
        writer.string(segment)
    writer.vdword(len(state.variables))
    for variable in state.variables:
        writer.string(variable.name)
        writer.u32(variable.value_type)
        writer.u32(len(variable.values))
        for value in variable.values:
            write_value(writer, variable.value_type, value)
    return bytes(writer.data)


def attribute_name(state: ScriptState, attribute: Attribute) -> str:
    return state.codec.get(attribute.name_code, f"#{attribute.name_code}")


def clean_event_attributes(
    state: ScriptState, attribute: Attribute, parent_name: str = ""
) -> int:
    handlers_removed = 0
    kept = []
    for child in attribute.children:
        name = attribute_name(state, child)
        if (
            parent_name == "Common"
            and name.casefold() == LEGACY_HANDLER.casefold()
        ):
            handlers_removed += 1
            continue
        handlers_removed += clean_event_attributes(state, child, name)
        kept.append(child)
    attribute.children = kept
    return handlers_removed


def has_legacy_handler(
    state: ScriptState, attribute: Attribute, parent_name: str = ""
) -> bool:
    for child in attribute.children:
        name = attribute_name(state, child)
        if (
            parent_name == "Common"
            and name.casefold() == LEGACY_HANDLER.casefold()
        ):
            return True
        if has_legacy_handler(state, child, name):
            return True
    return False


def clean_state(state: ScriptState) -> dict[str, object]:
    removed_indices = {
        index
        for index, variable in enumerate(state.variables)
        if text(variable.name) in LEGACY_VARIABLES
    }
    removed_names = [text(state.variables[index].name) for index in removed_indices]

    old_to_new = {}
    next_index = 0
    for old_index in range(len(state.variables)):
        if old_index in removed_indices:
            continue
        old_to_new[old_index] = next_index
        next_index += 1

    adjusted_references = 0
    for variable in state.variables:
        if variable.value_type not in (10, 11):
            continue
        for value in variable.values:
            assert isinstance(value, Reference)
            if value.variable_index in (0xFFFFFFFF, 0xFFFFFFAA):
                if (
                    value.variable_index == 0xFFFFFFAA
                    and text(value.variable_name) in LEGACY_VARIABLES
                ):
                    raise SaveFormatError(
                        f"A live reference targets legacy variable "
                        f"{text(value.variable_name)!r}; refusing unsafe removal"
                    )
                continue
            if value.variable_index in removed_indices:
                raise SaveFormatError(
                    f"A live numeric reference targets legacy variable index "
                    f"{value.variable_index}; refusing unsafe removal"
                )
            if value.variable_index not in old_to_new:
                raise SaveFormatError(
                    f"Reference target {value.variable_index} is out of range"
                )
            new_index = old_to_new[value.variable_index]
            if new_index != value.variable_index:
                value.variable_index = new_index
                adjusted_references += 1

    state.variables = [
        variable
        for index, variable in enumerate(state.variables)
        if index not in removed_indices
    ]

    handlers_removed = 0
    for variable in state.variables:
        if text(variable.name) != "__eventsData" or variable.value_type != 9:
            continue
        for value in variable.values:
            assert isinstance(value, ObjectValue)
            handlers_removed += clean_event_attributes(state, value.attributes)

    return {
        "removed_variables": sorted(removed_names),
        "adjusted_numeric_references": adjusted_references,
        "removed_event_handlers": handlers_removed,
    }


def convert(input_path: pathlib.Path, output_path: pathlib.Path) -> dict[str, object]:
    source = input_path.read_bytes()
    if len(source) < 48:
        raise SaveFormatError("File is too small to be a save")

    ext_offset, ext_size = struct.unpack_from("<II", source, 32)
    raw_size, packed_size = struct.unpack_from("<II", source, 40)
    packed_end = 48 + packed_size
    if packed_end > len(source):
        raise SaveFormatError("Compressed script state extends beyond the file")
    if ext_offset < packed_end or ext_offset > len(source):
        raise SaveFormatError("Invalid extended-data offset")
    # ext_size is the unpacked size of the extended block; its stored bytes may
    # therefore be shorter than ext_size. The complete stored tail is preserved.

    raw = zlib.decompress(source[48:packed_end])
    if len(raw) != raw_size:
        raise SaveFormatError(
            f"Script-state size mismatch: expected {raw_size}, got {len(raw)}"
        )

    state = parse_script_state(raw)
    round_trip = serialise_script_state(state)
    if round_trip != raw:
        raise SaveFormatError("Parser round-trip differed before modification")

    report = clean_state(state)
    cleaned_raw = serialise_script_state(state)
    reparsed = parse_script_state(cleaned_raw)
    if serialise_script_state(reparsed) != cleaned_raw:
        raise SaveFormatError("Cleaned script state failed round-trip validation")

    if any(text(variable.name) in LEGACY_VARIABLES for variable in reparsed.variables):
        raise SaveFormatError(
            "A legacy FasterGameAcceleration variable remains after cleanup"
        )

    for variable in reparsed.variables:
        if text(variable.name) != "__eventsData" or variable.value_type != 9:
            continue
        for value in variable.values:
            assert isinstance(value, ObjectValue)
            if has_legacy_handler(reparsed, value.attributes):
                raise SaveFormatError(
                    "The legacy FasterGameAcceleration frame handler remains "
                    "after cleanup"
                )

    packed = zlib.compress(cleaned_raw, level=9)
    gap = source[packed_end:ext_offset]
    extended_data = source[ext_offset:]
    new_ext_offset = 48 + len(packed) + len(gap)
    header = bytearray(source[:40])
    struct.pack_into("<I", header, 32, new_ext_offset)
    result = (
        bytes(header)
        + struct.pack("<II", len(cleaned_raw), len(packed))
        + packed
        + gap
        + extended_data
    )

    if output_path.resolve() == input_path.resolve():
        raise SaveFormatError("Refusing to overwrite the input save")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result)

    report.update(
        {
            "input_bytes": len(source),
            "output_bytes": len(result),
            "script_bytes_before": len(raw),
            "script_bytes_after": len(cleaned_raw),
            "extended_data_bytes_preserved": len(extended_data),
            "output": str(output_path),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_save", type=pathlib.Path)
    parser.add_argument("output_save", type=pathlib.Path)
    args = parser.parse_args()

    try:
        report = convert(args.input_save, args.output_save)
    except (OSError, SaveFormatError, zlib.error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("FasterGameAcceleration save cleanup completed")
    print(f"Output: {report['output']}")
    print(
        "Removed variables: "
        + (", ".join(report["removed_variables"]) or "none")
    )
    print(f"Removed legacy handlers: {report['removed_event_handlers']}")
    print(
        "Adjusted positional references: "
        f"{report['adjusted_numeric_references']}"
    )
    print(
        "Preserved extended data: "
        f"{report['extended_data_bytes_preserved']} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

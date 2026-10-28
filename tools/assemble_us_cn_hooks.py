#!/usr/bin/env python3
"""Assemble fixed-address optional US-CN hooks and verify the local reference.

Only readable source instructions and explicit literal/padding declarations are
assembled. Resource tables and copyrighted resource payloads are not generated
by this tool. All generated artifacts must be placed outside the source tree.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

COMPONENTS = (
    ("copy", 0x003B4220, 0x003B4262),
    ("override", 0x003B4270, 0x003B42DC),
    ("startup", 0x00A7FC00, 0x00A7FDB0),
)
REFERENCE_SHA256 = "ddbf29205a66d9711d8f6ec2ce7b2de481d3d58255efdc3791e45e1771548c03"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-rom", type=Path, help="Optional pinned reference used only for independent verification")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "engine/us_cn_hooks.s")
    parser.add_argument("--tool-prefix", default="arm-none-eabi-")
    args = parser.parse_args()
    source_root = Path(__file__).resolve().parents[1]
    output = args.output_dir.resolve()
    if output == source_root or source_root in output.parents:
        parser.error("generated artifacts must be outside the source tree")
    reference = args.reference_rom.read_bytes() if args.reference_rom else None
    if reference is not None and (len(reference) != 0x1000000 or sha(reference) != REFERENCE_SHA256):
        parser.error("reference ROM does not match the pinned 16 MiB US-CN identity")
    output.mkdir(parents=True, exist_ok=True)
    source = args.source.resolve()
    frozen_source = output / "us_cn_hooks.s"
    frozen_source.write_bytes(source.read_bytes())
    tools = {}
    for name in ("as", "ld", "objcopy"):
        executable = shutil.which(args.tool_prefix + name)
        if executable is None:
            parser.error("missing tool: " + args.tool_prefix + name)
        version = subprocess.check_output([executable, "--version"], text=True).splitlines()[0]
        tools[name] = {"path": executable, "version": version}
    commands = []

    def run(command: list[str]) -> None:
        commands.append(command)
        subprocess.run(command, check=True, capture_output=True, text=True)

    obj = output / "hooks.o"
    run([tools["as"]["path"], "-mcpu=arm7tdmi", "-o", str(obj), str(frozen_source)])
    linker_script = output / "hooks.ld"
    linker_script.write_text("SECTIONS {\n" + "\n".join(
        f"  .text.uscn_{name} 0x{start + 0x08000000:08X} : {{ *(.text.uscn_{name}) }}"
        for name, start, _ in COMPONENTS
    ) + "\n /DISCARD/ : { *(.ARM.attributes) *(.text) *(.data) *(.bss) }\n}\n")
    elf = output / "hooks.elf"
    run([tools["ld"]["path"], "-T", str(linker_script), "-o", str(elf), str(obj)])
    results = []
    for name, start, end in COMPONENTS:
        binary = output / (name + ".bin")
        run([tools["objcopy"]["path"], "-O", "binary", "--only-section=.text.uscn_" + name, str(elf), str(binary)])
        actual = binary.read_bytes()
        expected = reference[start:end] if reference is not None else None
        if len(actual) != end - start:
            raise ValueError(f"component {name} size {len(actual)} != {end-start}")
        differences = [i for i, (a, b) in enumerate(zip(actual, expected)) if a != b] if expected is not None else None
        results.append({
            "name": name, "rom_start": start, "rom_end_exclusive": end,
            "cpu_start": f"0x{start + 0x08000000:08X}",
            "cpu_end_exclusive": f"0x{end + 0x08000000:08X}",
            "bytes": len(actual), "expected_bytes": len(expected) if expected is not None else None,
            "sha256": sha(actual), "reference_sha256": sha(expected) if expected is not None else None,
            "exact": actual == expected if expected is not None else None, "different_byte_offsets": differences,
            "binary": str(binary),
        })
    report = {
        "schema": 1, "reference_rom": str(args.reference_rom.resolve()) if args.reference_rom else None,
        "reference_sha256": sha(reference) if reference is not None else None, "reference_bytes": len(reference) if reference is not None else None,
        "source": str(frozen_source), "source_sha256": sha(frozen_source.read_bytes()),
        "tools": tools, "commands": commands, "components": results,
        "all_exact": all(x["exact"] for x in results) if reference is not None else None,
        "segments": [{"rom_offset": x["rom_start"], "bytes": x["bytes"], "binary": x["binary"], "sha256": x["sha256"]} for x in results],
        "external_literal_contracts": ["0x083B42E0", "0x083B4320", "0x083B4450"],
        "limits": "Components exclude resource replacement tables, payloads and original-site instruction changes. No native C build or matching credit.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"all_exact": report["all_exact"], "components": [{k: x[k] for k in ("name", "bytes", "expected_bytes", "exact", "different_byte_offsets")} for x in results]}))
    if reference is not None and not report["all_exact"]:
        raise SystemExit(1)


def assemble_hooks(source: Path, output_dir: Path, tool_prefix: str = "arm-none-eabi-") -> dict:
    """Build from readable source only; return fixed-offset segment descriptors.

    This API never opens a translated ROM or frozen binary. The caller reads
    each returned binary and places it at its ``rom_offset`` in the English
    baseline. CLI --reference-rom is an optional separate verification gate.
    """
    subprocess.run([sys.executable, str(Path(__file__).resolve()),
                    "--source", str(source), "--output-dir", str(output_dir),
                    "--tool-prefix", tool_prefix], check=True, capture_output=True, text=True)
    return json.loads((Path(output_dir) / "report.json").read_text())


if __name__ == "__main__":
    main()

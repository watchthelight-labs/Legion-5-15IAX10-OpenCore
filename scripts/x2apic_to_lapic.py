# <wtl> project: legion-5-15iax10-opencore | file: scripts/x2apic_to_lapic.py | author: watchthelight </wtl>
"""Rewrite an x2APIC-only MADT (APIC table) into classic Local APIC entries for macOS.

Why: XNU counts CPUs only from MADT type-0 (Processor Local APIC) entries
(xnu osfmk/i386/acpi.c acpi_count_enabled_logical_processors). This laptop's firmware emits
only type-9 (x2APIC) entries, so XNU counts 0 CPUs and cpu_data_startup_init() panics with
"percpu: max_cpus_from_firmware not yet initialized" before the console exists: a silent
hang right after EXITBS:START (I-025). OpenCore then deletes the firmware table and adds this one.

Output table: same header (OEM IDs, revision, Local APIC address, flags), one type-0 entry per
ENABLED type-9 entry in firmware order (ProcessorId = UID, APIC ID = x2APIC ID, which must be
< 0xFF), IOAPIC and interrupt source overrides copied byte for byte, and type-10 x2APIC NMI
entries converted to type-4 Local APIC NMI (UID 0xFFFFFFFF -> ProcessorId 0xFF = all CPUs).

  python scripts/x2apic_to_lapic.py APIC.aml ACPI/APIC-legacy.aml
"""
import struct
import sys


def convert(src: bytes) -> tuple[bytes, list[str]]:
    assert src[:4] == b"APIC", "not an APIC/MADT table"
    length = struct.unpack_from("<I", src, 4)[0]
    header = bytearray(src[:44])            # 36-byte SDT header + LAPIC address + flags
    out = bytearray()
    notes = []
    off = 44
    cpus = []
    while off < length:
        etype, elen = src[off], src[off + 1]
        e = src[off:off + elen]
        if etype == 9:                      # Processor Local x2APIC
            x2id, flags, uid = struct.unpack_from("<III", e, 4)
            if flags & 1:
                if x2id >= 0xFF or uid > 0xFF:
                    raise SystemExit(f"x2APIC ID {x2id:#x} / UID {uid} does not fit a type-0 entry")
                cpus.append((uid, x2id, flags))
        elif etype == 0xA:                  # Local x2APIC NMI -> Local APIC NMI
            nflags, uid, lint = struct.unpack_from("<HIB", e, 2)
            pid = 0xFF if uid == 0xFFFFFFFF else uid
            out += struct.pack("<BBBHB", 4, 6, pid, nflags, lint)
            notes.append(f"NMI uid {uid:#x} -> type-4 ProcessorId {pid:#x} LINT{lint} flags {nflags:#x}")
        elif etype in (1, 2, 3, 4):         # IOAPIC, ISO, NMI source, LAPIC NMI: keep as is
            out += e
            notes.append(f"kept type {etype} ({elen} bytes)")
        elif etype == 0:
            raise SystemExit("table already has type-0 entries; nothing to convert")
        else:
            notes.append(f"dropped type {etype} ({elen} bytes)")
        off += elen
    procs = bytearray()
    for uid, x2id, flags in cpus:
        procs += struct.pack("<BBBBI", 0, 8, uid, x2id, 1)
    table = header + procs + out
    struct.pack_into("<I", table, 4, len(table))
    table[9] = 0
    table[9] = (-sum(table)) & 0xFF
    assert sum(table) & 0xFF == 0
    notes.insert(0, f"{len(cpus)} enabled CPUs -> type-0: " +
                 ", ".join(f"uid {u} apic {a:#x}" for u, a, _ in cpus))
    notes.insert(1, f"length {length} -> {len(table)}, checksum {table[9]:#04x}")
    return bytes(table), notes


if __name__ == "__main__":
    src = open(sys.argv[1], "rb").read()
    table, notes = convert(src)
    open(sys.argv[2], "wb").write(table)
    print("\n".join(notes))

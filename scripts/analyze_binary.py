"""Inspect the owner's PC executable and prepare a local analysis copy."""
import hashlib
import json
import struct
import sys
from pathlib import Path
import pefile


def analyze(source, output):
    source, output = Path(source).resolve(), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw = source.read_bytes()
    pe = pefile.PE(data=raw)
    if pe.FILE_HEADER.Machine != 0x14C or pe.OPTIONAL_HEADER.Magic != 0x10B:
        raise ValueError('The reference must be a PC x86 PE32 executable')
    imports = {item.dll.decode(): [entry.name.decode() if entry.name else '#'+str(entry.ordinal)
               for entry in item.imports] for item in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', [])}
    sections = [dict(name=s.Name.decode(errors='replace').rstrip('\0'), rva=s.VirtualAddress,
                    virtual_size=s.Misc_VirtualSize, raw_size=s.SizeOfRawData,
                    characteristics=s.Characteristics, entropy=round(s.get_entropy(), 3))
                for s in pe.sections]
    restored = None
    directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[5]
    if not directory.VirtualAddress:
        # Reuse the NFSU2 observation, but validate the entire chain instead
        # of assuming its section RVA or number of entries for this game.
        for section in pe.sections:
            if not section.Characteristics & 0x02000000:
                continue
            data, offset, entries = section.get_data(), 0, 0
            while offset + 8 <= len(data):
                page, size = struct.unpack_from('<II', data, offset)
                if not page and not size:
                    break
                if page % 4096 or page >= pe.OPTIONAL_HEADER.SizeOfImage or size < 8 or size % 2 or offset+size > len(data):
                    break
                words = struct.unpack_from('<'+'H'*((size-8)//2), data, offset+8)
                if any(word>>12 not in (0, 3) for word in words):
                    break
                entries += sum(word>>12 == 3 for word in words)
                offset += size
            if offset and entries and not any(data[offset:]):
                directory.VirtualAddress, directory.Size = section.VirtualAddress, offset
                section.Name = b'.reloc\0\0'
                restored = dict(rva=section.VirtualAddress, bytes=offset, highlow_entries=entries)
                break
    analysis = output/'speed.analysis.exe'
    analysis.write_bytes(pe.write() if restored else raw)
    versions = []
    for group in getattr(pe, 'FileInfo', []):
        for entry in group:
            for table in getattr(entry, 'StringTable', []):
                versions.append({k.decode(errors='replace'):v.decode(errors='replace') for k,v in table.entries.items()})
    report = dict(source=str(source), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                  architecture='x86 PE32', image_base=pe.OPTIONAL_HEADER.ImageBase,
                  entry=pe.OPTIONAL_HEADER.ImageBase+pe.OPTIONAL_HEADER.AddressOfEntryPoint,
                  image_size=pe.OPTIONAL_HEADER.SizeOfImage, sections=sections, imports=imports,
                  import_count=sum(map(len, imports.values())), version_resources=versions,
                  relocation_restoration=restored, analysis_sha256=hashlib.sha256(analysis.read_bytes()).hexdigest())
    (output/'binary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('sections','imports')}, indent=2))


if __name__ == '__main__':
    analyze(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else 'work')

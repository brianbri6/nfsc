"""Copy a DLL rebased to a fixed address with ASLR disabled, so Windows loads it
exactly there (patch capture must use the guest's layout).
Usage: rebase_fixed.py <dll> <base> <output>"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))
import pefile
from prepare_module import relocate_file

src, base, dst = sys.argv[1], int(sys.argv[2], 0), sys.argv[3]
relocate_file(src, base, dst)
pe = pefile.PE(dst)
off = pe.OPTIONAL_HEADER.get_file_offset() + 70        # DllCharacteristics
pe.close()
data = bytearray(open(dst, 'rb').read())
flags = int.from_bytes(data[off:off + 2], 'little') & ~0x0040   # IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE
data[off:off + 2] = flags.to_bytes(2, 'little')
open(dst, 'wb').write(bytes(data))
print(f'{dst}: base {base:#010x}, DllCharacteristics {flags:#06x}')

"""Compare the real sound gain routine against x86, including its -1 sentinel.

Run in a VS developer prompt: python tests/sound_channel_flags.py
Requires the locally analysed game, catalog, capstone and Unicorn. No game
bytes are distributed: C and executables are generated under ignored work/.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_lift as driver
from mw_lifter import Lifter
from lift32 import Lifter as OldLifter
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as X

BASE, VOICE, STACK, RETURN = 0x400000, 0xB00000, 0xC08000, 0xD00000
FUNCTION = 0x81CDC6
REGS = ['eax', 'ecx', 'edx', 'ebx', 'esp', 'ebp', 'esi', 'edi']
R = [getattr(X, 'UC_X86_REG_' + name.upper()) for name in REGS]
CASES = [(channel, gain) for channel in (-1, 0, 1, 5)
         for gain in (-1000000., 0., .5, 175.25)]


def reference(image, channel, gain):
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(BASE, 0xA00000)
    uc.mem_write(BASE, image)
    uc.mem_write(0x9C2188, b'\x01')
    uc.mem_write(VOICE, bytes([0xA5]) * 0x300)
    uc.mem_write(STACK, struct.pack('<IIif', RETURN, 7, channel, gain))
    uc.reg_write(X.UC_X86_REG_ESP, STACK)
    uc.reg_write(X.UC_X86_REG_FPCW, 0x027F)
    uc.reg_write(X.UC_X86_REG_FPTAG, 0xFFFF)

    def stub(machine, address, size, context):
        if address not in (0x81C131, 0x81F7CB, 0x81F207):
            return
        if address == 0x81F207:
            raise AssertionError('Unexpected downstream sound call')
        machine.reg_write(X.UC_X86_REG_EAX, VOICE if address == 0x81C131 else 0xFFFFFFFF)
        esp = machine.reg_read(X.UC_X86_REG_ESP)
        machine.reg_write(X.UC_X86_REG_EIP, struct.unpack('<I', machine.mem_read(esp, 4))[0])
        machine.reg_write(X.UC_X86_REG_ESP, esp + 4)

    uc.hook_add(UC_HOOK_CODE, stub)
    uc.emu_start(FUNCTION, RETURN, count=10000)
    assert uc.reg_read(X.UC_X86_REG_EIP) == RETURN
    return struct.pack('<8I', *(uc.reg_read(reg) for reg in R)) + bytes(uc.mem_read(VOICE, 0x300))


def compiled(image, catalog, lifter_type, output):
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    descriptor = next(f for f in catalog['functions'] if f['address'] == FUNCTION)
    function = driver.rebuild(md, image, BASE, descriptor)
    lifter = lifter_type(precise_carry=True)
    code = lifter.lift_function(function)
    prelude = r'''
#define RECOMP_GENERATED_CODE
#include "recomp_types.h"
uint32_t g_eax,g_ecx,g_edx,g_ebx,g_esp,g_ebp,g_esi,g_edi,g_cur_func;
uint32_t g_fs_base,g_gs_base,g_mxcsr;
uint16_t g_seg_cs,g_seg_ds,g_seg_es,g_seg_fs,g_seg_gs,g_seg_ss,g_fpu_cw=0x027f;
double g_st[8];int g_fp_top;V128 g_xmm[8];uint64_t g_mm[8];ptrdiff_t g_mem_base;
void recomp_dump_trace(const char* why){(void)why;}
void recomp_unimpl(uint32_t va,const char* why){fprintf(stderr,"%08x %s",va,why);exit(2);}
void sub_0081C131(void){g_eax=0xB00000;g_esp+=4;}
void sub_0081F7CB(void){g_eax=0xffffffff;g_esp+=4;}
void sub_0081F207(void){abort();}
'''
    body = ['int main(void){FILE* f;unsigned char* memory=(unsigned char*)calloc(1,0xE00000);',
            'g_mem_base=(ptrdiff_t)memory;f=fopen("image.bin","rb");',
            f'fread(memory+0x{BASE:X},1,{len(image)},f);fclose(f);f=fopen("{output.name}.bin","wb");']
    for channel, gain in CASES:
        bits = struct.unpack('<I', struct.pack('<f', gain))[0]
        body.extend(['MEM8(0x9C2188)=1;memset(memory+0xB00000,0xA5,0x300);memset(g_st,0,sizeof g_st);g_fp_top=0;',
                     'g_eax=g_ecx=g_edx=g_ebx=g_ebp=g_esi=g_edi=0;g_esp=0xC08000;',
                     f'MEM32(g_esp)=0xD00000;MEM32(g_esp+4)=7;MEM32(g_esp+8)={channel & 0xFFFFFFFF}u;MEM32(g_esp+12)={bits}u;',
                     'sub_0081CDC6();{uint32_t r[]={g_eax,g_ecx,g_edx,g_ebx,g_esp,g_ebp,g_esi,g_edi};',
                     'fwrite(r,1,sizeof r,f);fwrite(memory+0xB00000,1,0x300,f);}'])
    body.append('fclose(f);free(memory);return 0;}')
    source = output.with_suffix('.c')
    source.write_text(prelude + code + '\n' + '\n'.join(body))
    subprocess.run(['cl', '/nologo', '/O2', '/TC',
                    '/I' + str(ROOT.parent / 'pcrecomp/runtime/recomp32'),
                    str(source), '/Fe' + str(output), '/Fo' + str(output.with_suffix('.obj'))],
                   cwd=output.parent, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([str(output)], cwd=output.parent, check=True)
    return output.with_suffix('.exe.bin').read_bytes()


def main():
    image = pefile.PE(str(ROOT / 'work/speed.analysis.exe')).get_memory_mapped_image()
    catalog = json.loads((ROOT / 'work/catalog.json').read_text())
    work = ROOT / 'work/sound-channel-flags'
    work.mkdir(exist_ok=True)
    (work / 'image.bin').write_bytes(image)
    expected = b''.join(reference(image, *case) for case in CASES)
    if '--prove-old-bug' in sys.argv:
        old = compiled(image, catalog, OldLifter, work / 'old.exe')
        # Channel -1, gain 175.25 overwrote the callback-presence field.
        assert struct.unpack_from('<I', old, 3 * 800 + 32 + 0x118)[0] == 0x432F4000
        assert old != expected, 'Old lifter unexpectedly agrees: re-evaluate baseline'
    result = compiled(image, catalog, Lifter, work / 'fixed.exe')
    if result != expected:
        record = 32 + 0x300
        for i, case in enumerate(CASES):
            if result[i*record:(i+1)*record] != expected[i*record:(i+1)*record]:
                raise AssertionError(f'x86 mismatch for channel/gain {case}')
    print(f'Sound channel flags: {len(CASES)} real-function cases match x86')
    if '--prove-old-bug' in sys.argv:
        print('Old lifter reproduced the callback overwrite at voice+0x118')


if __name__ == '__main__':
    main()

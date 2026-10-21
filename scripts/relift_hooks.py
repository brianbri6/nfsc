"""Relift only catalogued functions containing configured hooks.

Equivalent to a complete lift for these functions; untouched units retain
their bytes and timestamps. Generated game C remains local and ignored.
Pass --x87-flags once to also replace old x87 flag translations in a local lift.
"""
import re
import json
import sys
from pathlib import Path
import pefile
import run_lift as driver
from mw_lifter import Lifter
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

root=Path(__file__).resolve().parent.parent
image_path=root/'work/speed.analysis.exe'
catalog=json.loads((root/'work/catalog.json').read_text())
hooks=set(driver.read_va_list(root/'config/hooks.txt'))
overrides=driver.read_va_list(root/'config/overrides.txt')
# Include old sites when selecting functions so deleting a hook removes it from
# locally generated code as well as from future full lifts.
previous_hooks=set()
fpu_functions=set()
for generated in (root/'src/recomp/gen').glob('recomp_[0-9]*.c'):
    source=generated.read_text()
    previous_hooks.update(int(site,16) for site in re.findall(r'RECOMP_HOOK\(0x([0-9A-Fa-f]+)u\)',source))
    if '--x87-flags' in sys.argv:
        for match in re.finditer(r'^void sub_([0-9A-F]{8})\(void\) \{(.*?)(?=^void sub_|\Z)',source,re.M|re.S):
            if 'FK_FCOM' in match[2]:fpu_functions.add(int(match[1],16))
selected_sites=hooks|previous_hooks|set(overrides)
pe=pefile.PE(str(image_path));base=pe.OPTIONAL_HEADER.ImageBase;image=pe.get_memory_mapped_image()
info=driver.analyze_pe(str(image_path));iat=driver.build_iat_map(info)
lifter=Lifter(iat_map=iat,func_names={},lifted={f['address'] for f in catalog['functions']},precise_carry=True,hook_sites=hooks)
decoder=Cs(CS_ARCH_X86,CS_MODE_32);decoder.detail=True
replacement={};observed=set()
for descriptor in catalog['functions']:
    if descriptor['address'] not in fpu_functions and not any(start<=hook<end for start,end,*_ in descriptor['blocks'] for hook in selected_sites):continue
    function=driver.rebuild(decoder,image,base,descriptor)
    for block in function.blocks.values():
        observed.update(i.address for i in block.instructions if i.address in hooks)
    address=descriptor['address']
    if address in overrides:
        replacement[address]=(f'void sub_{address:08X}(void) {{ recomp_func_t fn=recomp_lookup_manual(0x{address:08X}u); '
                              f'if(fn){{fn();return;}} RECOMP_UNIMPL(0x{address:08X}u,"override missing"); }}')
    else:replacement[address]=lifter.lift_function(function)
if observed!=hooks:raise RuntimeError('Hooks not on instruction boundaries: '+str(hooks-observed))
written=set()
for path in (root/'src/recomp/gen').glob('recomp_[0-9]*.c'):
    source=path.read_text();matches=list(re.finditer(r'^void sub_([0-9A-F]{8})\(void\) \{',source,re.M));changed=False
    for index in range(len(matches)-1,-1,-1):
        match=matches[index];address=int(match[1],16)
        if address not in replacement:continue
        end=matches[index+1].start() if index+1<len(matches) else len(source)
        written.add(address)
        if source[match.start():end].strip()==replacement[address].strip():continue
        source=source[:match.start()]+replacement[address]+'\n\n'+source[end:];changed=True
    if changed:path.write_text(source,encoding='utf-8',newline='\n');print('Updated',path.name)
if written!=set(replacement):raise RuntimeError('Affected functions not found in generated units')
print('Relifted',len(written),'functions with',len(hooks),'verified hooks')

/* Build from a VS developer prompt:
 * cl /nologo /TC /I../pcrecomp/runtime/recomp32 /I../nfsu2-recompiled/src/runtime
 * tests/memmove_override.c src/runtime/overrides.c /Fework/memmove_override.exe
 */
#include "recomp_types.h"
#include "nfs_runtime.h"
#include <stdio.h>
#include <string.h>
ptrdiff_t g_mem_base;
uint32_t g_eax,g_esp;
static unsigned char guest[4096],expected[512];
int main(void){
    const unsigned sizes[]={0,1,2,3,4,7,15,16,31,32,33,63,64,65,127,128,129,255};
    nfs_override_fn fn=nfs_override_lookup(0x7C4840);unsigned count=0;
    if(!fn)return 1;g_mem_base=(ptrdiff_t)guest;
    for(unsigned alignment=0;alignment<4;++alignment)
    for(int delta=-33;delta<=33;++delta)
    for(unsigned n=0;n<sizeof sizes/sizeof sizes[0];++n){
        unsigned source=100+alignment,dest=(unsigned)((int)source+delta),size=sizes[n];
        for(unsigned i=0;i<512;++i)guest[512+i]=expected[i]=(unsigned char)(i*73+19);
        memmove(expected+dest,expected+source,size);
        g_esp=32;MEM32(36)=512+dest;MEM32(40)=512+source;MEM32(44)=size;fn();
        if(g_esp!=36||g_eax!=512+dest||memcmp(guest+512,expected,512)){
            printf("FAIL alignment=%u delta=%d size=%u\n",alignment,delta,size);return 1;}
        ++count;
    }
    g_esp=32;MEM32(36)=MEM32(40)=MEM32(44)=0;fn();
    if(g_esp!=36||g_eax)return 1;
    printf("memmove override passed %u overlap/alignment/length cases, guards, return and cdecl stack\n",count+1);
    return 0;
}

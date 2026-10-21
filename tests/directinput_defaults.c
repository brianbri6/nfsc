/* Probe Windows' actual system keyboard/mouse defaults without cooperative level. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
typedef struct {const GUID* guid;DWORD offset,type,flags;} ObjectFormat;
typedef struct {DWORD size,objectSize,flags,dataSize,count;ObjectFormat* objects;} DataFormat;
typedef HRESULT (WINAPI* Factory)(HINSTANCE,DWORD,const GUID*,void**,void*);
typedef HRESULT (WINAPI* CreateDevice)(void*,const GUID*,void**,void*);
typedef HRESULT (WINAPI* SetFormat)(void*,const DataFormat*);
typedef HRESULT (WINAPI* Acquire)(void*);
typedef HRESULT (WINAPI* GetState)(void*,DWORD,void*);
int main(void){
    const GUID iid={0xbf798030,0x483a,0x4da2,{0xaa,0x99,0x5d,0x64,0xed,0x36,0x97,0}};
    const GUID keyboard={0x6f1d2b61,0xd5a0,0x11cf,{0xbf,0xc7,0x44,0x45,0x53,0x54,0,0}};
    const GUID mouse={0x6f1d2b60,0xd5a0,0x11cf,{0xbf,0xc7,0x44,0x45,0x53,0x54,0,0}};
    const GUID key={0x55728220,0xd33c,0x11cf,{0xbf,0xc7,0x44,0x45,0x53,0x54,0,0}};
    const GUID button={0xa36d02f0,0xc9f3,0x11cf,{0xbf,0xc7,0x44,0x45,0x53,0x54,0,0}};
    GUID axes[3];for(unsigned i=0;i<3;++i){axes[i]=button;axes[i].Data1=0xa36d02e0+i;}
    void* input=0;Factory factory=(Factory)GetProcAddress(LoadLibraryA("dinput8.dll"),"DirectInput8Create");
    HRESULT hr=factory(GetModuleHandleA(0),0x800,&iid,&input,0);if(hr)return 1;
    for(int kind=0;kind<2;++kind){
        void* device=0;void** table=*(void***)input;
        hr=((CreateDevice)table[3])(input,kind?&mouse:&keyboard,&device,0);if(hr)return 2;
        ObjectFormat objects[256];DWORD count=kind?11:256;
        for(DWORD i=0;i<count;++i){objects[i].guid=kind?(i<3?&axes[i]:&button):&key;objects[i].flags=0;
            objects[i].offset=kind?(i<3?i*4:12+i-3):i;
            objects[i].type=(kind&&i<3?2:12)|((i-(kind&&i>=3?3:0))<<8)|0x80000000u;
        }
        DataFormat format={24,16,2,kind?20:256,count,objects};if(!kind)format.flags=0;
        table=*(void***)device;hr=((SetFormat)table[11])(device,&format);
        HRESULT acquired=((Acquire)table[7])(device);unsigned char state[256];HRESULT read=((GetState)table[9])(device,format.dataSize,state);
        printf("%s format=%08lx acquire=%08lx state=%08lx\n",kind?"mouse":"keyboard",hr,acquired,read);
    }
    return 0;
}

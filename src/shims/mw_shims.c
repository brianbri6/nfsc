/*
 * mw_shims.c - Carbon import shims on top of the shared win32_shims.c.
 *
 * D3DXCreateEffectFromResourceA: speed.exe asks d3dx9_26 to load its effect
 * files (IDI_WORLD_FX, ...) from its own RT_RCDATA resources with hModule =
 * NULL. The real d3dx then searches the host exe, since speed.exe was mapped
 * by image_loader and is no module Windows knows, and fails with
 * D3DXERR_INVALIDDATA; the game later dereferences the missing effect. Here the
 * resource is found in the guest image and handed to D3DXCreateEffect, the
 * in-memory form of the same call with the same remaining arguments.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include "recomp_types.h"
#include "native32.h"
#include "nfs_runtime.h"
#include "nfs_log.h"

#define ARG(i) (*(uint32_t *)(uintptr_t)(g_esp + 4 + 4 * (i)))
#define RET(v, nargs) do { g_eax = (uint32_t)(v); g_esp += 4 + 4 * (nargs); } while (0)

static IMAGE_RESOURCE_DIRECTORY *rsrc_root(void) {
    IMAGE_NT_HEADERS32 *nt = (IMAGE_NT_HEADERS32 *)(uintptr_t)(NFS_GUEST_BASE +
        ((IMAGE_DOS_HEADER *)(uintptr_t)NFS_GUEST_BASE)->e_lfanew);
    IMAGE_DATA_DIRECTORY d = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_RESOURCE];
    return d.VirtualAddress ? (IMAGE_RESOURCE_DIRECTORY *)(uintptr_t)(NFS_GUEST_BASE + d.VirtualAddress) : NULL;
}

/* Entry of `dir` with integer id, or (wname != NULL) with that name. */
static IMAGE_RESOURCE_DIRECTORY_ENTRY *rsrc_find(IMAGE_RESOURCE_DIRECTORY *root, IMAGE_RESOURCE_DIRECTORY *dir,
                                                 WORD id, const wchar_t *wname) {
    IMAGE_RESOURCE_DIRECTORY_ENTRY *e = (IMAGE_RESOURCE_DIRECTORY_ENTRY *)(dir + 1);
    int n = dir->NumberOfNamedEntries + dir->NumberOfIdEntries;
    for (int i = 0; i < n; i++, e++) {
        if (wname) {
            if (!e->NameIsString) continue;
            IMAGE_RESOURCE_DIR_STRING_U *s = (IMAGE_RESOURCE_DIR_STRING_U *)((BYTE *)root + e->NameOffset);
            if ((int)wcslen(wname) == s->Length && !_wcsnicmp(wname, s->NameString, s->Length)) return e;
        } else if (!e->NameIsString && e->Id == id) {
            return e;
        }
    }
    return NULL;
}

/* RT_RCDATA resource `name` (string or #id) of the guest: data VA and size. */
static int guest_rcdata(uint32_t name, uint32_t *data, uint32_t *size) {
    IMAGE_RESOURCE_DIRECTORY *root = rsrc_root();
    wchar_t buf[256];
    const wchar_t *wname = NULL;
    WORD id = 0;
    if (!root) return 0;
    if (name < 0x10000) id = (WORD)name;
    else {
        MultiByteToWideChar(CP_ACP, 0, (const char *)(uintptr_t)name, -1, buf, 256);
        buf[255] = 0;
        if (buf[0] == L'#') id = (WORD)_wtoi(buf + 1); else wname = buf;
    }
    IMAGE_RESOURCE_DIRECTORY_ENTRY *t = rsrc_find(root, root, 10 /* RT_RCDATA */, NULL);
    if (!t || !t->DataIsDirectory) return 0;
    IMAGE_RESOURCE_DIRECTORY *td = (IMAGE_RESOURCE_DIRECTORY *)((BYTE *)root + t->OffsetToDirectory);
    IMAGE_RESOURCE_DIRECTORY_ENTRY *n = rsrc_find(root, td, id, wname);
    if (!n || !n->DataIsDirectory) return 0;
    IMAGE_RESOURCE_DIRECTORY *ld = (IMAGE_RESOURCE_DIRECTORY *)((BYTE *)root + n->OffsetToDirectory);
    if (ld->NumberOfNamedEntries + ld->NumberOfIdEntries == 0) return 0;
    IMAGE_RESOURCE_DIRECTORY_ENTRY *lang = (IMAGE_RESOURCE_DIRECTORY_ENTRY *)(ld + 1);
    if (lang->DataIsDirectory) return 0;
    IMAGE_RESOURCE_DATA_ENTRY *de = (IMAGE_RESOURCE_DATA_ENTRY *)((BYTE *)root + lang->OffsetToData);
    *data = NFS_GUEST_BASE + de->OffsetToData;
    *size = de->Size;
    return 1;
}

typedef HRESULT (WINAPI *create_effect_t)(void *, const void *, UINT, const void *, void *, DWORD, void *, void **, void **);
typedef HRESULT (WINAPI *create_from_resource_t)(void *, HMODULE, LPCSTR, const void *, void *, DWORD, void *, void **, void **);

/* HRESULT D3DXCreateEffectFromResourceA(device, hSrcModule, pSrcResource,
 *     pDefines, pInclude, Flags, pPool, ppEffect, ppCompilationErrors) */
static void shim_D3DXCreateEffectFromResourceA(void) {
    static create_effect_t create;
    static create_from_resource_t from_resource;
    uint32_t module = ARG(1), name = ARG(2), data = 0, size = 0;
    HRESULT hr;
    if (!create) {
        HMODULE d3dx = LoadLibraryA("d3dx9_26.dll");
        create = (create_effect_t)GetProcAddress(d3dx, "D3DXCreateEffect");
        from_resource = (create_from_resource_t)GetProcAddress(d3dx, "D3DXCreateEffectFromResourceA");
    }
    if ((module == 0 || module == NFS_GUEST_BASE) && guest_rcdata(name, &data, &size) && create) {
        hr = create((void *)(uintptr_t)ARG(0), (const void *)(uintptr_t)data, size,
                    (const void *)(uintptr_t)ARG(3), (void *)(uintptr_t)ARG(4), ARG(5),
                    (void *)(uintptr_t)ARG(6), (void **)(uintptr_t)ARG(7), (void **)(uintptr_t)ARG(8));
        NFS_LOG(D3D9, "D3DXCreateEffectFromResourceA(guest, %s): %u bytes -> %08lX",
                name < 0x10000 ? "#id" : (const char *)(uintptr_t)name, size, (unsigned long)hr);
    } else {
        hr = from_resource((void *)(uintptr_t)ARG(0), (HMODULE)(uintptr_t)module, (LPCSTR)(uintptr_t)name,
                           (const void *)(uintptr_t)ARG(3), (void *)(uintptr_t)ARG(4), ARG(5),
                           (void *)(uintptr_t)ARG(6), (void **)(uintptr_t)ARG(7), (void **)(uintptr_t)ARG(8));
        NFS_LOG(D3D9, "D3DXCreateEffectFromResourceA(module %08X) -> %08lX (resource %s)", module,
                (unsigned long)hr, data ? "found" : "not in the guest image");
    }
    RET((uint32_t)hr, 9);
}

native32_shim_t g_mw_shims[] = {
    { "D3DXCreateEffectFromResourceA", shim_D3DXCreateEffectFromResourceA },
};
int g_mw_nshims = sizeof g_mw_shims / sizeof g_mw_shims[0];

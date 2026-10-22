/*
 * CI-ONLY native link smoke fixture.
 * NOT generated from Need for Speed Carbon, not gameplay code.
 * Never include this file in a playable/release Android build.
 *
 * It supplies empty dispatch tables so that every native C++ host translation
 * unit and the Android/DXVK bridge can be compile- and link-checked without
 * copyrighted game executables, DLLs, or ABK sound data.
 */
#include "recomp_types.h"
#include "nfs_abk.h"

#define DECLARE_EMPTY_DISPATCH(prefix) \
    const recomp_dispatch_entry_t prefix##recomp_dispatch_table[1] = {{0, 0}}; \
    const uint32_t prefix##recomp_dispatch_count = 0

DECLARE_EMPTY_DISPATCH();
DECLARE_EMPTY_DISPATCH(d3dx_);
DECLARE_EMPTY_DISPATCH(msvcr_);
DECLARE_EMPTY_DISPATCH(msvcp_);
DECLARE_EMPTY_DISPATCH(abk_);

const nfs_abk_block_t nfs_abk_blocks[1] = {{0}};
const unsigned nfs_abk_block_count = 0;

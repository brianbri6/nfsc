/* Hand-written replacements for lifted NFSC.exe functions, by guest VA.
 * Carbon's addresses are discovered on its own binary; none is inherited
 * from the Underground or Most Wanted ports (Most Wanted replaced its static
 * CRT memmove; Carbon's memmove lives in msvcr71.dll). None needed yet. */
#include "nfs_runtime.h"
#include "recomp_types.h"
nfs_override_fn nfs_override_lookup(uint32_t va) { (void)va; return 0; }
int nfs_override_count(void) { return 0; }

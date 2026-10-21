/* Generic D3D9 observer ABI. No Underground HUD/FOV addresses are applied.
 * Carbon widescreen geometry and timing require their own validation. */
#include "nfs_widescreen.h"
void nfs_widescreen_set_resolution(unsigned width, unsigned height) {
    (void)width; (void)height;
}

/* Port Lab Maple VMU protocol adapter. GPL-2.0. */
#ifndef PORT_VMU_H
#define PORT_VMU_H
#include <stdint.h>
int port_vmu_init(void);
int port_vmu_connected(void);
void port_vmu_dma(uint32_t frame,const uint32_t *input,unsigned words,uint32_t *out);
#endif


/Users/swchen.tw/git/percepio/poc/runs/tcp-opt-checksum-os-v1/.build/tcp_checksum1/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80002d5e <lwip_standard_chksum>:
80002d5e:	4701                	li	a4,0
80002d60:	952e                	add	a0,a0,a1
80002d62:	4605                	li	a2,1
80002d64:	40b507b3          	sub	a5,a0,a1
80002d68:	02b64863          	blt	a2,a1,80002d98 <lwip_standard_chksum+0x3a>
80002d6c:	00c59863          	bne	a1,a2,80002d7c <lwip_standard_chksum+0x1e>
80002d70:	0007c783          	lbu	a5,0(a5)
80002d74:	0ff7f793          	zext.b	a5,a5
80002d78:	07a2                	slli	a5,a5,0x8
80002d7a:	973e                	add	a4,a4,a5
80002d7c:	01075513          	srli	a0,a4,0x10
80002d80:	0742                	slli	a4,a4,0x10
80002d82:	8341                	srli	a4,a4,0x10
80002d84:	953a                	add	a0,a0,a4
80002d86:	67c1                	lui	a5,0x10
80002d88:	00f537b3          	sltu	a5,a0,a5
80002d8c:	0017b793          	seqz	a5,a5
80002d90:	953e                	add	a0,a0,a5
80002d92:	0542                	slli	a0,a0,0x10
80002d94:	8141                	srli	a0,a0,0x10
80002d96:	a815                	j	80002dca <lwip_htons>
80002d98:	0007c683          	lbu	a3,0(a5) # 10000 <__stack_size+0xf000>
80002d9c:	0017c783          	lbu	a5,1(a5)
80002da0:	15f9                	addi	a1,a1,-2
80002da2:	07a2                	slli	a5,a5,0x8
80002da4:	8edd                	or	a3,a3,a5
80002da6:	06a2                	slli	a3,a3,0x8
80002da8:	83a1                	srli	a5,a5,0x8
80002daa:	97b6                	add	a5,a5,a3
80002dac:	07c2                	slli	a5,a5,0x10
80002dae:	83c1                	srli	a5,a5,0x10
80002db0:	973e                	add	a4,a4,a5
80002db2:	bf4d                	j	80002d64 <lwip_standard_chksum+0x6>


/Users/swchen.tw/git/percepio/poc/runs/tcp-checksum-v2/.build/tcp_checksum2/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80002d5e <lwip_standard_chksum>:
80002d5e:	4781                	li	a5,0
80002d60:	00157693          	andi	a3,a0,1
80002d64:	00b05863          	blez	a1,80002d74 <lwip_standard_chksum+0x16>
80002d68:	c691                	beqz	a3,80002d74 <lwip_standard_chksum+0x16>
80002d6a:	00054783          	lbu	a5,0(a0)
80002d6e:	15fd                	addi	a1,a1,-1
80002d70:	0505                	addi	a0,a0,1
80002d72:	07a2                	slli	a5,a5,0x8
80002d74:	4701                	li	a4,0
80002d76:	4605                	li	a2,1
80002d78:	02b64e63          	blt	a2,a1,80002db4 <lwip_standard_chksum+0x56>
80002d7c:	00c59763          	bne	a1,a2,80002d8a <lwip_standard_chksum+0x2c>
80002d80:	00054603          	lbu	a2,0(a0)
80002d84:	f007f793          	andi	a5,a5,-256
80002d88:	8fd1                	or	a5,a5,a2
80002d8a:	97ba                	add	a5,a5,a4
80002d8c:	0107d713          	srli	a4,a5,0x10
80002d90:	07c2                	slli	a5,a5,0x10
80002d92:	83c1                	srli	a5,a5,0x10
80002d94:	97ba                	add	a5,a5,a4
80002d96:	0107d513          	srli	a0,a5,0x10
80002d9a:	07c2                	slli	a5,a5,0x10
80002d9c:	83c1                	srli	a5,a5,0x10
80002d9e:	953e                	add	a0,a0,a5
80002da0:	c699                	beqz	a3,80002dae <lwip_standard_chksum+0x50>
80002da2:	00851793          	slli	a5,a0,0x8
80002da6:	8121                	srli	a0,a0,0x8
80002da8:	0ff57513          	zext.b	a0,a0
80002dac:	8d5d                	or	a0,a0,a5
80002dae:	0542                	slli	a0,a0,0x10
80002db0:	8141                	srli	a0,a0,0x10
80002db2:	8082                	ret
80002db4:	00055803          	lhu	a6,0(a0)
80002db8:	0509                	addi	a0,a0,2
80002dba:	15f9                	addi	a1,a1,-2
80002dbc:	9742                	add	a4,a4,a6
80002dbe:	bf6d                	j	80002d78 <lwip_standard_chksum+0x1a>


/Users/swchen.tw/git/percepio/poc/runs/tcp-opt-checksum-o2-v2/.build/tcp_checksum2/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80002d5e <lwip_standard_chksum>:
80002d5e:	00157813          	andi	a6,a0,1
80002d62:	4781                	li	a5,0
80002d64:	00b05963          	blez	a1,80002d76 <lwip_standard_chksum+0x18>
80002d68:	00080763          	beqz	a6,80002d76 <lwip_standard_chksum+0x18>
80002d6c:	00054783          	lbu	a5,0(a0)
80002d70:	15fd                	addi	a1,a1,-1
80002d72:	0505                	addi	a0,a0,1
80002d74:	07a2                	slli	a5,a5,0x8
80002d76:	4705                	li	a4,1
80002d78:	06b75963          	bge	a4,a1,80002dea <lwip_standard_chksum+0x8c>
80002d7c:	ffe58313          	addi	t1,a1,-2
80002d80:	00250893          	addi	a7,a0,2
80002d84:	ffe37613          	andi	a2,t1,-2
80002d88:	9646                	add	a2,a2,a7
80002d8a:	4701                	li	a4,0
80002d8c:	00055683          	lhu	a3,0(a0)
80002d90:	0509                	addi	a0,a0,2
80002d92:	9736                	add	a4,a4,a3
80002d94:	fec51ce3          	bne	a0,a2,80002d8c <lwip_standard_chksum+0x2e>
80002d98:	8185                	srli	a1,a1,0x1
80002d9a:	15fd                	addi	a1,a1,-1
80002d9c:	40b005b3          	neg	a1,a1
80002da0:	00159513          	slli	a0,a1,0x1
80002da4:	006505b3          	add	a1,a0,t1
80002da8:	40a88533          	sub	a0,a7,a0
80002dac:	4685                	li	a3,1
80002dae:	00d59763          	bne	a1,a3,80002dbc <lwip_standard_chksum+0x5e>
80002db2:	00054683          	lbu	a3,0(a0)
80002db6:	f007f793          	andi	a5,a5,-256
80002dba:	8fd5                	or	a5,a5,a3
80002dbc:	97ba                	add	a5,a5,a4
80002dbe:	01079713          	slli	a4,a5,0x10
80002dc2:	8341                	srli	a4,a4,0x10
80002dc4:	83c1                	srli	a5,a5,0x10
80002dc6:	00e78533          	add	a0,a5,a4
80002dca:	01051793          	slli	a5,a0,0x10
80002dce:	83c1                	srli	a5,a5,0x10
80002dd0:	8141                	srli	a0,a0,0x10
80002dd2:	953e                	add	a0,a0,a5
80002dd4:	00080863          	beqz	a6,80002de4 <lwip_standard_chksum+0x86>
80002dd8:	00855793          	srli	a5,a0,0x8
80002ddc:	0ff7f793          	zext.b	a5,a5
80002de0:	0522                	slli	a0,a0,0x8
80002de2:	8d5d                	or	a0,a0,a5
80002de4:	0542                	slli	a0,a0,0x10
80002de6:	8141                	srli	a0,a0,0x10
80002de8:	8082                	ret
80002dea:	4701                	li	a4,0
80002dec:	b7c1                	j	80002dac <lwip_standard_chksum+0x4e>

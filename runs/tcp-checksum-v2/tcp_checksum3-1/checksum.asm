
/Users/swchen.tw/git/percepio/poc/runs/tcp-checksum-v2/.build/tcp_checksum3/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80002d5e <lwip_standard_chksum>:
80002d5e:	4701                	li	a4,0
80002d60:	00157613          	andi	a2,a0,1
80002d64:	00b05863          	blez	a1,80002d74 <lwip_standard_chksum+0x16>
80002d68:	c611                	beqz	a2,80002d74 <lwip_standard_chksum+0x16>
80002d6a:	00054703          	lbu	a4,0(a0)
80002d6e:	15fd                	addi	a1,a1,-1
80002d70:	0505                	addi	a0,a0,1
80002d72:	0722                	slli	a4,a4,0x8
80002d74:	00357793          	andi	a5,a0,3
80002d78:	cfb9                	beqz	a5,80002dd6 <lwip_standard_chksum+0x78>
80002d7a:	0025a793          	slti	a5,a1,2
80002d7e:	efa1                	bnez	a5,80002dd6 <lwip_standard_chksum+0x78>
80002d80:	00055783          	lhu	a5,0(a0)
80002d84:	15f9                	addi	a1,a1,-2
80002d86:	0509                	addi	a0,a0,2
80002d88:	481d                	li	a6,7
80002d8a:	04b84863          	blt	a6,a1,80002dda <lwip_standard_chksum+0x7c>
80002d8e:	0107d693          	srli	a3,a5,0x10
80002d92:	07c2                	slli	a5,a5,0x10
80002d94:	83c1                	srli	a5,a5,0x10
80002d96:	97b6                	add	a5,a5,a3
80002d98:	4685                	li	a3,1
80002d9a:	04b6ce63          	blt	a3,a1,80002df6 <lwip_standard_chksum+0x98>
80002d9e:	00d59763          	bne	a1,a3,80002dac <lwip_standard_chksum+0x4e>
80002da2:	00054683          	lbu	a3,0(a0)
80002da6:	f0077713          	andi	a4,a4,-256
80002daa:	8f55                	or	a4,a4,a3
80002dac:	973e                	add	a4,a4,a5
80002dae:	01075793          	srli	a5,a4,0x10
80002db2:	0742                	slli	a4,a4,0x10
80002db4:	8341                	srli	a4,a4,0x10
80002db6:	97ba                	add	a5,a5,a4
80002db8:	0107d513          	srli	a0,a5,0x10
80002dbc:	07c2                	slli	a5,a5,0x10
80002dbe:	83c1                	srli	a5,a5,0x10
80002dc0:	953e                	add	a0,a0,a5
80002dc2:	c619                	beqz	a2,80002dd0 <lwip_standard_chksum+0x72>
80002dc4:	00851793          	slli	a5,a0,0x8
80002dc8:	8121                	srli	a0,a0,0x8
80002dca:	0ff57513          	zext.b	a0,a0
80002dce:	8d5d                	or	a0,a0,a5
80002dd0:	0542                	slli	a0,a0,0x10
80002dd2:	8141                	srli	a0,a0,0x10
80002dd4:	8082                	ret
80002dd6:	4781                	li	a5,0
80002dd8:	bf45                	j	80002d88 <lwip_standard_chksum+0x2a>
80002dda:	4114                	lw	a3,0(a0)
80002ddc:	0521                	addi	a0,a0,8
80002dde:	15e1                	addi	a1,a1,-8
80002de0:	97b6                	add	a5,a5,a3
80002de2:	00d7b6b3          	sltu	a3,a5,a3
80002de6:	97b6                	add	a5,a5,a3
80002de8:	ffc52683          	lw	a3,-4(a0)
80002dec:	97b6                	add	a5,a5,a3
80002dee:	00d7b6b3          	sltu	a3,a5,a3
80002df2:	97b6                	add	a5,a5,a3
80002df4:	bf59                	j	80002d8a <lwip_standard_chksum+0x2c>
80002df6:	00055803          	lhu	a6,0(a0)
80002dfa:	0509                	addi	a0,a0,2
80002dfc:	15f9                	addi	a1,a1,-2
80002dfe:	97c2                	add	a5,a5,a6
80002e00:	bf69                	j	80002d9a <lwip_standard_chksum+0x3c>


/Users/swchen.tw/git/percepio/poc/runs/tcp-opt-os-v1/enabled-1-1/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80003bd4 <lwip_standard_chksum>:
80003bd4:	4701                	li	a4,0
80003bd6:	00157613          	andi	a2,a0,1
80003bda:	00b05863          	blez	a1,80003bea <lwip_standard_chksum+0x16>
80003bde:	c611                	beqz	a2,80003bea <lwip_standard_chksum+0x16>
80003be0:	00054703          	lbu	a4,0(a0)
80003be4:	15fd                	addi	a1,a1,-1
80003be6:	0505                	addi	a0,a0,1
80003be8:	0722                	slli	a4,a4,0x8
80003bea:	00357793          	andi	a5,a0,3
80003bee:	cfb9                	beqz	a5,80003c4c <lwip_standard_chksum+0x78>
80003bf0:	0025a793          	slti	a5,a1,2
80003bf4:	efa1                	bnez	a5,80003c4c <lwip_standard_chksum+0x78>
80003bf6:	00055783          	lhu	a5,0(a0)
80003bfa:	15f9                	addi	a1,a1,-2
80003bfc:	0509                	addi	a0,a0,2
80003bfe:	481d                	li	a6,7
80003c00:	04b84863          	blt	a6,a1,80003c50 <lwip_standard_chksum+0x7c>
80003c04:	0107d693          	srli	a3,a5,0x10
80003c08:	07c2                	slli	a5,a5,0x10
80003c0a:	83c1                	srli	a5,a5,0x10
80003c0c:	97b6                	add	a5,a5,a3
80003c0e:	4685                	li	a3,1
80003c10:	04b6ce63          	blt	a3,a1,80003c6c <lwip_standard_chksum+0x98>
80003c14:	00d59763          	bne	a1,a3,80003c22 <lwip_standard_chksum+0x4e>
80003c18:	00054683          	lbu	a3,0(a0)
80003c1c:	f0077713          	andi	a4,a4,-256
80003c20:	8f55                	or	a4,a4,a3
80003c22:	973e                	add	a4,a4,a5
80003c24:	01075793          	srli	a5,a4,0x10
80003c28:	0742                	slli	a4,a4,0x10
80003c2a:	8341                	srli	a4,a4,0x10
80003c2c:	97ba                	add	a5,a5,a4
80003c2e:	0107d513          	srli	a0,a5,0x10
80003c32:	07c2                	slli	a5,a5,0x10
80003c34:	83c1                	srli	a5,a5,0x10
80003c36:	953e                	add	a0,a0,a5
80003c38:	c619                	beqz	a2,80003c46 <lwip_standard_chksum+0x72>
80003c3a:	00851793          	slli	a5,a0,0x8
80003c3e:	8121                	srli	a0,a0,0x8
80003c40:	0ff57513          	zext.b	a0,a0
80003c44:	8d5d                	or	a0,a0,a5
80003c46:	0542                	slli	a0,a0,0x10
80003c48:	8141                	srli	a0,a0,0x10
80003c4a:	8082                	ret
80003c4c:	4781                	li	a5,0
80003c4e:	bf45                	j	80003bfe <lwip_standard_chksum+0x2a>
80003c50:	4114                	lw	a3,0(a0)
80003c52:	0521                	addi	a0,a0,8
80003c54:	15e1                	addi	a1,a1,-8
80003c56:	97b6                	add	a5,a5,a3
80003c58:	00d7b6b3          	sltu	a3,a5,a3
80003c5c:	97b6                	add	a5,a5,a3
80003c5e:	ffc52683          	lw	a3,-4(a0)
80003c62:	97b6                	add	a5,a5,a3
80003c64:	00d7b6b3          	sltu	a3,a5,a3
80003c68:	97b6                	add	a5,a5,a3
80003c6a:	bf59                	j	80003c00 <lwip_standard_chksum+0x2c>
80003c6c:	00055803          	lhu	a6,0(a0)
80003c70:	0509                	addi	a0,a0,2
80003c72:	15f9                	addi	a1,a1,-2
80003c74:	97c2                	add	a5,a5,a6
80003c76:	bf69                	j	80003c10 <lwip_standard_chksum+0x3c>

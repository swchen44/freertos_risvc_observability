
/Users/swchen.tw/git/percepio/poc/runs/tcp-opt-o2-v1/enabled-1-1/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80003bd4 <lwip_standard_chksum>:
80003bd4:	00157313          	andi	t1,a0,1
80003bd8:	4801                	li	a6,0
80003bda:	00b05963          	blez	a1,80003bec <lwip_standard_chksum+0x18>
80003bde:	00030763          	beqz	t1,80003bec <lwip_standard_chksum+0x18>
80003be2:	00054803          	lbu	a6,0(a0)
80003be6:	15fd                	addi	a1,a1,-1
80003be8:	0505                	addi	a0,a0,1
80003bea:	0822                	slli	a6,a6,0x8
80003bec:	00357793          	andi	a5,a0,3
80003bf0:	c781                	beqz	a5,80003bf8 <lwip_standard_chksum+0x24>
80003bf2:	0025a793          	slti	a5,a1,2
80003bf6:	c3e9                	beqz	a5,80003cb8 <lwip_standard_chksum+0xe4>
80003bf8:	479d                	li	a5,7
80003bfa:	4701                	li	a4,0
80003bfc:	0cb7d563          	bge	a5,a1,80003cc6 <lwip_standard_chksum+0xf2>
80003c00:	0035d793          	srli	a5,a1,0x3
80003c04:	00379893          	slli	a7,a5,0x3
80003c08:	15e1                	addi	a1,a1,-8
80003c0a:	98aa                	add	a7,a7,a0
80003c0c:	fff78e13          	addi	t3,a5,-1
80003c10:	86aa                	mv	a3,a0
80003c12:	429c                	lw	a5,0(a3)
80003c14:	06a1                	addi	a3,a3,8
80003c16:	97ba                	add	a5,a5,a4
80003c18:	ffc6a603          	lw	a2,-4(a3)
80003c1c:	00e7b733          	sltu	a4,a5,a4
80003c20:	97ba                	add	a5,a5,a4
80003c22:	00c78733          	add	a4,a5,a2
80003c26:	00f737b3          	sltu	a5,a4,a5
80003c2a:	973e                	add	a4,a4,a5
80003c2c:	fed893e3          	bne	a7,a3,80003c12 <lwip_standard_chksum+0x3e>
80003c30:	41c007b3          	neg	a5,t3
80003c34:	078e                	slli	a5,a5,0x3
80003c36:	0521                	addi	a0,a0,8
80003c38:	95be                	add	a1,a1,a5
80003c3a:	8d1d                	sub	a0,a0,a5
80003c3c:	01071793          	slli	a5,a4,0x10
80003c40:	83c1                	srli	a5,a5,0x10
80003c42:	8341                	srli	a4,a4,0x10
80003c44:	4885                	li	a7,1
80003c46:	973e                	add	a4,a4,a5
80003c48:	02b8d763          	bge	a7,a1,80003c76 <lwip_standard_chksum+0xa2>
80003c4c:	87aa                	mv	a5,a0
80003c4e:	00b50e33          	add	t3,a0,a1
80003c52:	0007d603          	lhu	a2,0(a5)
80003c56:	0789                	addi	a5,a5,2
80003c58:	40fe06b3          	sub	a3,t3,a5
80003c5c:	9732                	add	a4,a4,a2
80003c5e:	fed8cae3          	blt	a7,a3,80003c52 <lwip_standard_chksum+0x7e>
80003c62:	0015d793          	srli	a5,a1,0x1
80003c66:	17fd                	addi	a5,a5,-1
80003c68:	40f007b3          	neg	a5,a5
80003c6c:	0786                	slli	a5,a5,0x1
80003c6e:	0509                	addi	a0,a0,2
80003c70:	15f9                	addi	a1,a1,-2
80003c72:	8d1d                	sub	a0,a0,a5
80003c74:	95be                	add	a1,a1,a5
80003c76:	4785                	li	a5,1
80003c78:	00f59863          	bne	a1,a5,80003c88 <lwip_standard_chksum+0xb4>
80003c7c:	00054783          	lbu	a5,0(a0)
80003c80:	f0087813          	andi	a6,a6,-256
80003c84:	00f86833          	or	a6,a6,a5
80003c88:	983a                	add	a6,a6,a4
80003c8a:	01081793          	slli	a5,a6,0x10
80003c8e:	83c1                	srli	a5,a5,0x10
80003c90:	01085813          	srli	a6,a6,0x10
80003c94:	00f80533          	add	a0,a6,a5
80003c98:	01051793          	slli	a5,a0,0x10
80003c9c:	83c1                	srli	a5,a5,0x10
80003c9e:	8141                	srli	a0,a0,0x10
80003ca0:	953e                	add	a0,a0,a5
80003ca2:	00030863          	beqz	t1,80003cb2 <lwip_standard_chksum+0xde>
80003ca6:	00855793          	srli	a5,a0,0x8
80003caa:	0ff7f793          	zext.b	a5,a5
80003cae:	0522                	slli	a0,a0,0x8
80003cb0:	8d5d                	or	a0,a0,a5
80003cb2:	0542                	slli	a0,a0,0x10
80003cb4:	8141                	srli	a0,a0,0x10
80003cb6:	8082                	ret
80003cb8:	15f9                	addi	a1,a1,-2
80003cba:	479d                	li	a5,7
80003cbc:	00055703          	lhu	a4,0(a0)
80003cc0:	0509                	addi	a0,a0,2
80003cc2:	f2b7cfe3          	blt	a5,a1,80003c00 <lwip_standard_chksum+0x2c>
80003cc6:	87ba                	mv	a5,a4
80003cc8:	bfad                	j	80003c42 <lwip_standard_chksum+0x6e>

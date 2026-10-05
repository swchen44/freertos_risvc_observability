
/Users/swchen.tw/git/percepio/poc/runs/tcp-opt-checksum-o2-v2/.build/tcp_checksum3/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80002d62 <lwip_standard_chksum>:
80002d62:	00157313          	andi	t1,a0,1
80002d66:	4801                	li	a6,0
80002d68:	00b05963          	blez	a1,80002d7a <lwip_standard_chksum+0x18>
80002d6c:	00030763          	beqz	t1,80002d7a <lwip_standard_chksum+0x18>
80002d70:	00054803          	lbu	a6,0(a0)
80002d74:	15fd                	addi	a1,a1,-1
80002d76:	0505                	addi	a0,a0,1
80002d78:	0822                	slli	a6,a6,0x8
80002d7a:	00357793          	andi	a5,a0,3
80002d7e:	c781                	beqz	a5,80002d86 <lwip_standard_chksum+0x24>
80002d80:	0025a793          	slti	a5,a1,2
80002d84:	c3e9                	beqz	a5,80002e46 <lwip_standard_chksum+0xe4>
80002d86:	479d                	li	a5,7
80002d88:	4701                	li	a4,0
80002d8a:	0cb7d563          	bge	a5,a1,80002e54 <lwip_standard_chksum+0xf2>
80002d8e:	0035d793          	srli	a5,a1,0x3
80002d92:	00379893          	slli	a7,a5,0x3
80002d96:	15e1                	addi	a1,a1,-8
80002d98:	98aa                	add	a7,a7,a0
80002d9a:	fff78e13          	addi	t3,a5,-1
80002d9e:	86aa                	mv	a3,a0
80002da0:	429c                	lw	a5,0(a3)
80002da2:	06a1                	addi	a3,a3,8
80002da4:	97ba                	add	a5,a5,a4
80002da6:	ffc6a603          	lw	a2,-4(a3)
80002daa:	00e7b733          	sltu	a4,a5,a4
80002dae:	97ba                	add	a5,a5,a4
80002db0:	00c78733          	add	a4,a5,a2
80002db4:	00f737b3          	sltu	a5,a4,a5
80002db8:	973e                	add	a4,a4,a5
80002dba:	fed893e3          	bne	a7,a3,80002da0 <lwip_standard_chksum+0x3e>
80002dbe:	41c007b3          	neg	a5,t3
80002dc2:	078e                	slli	a5,a5,0x3
80002dc4:	0521                	addi	a0,a0,8
80002dc6:	95be                	add	a1,a1,a5
80002dc8:	8d1d                	sub	a0,a0,a5
80002dca:	01071793          	slli	a5,a4,0x10
80002dce:	83c1                	srli	a5,a5,0x10
80002dd0:	8341                	srli	a4,a4,0x10
80002dd2:	4885                	li	a7,1
80002dd4:	973e                	add	a4,a4,a5
80002dd6:	02b8d763          	bge	a7,a1,80002e04 <lwip_standard_chksum+0xa2>
80002dda:	87aa                	mv	a5,a0
80002ddc:	00b50e33          	add	t3,a0,a1
80002de0:	0007d603          	lhu	a2,0(a5)
80002de4:	0789                	addi	a5,a5,2
80002de6:	40fe06b3          	sub	a3,t3,a5
80002dea:	9732                	add	a4,a4,a2
80002dec:	fed8cae3          	blt	a7,a3,80002de0 <lwip_standard_chksum+0x7e>
80002df0:	0015d793          	srli	a5,a1,0x1
80002df4:	17fd                	addi	a5,a5,-1
80002df6:	40f007b3          	neg	a5,a5
80002dfa:	0786                	slli	a5,a5,0x1
80002dfc:	0509                	addi	a0,a0,2
80002dfe:	15f9                	addi	a1,a1,-2
80002e00:	8d1d                	sub	a0,a0,a5
80002e02:	95be                	add	a1,a1,a5
80002e04:	4785                	li	a5,1
80002e06:	00f59863          	bne	a1,a5,80002e16 <lwip_standard_chksum+0xb4>
80002e0a:	00054783          	lbu	a5,0(a0)
80002e0e:	f0087813          	andi	a6,a6,-256
80002e12:	00f86833          	or	a6,a6,a5
80002e16:	983a                	add	a6,a6,a4
80002e18:	01081793          	slli	a5,a6,0x10
80002e1c:	83c1                	srli	a5,a5,0x10
80002e1e:	01085813          	srli	a6,a6,0x10
80002e22:	00f80533          	add	a0,a6,a5
80002e26:	01051793          	slli	a5,a0,0x10
80002e2a:	83c1                	srli	a5,a5,0x10
80002e2c:	8141                	srli	a0,a0,0x10
80002e2e:	953e                	add	a0,a0,a5
80002e30:	00030863          	beqz	t1,80002e40 <lwip_standard_chksum+0xde>
80002e34:	00855793          	srli	a5,a0,0x8
80002e38:	0ff7f793          	zext.b	a5,a5
80002e3c:	0522                	slli	a0,a0,0x8
80002e3e:	8d5d                	or	a0,a0,a5
80002e40:	0542                	slli	a0,a0,0x10
80002e42:	8141                	srli	a0,a0,0x10
80002e44:	8082                	ret
80002e46:	15f9                	addi	a1,a1,-2
80002e48:	479d                	li	a5,7
80002e4a:	00055703          	lhu	a4,0(a0)
80002e4e:	0509                	addi	a0,a0,2
80002e50:	f2b7cfe3          	blt	a5,a1,80002d8e <lwip_standard_chksum+0x2c>
80002e54:	87ba                	mv	a5,a4
80002e56:	bfad                	j	80002dd0 <lwip_standard_chksum+0x6e>

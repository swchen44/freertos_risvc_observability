
/Users/swchen.tw/git/percepio/poc/runs/tcp-opt-checksum-o2/.build/tcp_checksum1/firmware.elf:     file format elf32-littleriscv


Disassembly of section .init:

Disassembly of section .text:

80002d5e <lwip_standard_chksum>:
80002d5e:	4785                	li	a5,1
80002d60:	06b7d563          	bge	a5,a1,80002dca <lwip_standard_chksum+0x6c>
80002d64:	0015d793          	srli	a5,a1,0x1
80002d68:	00179813          	slli	a6,a5,0x1
80002d6c:	982a                	add	a6,a6,a0
80002d6e:	fff78893          	addi	a7,a5,-1
80002d72:	86aa                	mv	a3,a0
80002d74:	4601                	li	a2,0
80002d76:	0016c783          	lbu	a5,1(a3)
80002d7a:	0006c703          	lbu	a4,0(a3)
80002d7e:	0689                	addi	a3,a3,2
80002d80:	07a2                	slli	a5,a5,0x8
80002d82:	8f5d                	or	a4,a4,a5
80002d84:	0722                	slli	a4,a4,0x8
80002d86:	83a1                	srli	a5,a5,0x8
80002d88:	97ba                	add	a5,a5,a4
80002d8a:	07c2                	slli	a5,a5,0x10
80002d8c:	83c1                	srli	a5,a5,0x10
80002d8e:	963e                	add	a2,a2,a5
80002d90:	ff0693e3          	bne	a3,a6,80002d76 <lwip_standard_chksum+0x18>
80002d94:	411007b3          	neg	a5,a7
80002d98:	0786                	slli	a5,a5,0x1
80002d9a:	95be                	add	a1,a1,a5
80002d9c:	470d                	li	a4,3
80002d9e:	00e59963          	bne	a1,a4,80002db0 <lwip_standard_chksum+0x52>
80002da2:	8d1d                	sub	a0,a0,a5
80002da4:	00254783          	lbu	a5,2(a0)
80002da8:	0ff7f793          	zext.b	a5,a5
80002dac:	07a2                	slli	a5,a5,0x8
80002dae:	963e                	add	a2,a2,a5
80002db0:	01061713          	slli	a4,a2,0x10
80002db4:	8341                	srli	a4,a4,0x10
80002db6:	8241                	srli	a2,a2,0x10
80002db8:	67c1                	lui	a5,0x10
80002dba:	963a                	add	a2,a2,a4
80002dbc:	00f66363          	bltu	a2,a5,80002dc2 <lwip_standard_chksum+0x64>
80002dc0:	0605                	addi	a2,a2,1
80002dc2:	0642                	slli	a2,a2,0x10
80002dc4:	8241                	srli	a2,a2,0x10
80002dc6:	8532                	mv	a0,a2
80002dc8:	a01d                	j	80002dee <lwip_htons>
80002dca:	4601                	li	a2,0
80002dcc:	fef59de3          	bne	a1,a5,80002dc6 <lwip_standard_chksum+0x68>
80002dd0:	00054603          	lbu	a2,0(a0)
80002dd4:	0622                	slli	a2,a2,0x8
80002dd6:	b7f5                	j	80002dc2 <lwip_standard_chksum+0x64>

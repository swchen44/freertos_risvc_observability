
/opt/homebrew/bin/qemu-system-riscv32:	file format mach-o arm64

Disassembly of section __TEXT,__text:

0000000100072ea4 <_tcg_accel_ops_init>:
100072ea4: a9be4ff4    	stp	x20, x19, [sp, #-0x20]!
100072ea8: a9017bfd    	stp	x29, x30, [sp, #0x10]
100072eac: 910043fd    	add	x29, sp, #0x10
100072eb0: f9403413    	ldr	x19, [x0, #0x68]
100072eb4: 97ffbf86    	bl	0x100062ccc <_qemu_tcg_mttcg_enabled>
100072eb8: 340000e0    	cbz	w0, 0x100072ed4 <_tcg_accel_ops_init+0x30>
100072ebc: b0000008    	adrp	x8, 0x100073000 <_tcg_insert_gdbstub_breakpoint+0x70>
100072ec0: 910fa108    	add	x8, x8, #0x3e8
100072ec4: f0ffff29    	adrp	x9, 0x100059000 <_cpu_exec_step_atomic+0x118>
100072ec8: 91101129    	add	x9, x9, #0x404
100072ecc: a9082668    	stp	x8, x9, [x19, #0x80]
100072ed0: 14000012    	b	0x100072f18 <_tcg_accel_ops_init+0x74>
100072ed4: b0000008    	adrp	x8, 0x100073000 <_tcg_insert_gdbstub_breakpoint+0x70>
100072ed8: 911b4108    	add	x8, x8, #0x6d0
100072edc: b0000009    	adrp	x9, 0x100073000 <_tcg_insert_gdbstub_breakpoint+0x70>
100072ee0: 911a4129    	add	x9, x9, #0x690
100072ee4: a9082668    	stp	x8, x9, [x19, #0x80]
100072ee8: d0004f88    	adrp	x8, 0x100a64000 <__TRACE_QMP_EXIT_QUERY_SEV_LAUNCH_MEASURE_EVENT+0x8>
100072eec: 913fc108    	add	x8, x8, #0xff0
100072ef0: b9400108    	ldr	w8, [x8]
100072ef4: 34000128    	cbz	w8, 0x100072f18 <_tcg_accel_ops_init+0x74>
100072ef8: b0000008    	adrp	x8, 0x100073000 <_tcg_insert_gdbstub_breakpoint+0x70>
100072efc: 910df108    	add	x8, x8, #0x37c
100072f00: f9005e68    	str	x8, [x19, #0xb8]
100072f04: 90000008    	adrp	x8, 0x100072000 <_OUTLINED_FUNCTION_0+0x14>
100072f08: 9107c108    	add	x8, x8, #0x1f0
100072f0c: f9006668    	str	x8, [x19, #0xc8]
100072f10: f9006e68    	str	x8, [x19, #0xd8]
100072f14: 14000004    	b	0x100072f24 <_tcg_accel_ops_init+0x80>
100072f18: 90000008    	adrp	x8, 0x100072000 <_OUTLINED_FUNCTION_0+0x14>
100072f1c: 91377108    	add	x8, x8, #0xddc
100072f20: f9005e68    	str	x8, [x19, #0xb8]
100072f24: 90000008    	adrp	x8, 0x100072000 <_OUTLINED_FUNCTION_0+0x14>
100072f28: 913db108    	add	x8, x8, #0xf6c
100072f2c: 90000009    	adrp	x9, 0x100072000 <_OUTLINED_FUNCTION_0+0x14>
100072f30: 913e4129    	add	x9, x9, #0xf90
100072f34: b000000a    	adrp	x10, 0x100073000 <_tcg_insert_gdbstub_breakpoint+0x70>
100072f38: 9101e14a    	add	x10, x10, #0x78
100072f3c: f9003e68    	str	x8, [x19, #0x78]
100072f40: a90eaa69    	stp	x9, x10, [x19, #0xe8]
100072f44: b0000008    	adrp	x8, 0x100073000 <_tcg_insert_gdbstub_breakpoint+0x70>
100072f48: 91055108    	add	x8, x8, #0x154
100072f4c: f9007e68    	str	x8, [x19, #0xf8]
100072f50: a9417bfd    	ldp	x29, x30, [sp, #0x10]
100072f54: a8c24ff4    	ldp	x20, x19, [sp], #0x20
100072f58: d2800000    	mov	x0, #0x0                ; =0
100072f5c: d2800008    	mov	x8, #0x0                ; =0
100072f60: d2800009    	mov	x9, #0x0                ; =0
100072f64: d280000a    	mov	x10, #0x0               ; =0
100072f68: d65f03c0    	ret

00000001000f275c <_qemu_plugin_update_ns>:
1000f275c: b0004d88    	adrp	x8, 0x100aa3000 <_all_cts+0x1300>
1000f2760: 9120a108    	add	x8, x8, #0x828
1000f2764: eb08001f    	cmp	x0, x8
1000f2768: 54000060    	b.eq	0x1000f2774 <_qemu_plugin_update_ns+0x18>
1000f276c: d2800008    	mov	x8, #0x0                ; =0
1000f2770: d65f03c0    	ret
1000f2774: a9bf7bfd    	stp	x29, x30, [sp, #-0x10]!
1000f2778: 910003fd    	mov	x29, sp
1000f277c: aa0103e2    	mov	x2, x1
1000f2780: d0004b80    	adrp	x0, 0x100a64000 <__TRACE_QMP_EXIT_QUERY_SEV_LAUNCH_MEASURE_EVENT+0x8>
1000f2784: 912c4000    	add	x0, x0, #0xb10
1000f2788: f9400008    	ldr	x8, [x0]
1000f278c: d63f0100    	blr	x8
1000f2790: f9400000    	ldr	x0, [x0]
1000f2794: 90000001    	adrp	x1, 0x1000f2000 <_do_op3+0xd4>
1000f2798: 911ea021    	add	x1, x1, #0x7a8
1000f279c: a8c17bfd    	ldp	x29, x30, [sp], #0x10
1000f27a0: d2800008    	mov	x8, #0x0                ; =0
1000f27a4: 17fcd9df    	b	0x100028f20 <_async_run_on_cpu>

000000010026a1a4 <_cpus_set_virtual_clock>:
10026a1a4: d00041c8    	adrp	x8, 0x100aa4000 <_expand2+0xac>
10026a1a8: f9439d08    	ldr	x8, [x8, #0x738]
10026a1ac: b40000a8    	cbz	x8, 0x10026a1c0 <_cpus_set_virtual_clock+0x1c>
10026a1b0: f9406901    	ldr	x1, [x8, #0xd0]
10026a1b4: b4000061    	cbz	x1, 0x10026a1c0 <_cpus_set_virtual_clock+0x1c>
10026a1b8: d2800008    	mov	x8, #0x0                ; =0
10026a1bc: d61f0020    	br	x1
10026a1c0: d2800008    	mov	x8, #0x0                ; =0
10026a1c4: d65f03c0    	ret

import json
import shlex
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

HARNESS = r"""
#include <qemu-plugin.h>
#include <stdint.h>
#include <stdlib.h>
#include "live_context.h"
static int failure;
static uint32_t task=0x80001000;
GArray *qemu_plugin_get_registers(void) {
 GArray *a=g_array_new(FALSE,FALSE,sizeof(qemu_plugin_reg_descriptor));
 qemu_plugin_reg_descriptor d={(struct qemu_plugin_register*)1,"mcause",NULL};
 if(failure!=1) g_array_append_val(a,d);
 return a;
}
int qemu_plugin_read_register(struct qemu_plugin_register *handle,GByteArray *b) {
 (void)handle;
 if(failure==2)return -1;
 g_byte_array_set_size(b,4);uint32_t v=0x80000007;
 for(unsigned i=0;i<4;i++) b->data[i]=(v>>(8*i))&255;
 if(failure==4)g_byte_array_set_size(b,0);
 return 4;
}
bool qemu_plugin_read_memory_vaddr(uint64_t address,GByteArray *b,size_t len) {
 (void)address;(void)len;
 if(failure==3)return false;
 g_byte_array_set_size(b,4);
 for(unsigned i=0;i<4;i++) b->data[i]=(task>>(8*i))&255;
 return true;
}
int main(int argc,char **argv) {
 if(argc!=4)return 3;
 failure=atoi(argv[3]);
 if(context_init(argv[1],argv[2]))return 2;
 context_vcpu_init(0,0);
 context_before_instruction(0,0x80000000);
 context_before_instruction(2,0x80000010);
 task=0x80002000;
 context_before_instruction(3,0x80000008);
 context_after_instruction(4,0x80000014);
 context_before_instruction(5,0x80000018);
 context_before_instruction(10,0x80000004);
 return context_finish(10);
}
"""
CONFIG = """version=1
xlen=32
endian=1
capture_begin_pc=2147483648
capture_end_pc=2147483652
trap_entry_pc=2147483664
selected_task_pc=2147483656
current_tcb_address=2148007936
mret_count=1
mret_0=2147483668
"""


class LiveContextTests(unittest.TestCase):
    def test_stub_boundaries_faults_and_config_validation(self):
        root = Path.cwd()
        self.assertTrue((root / "tools/tcp/live_context.c").exists())
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "harness.c").write_text(HARNESS)
            flags = shlex.split(
                subprocess.check_output(["pkg-config", "--cflags", "--libs", "glib-2.0"], text=True)
            )
            result = subprocess.run(
                [
                    "cc",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-I" + str(root / "references/qemu-time-control/include/qemu"),
                    "-I" + str(root / "tools/tcp"),
                    str(out / "harness.c"),
                    str(root / "tools/tcp/live_context.c"),
                    "-o",
                    str(out / "test"),
                    *flags,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = out / "config"
            config.write_text(CONFIG)
            for fault in range(5):
                output = out / f"events-{fault}.jsonl"
                result = subprocess.run(
                    [str(out / "test"), str(config), str(output), str(fault)],
                    capture_output=True,
                    text=True,
                )
                events = [json.loads(line) for line in output.read_text().splitlines()]
                if fault:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("fault", [e["kind"] for e in events])
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        [e["kind"] for e in events],
                        [
                            "begin",
                            "trap_enter",
                            "selected_task",
                            "mret_pending",
                            "return_commit",
                            "end",
                        ],
                    )
                    self.assertEqual([e["event_index"] for e in events], [0, 2, 3, 4, 5, 10])
                    from psf_lab.execution_context import context_intervals

                    r = context_intervals(events, raw_events=10, task_ids={0x80001000, 0x80002000})
                    self.assertEqual(
                        [(i["start"], i["end"], i["context"]) for i in r["intervals"]],
                        [(0, 2, "task:2147487744"), (2, 5, "irq:7"), (5, 10, "task:2147491840")],
                    )
                    again = subprocess.run(
                        [str(out / "test"), str(config), str(output), "0"], capture_output=True
                    )
                    self.assertNotEqual(again.returncode, 0)
            for n, invalid in enumerate(
                (
                    CONFIG + "unknown=1\n",
                    CONFIG + "version=1\n",
                    CONFIG.replace("version=1", "version=2"),
                    CONFIG.replace("2147483648", "2147483649"),
                )
            ):
                config.write_text(invalid)
                result = subprocess.run(
                    [str(out / "test"), str(config), str(out / f"bad-{n}"), "0"],
                    capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)

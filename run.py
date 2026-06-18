"""RTOS もどきを動かして, スケジューリングのタイムラインを表示する。

    python run.py

外部ライブラリは不要 (標準ライブラリだけ)。
"""

from __future__ import annotations

from picvm import CPU
from picasm import assemble
from rtos import Scheduler

# 監視する LED レジスタ (demo.asm の EQU と合わせる)
LEDS = {"LED0": 0x20, "LED1": 0x21, "LED2": 0x22}


def main():
    with open("demo.asm", encoding="utf-8") as f:
        program, symbols = assemble(f.read())

    cpu = CPU(program)
    sched = Scheduler(cpu)
    # タスク生成: 名前と入口アドレス (ラベル) を渡すだけ
    for name in ("task0", "task1", "task2"):
        sched.create_task(name, symbols[name])

    # ヘッダ
    cols = "  ".join(LEDS.keys())
    print(f"{'slice':>5}  {'task':<6} {'steps':>5}   {cols}")
    print("-" * 40)

    slice_no = [0]

    def on_slice(tcb, status, steps):
        leds = "    ".join(f"{cpu.ram[addr]:>3}" for addr in LEDS.values())
        print(f"{slice_no[0]:>5}  {tcb.name:<6} {steps:>5}    {leds}")
        slice_no[0] += 1

    sched.run(slices=12, on_slice=on_slice)

    print("-" * 40)
    final = ", ".join(f"{k}={cpu.ram[a]}" for k, a in LEDS.items())
    print("final:", final)


if __name__ == "__main__":
    main()

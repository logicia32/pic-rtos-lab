"""RTOS もどき: 協調型ラウンドロビン・スケジューラ。

各タスクは TCB (タスク制御ブロック) を 1 つ持つ。TCB には、タスクが
明け渡した時点の「コンテキスト」一式を保存しておく。次にそのタスクへ
戻すとき、保存しておいたコンテキストを CPU に書き戻せば、タスクは
中断されたことに気づかず続きから走る。これが文脈切り替えの本体。

PIC で特別なのは、コンテキストに「ハードウェアリターンスタックの中身」
まで関わること。普通の CPU ならスタックポインタ 1 個で済むところを、PIC は
タスクの続きを表すのにこの浅いスタックの面倒まで見ないといけない。この教材
VM ではスタックをリストとして丸ごと退避するが、本物の PIC18 では TOS 経由で
1 段ずつ動かす (pic18/ の忠実版を参照)。save_context / load_context が
それを単純化して見せている。

ファイルレジスタ (RAM) はタスク間で共有 = 各タスクは別領域を使う前提。
共有なのでメッセージのやり取りにも使える (タスク間通信は次の宿題)。
"""

from __future__ import annotations

READY, RUNNING, DONE = "ready", "running", "done"


class TCB:
    def __init__(self, name, entry_pc, stack_depth):
        self.name = name
        self.state = READY
        # --- 退避しておくコンテキスト一式 ---
        self.pc = entry_pc
        self.w = 0
        self.z = False
        self.c = False
        self.stack = [0] * stack_depth   # ハードスタックの中身を丸ごと持つ
        self.stkptr = 0


class Scheduler:
    def __init__(self, cpu):
        self.cpu = cpu
        self.tasks = []

    def create_task(self, name, entry_pc):
        """タスクを 1 つ生成する。entry_pc はそのタスクの入口アドレス。"""
        tcb = TCB(name, entry_pc, self.cpu.stack_depth)
        self.tasks.append(tcb)
        return tcb

    # ---- コンテキストの退避 / 復元 ---------------------------------------
    def _save_context(self, tcb):
        cpu = self.cpu
        tcb.pc = cpu.pc
        tcb.w = cpu.w
        tcb.z = cpu.z
        tcb.c = cpu.c
        tcb.stack = cpu.stack[:]      # ハードスタックを丸ごとコピーして退避
        tcb.stkptr = cpu.stkptr

    def _load_context(self, tcb):
        cpu = self.cpu
        cpu.pc = tcb.pc
        cpu.w = tcb.w
        cpu.z = tcb.z
        cpu.c = tcb.c
        cpu.stack = tcb.stack[:]      # 退避してあったスタックを書き戻す
        cpu.stkptr = tcb.stkptr

    # ---- スケジューラ本体 (ラウンドロビン) ------------------------------
    def run(self, slices, on_slice=None, max_steps=10000):
        """最大 slices 回, READY なタスクを順番に走らせる。

        on_slice(tcb, status, steps) が指定されていれば各スライス後に呼ぶ
        (トレース可視化用)。全タスクが DONE になったら早期終了。
        """
        if not self.tasks:
            return
        cur = 0
        n = len(self.tasks)
        for _ in range(slices):
            # 次に走らせる READY なタスクを探す
            scanned = 0
            while self.tasks[cur].state == DONE and scanned < n:
                cur = (cur + 1) % n
                scanned += 1
            tcb = self.tasks[cur]
            if tcb.state == DONE:
                break   # 走らせるものが無い

            # 文脈を載せて 1 スライス走らせ, 文脈を退避する
            self._load_context(tcb)
            tcb.state = RUNNING
            status, steps = self.cpu.run_slice(max_steps=max_steps)
            self._save_context(tcb)
            tcb.state = DONE if status == "halt" else READY

            if on_slice is not None:
                on_slice(tcb, status, steps)

            cur = (cur + 1) % n   # ラウンドロビン: 次のタスクへ

"""PIC 風の極小 8bit 仮想 CPU。

本物の PIC18 をビット単位で再現するものではなく、RTOS もどきの
スケジューラを「動かして見せる」ためだけの教材用 VM。ただし、PIC を
選んだ理由そのものである次の 1 点だけは本物に寄せている:

    戻り番地は「ハードウェアのリターンスタック」に積まれる。
    深さに上限があり (本物の PIC16 は 8 段, PIC18 は 31 段)、
    そのスタックの中身を退避/復元しないとタスクを切り替えられない。

普通の CPU はスタックポインタ 1 個を退避すれば済むが、PIC では「タスクの
続き」を表すのに、この浅いリターンスタックの中身まで面倒を見ないといけない。
ここを下の save_context / load_context で見せている。

ただし本物のハードウェアとは扱いが違う点に注意:
- 本物の PIC16 (mid-range) はハードスタックの中身にソフトから一切触れない
  (TOS レジスタも PUSH/POP も無い)。本来「丸ごとコピー」はできない。
- 本物の PIC18 は TOS 経由でてっぺんに手が届く。1 段ずつ動かす必要がある。
この VM はそこを「リスト丸ごとコピー」に単純化した教材。TOS を 1 段ずつ
動かす忠実版は pic18/ のアセンブラ実装にある。

簡略化したところ (教材なので割り切り):
- バンク切り替え (BSR) は無し。ファイルレジスタは単一バンク 256 個。
- MOVF / INCF / DECF の行き先 (d ビット) は固定。
- 命令は 16bit ワードにエンコードせず、タプルのまま実行する。
- ハードスタックはリスト丸ごと退避/復元 (本物の TOS 経由ではない)。
"""

from __future__ import annotations

from collections import namedtuple

# アセンブラが吐く 1 命令。name=ニーモニック, a/b=オペランド。
Instr = namedtuple("Instr", ["name", "a", "b"])

STACK_DEPTH = 8   # 本物の PIC16 相当の浅さ。PIC18 なら 31。


class StackError(RuntimeError):
    """ハードスタックのあふれ/から読み。PIC の有名な落とし穴を再現する。"""


class CPU:
    def __init__(self, program, ram_size=256, stack_depth=STACK_DEPTH):
        self.prog = program          # list[Instr] : プログラムメモリ (全タスク共有)
        self.ram = [0] * ram_size    # ファイルレジスタ (全タスク共有メモリ)
        self.stack_depth = stack_depth

        # --- ここから下がタスクごとの「コンテキスト」 ---
        self.pc = 0
        self.w = 0                   # アキュムレータ (W レジスタ)
        self.z = False               # ゼロフラグ
        self.c = False               # キャリーフラグ
        self.stack = [0] * stack_depth   # ハードウェアリターンスタック
        self.stkptr = 0                  # スタックポインタ (次に積む位置)

    # ---- ハードウェアリターンスタック ------------------------------------
    def _push(self, addr):
        if self.stkptr >= self.stack_depth:
            raise StackError(
                f"リターンスタックあふれ (深さ {self.stack_depth} 段)。"
                "CALL を入れ子にしすぎ。PIC ではこれが実際に起きる。"
            )
        self.stack[self.stkptr] = addr
        self.stkptr += 1

    def _pop(self):
        if self.stkptr <= 0:
            raise StackError("リターンスタックがからなのに RETURN した。")
        self.stkptr -= 1
        return self.stack[self.stkptr]

    def _setz(self, v):
        self.z = (v & 0xFF) == 0

    # ---- 1 命令実行 -------------------------------------------------------
    def step(self):
        """1 命令進める。戻り値は 'run' / 'yield' / 'halt'。"""
        op = self.prog[self.pc]
        name = op.name
        nxt = self.pc + 1   # 既定では次の命令へ

        if name == "NOP":
            pass
        elif name == "MOVLW":          # W <- 即値
            self.w = op.a & 0xFF
        elif name == "MOVWF":          # file[f] <- W
            self.ram[op.a] = self.w
        elif name == "MOVF":           # W <- file[f]
            self.w = self.ram[op.a]
            self._setz(self.w)
        elif name == "CLRF":           # file[f] <- 0
            self.ram[op.a] = 0
            self.z = True
        elif name == "ADDLW":          # W <- W + 即値
            r = self.w + (op.a & 0xFF)
            self.c = r > 0xFF
            self.w = r & 0xFF
            self._setz(self.w)
        elif name == "ADDWF":          # W <- W + file[f]
            r = self.w + self.ram[op.a]
            self.c = r > 0xFF
            self.w = r & 0xFF
            self._setz(self.w)
        elif name == "INCF":           # file[f] <- file[f] + 1
            v = (self.ram[op.a] + 1) & 0xFF
            self.ram[op.a] = v
            self._setz(v)
        elif name == "DECF":           # file[f] <- file[f] - 1
            v = (self.ram[op.a] - 1) & 0xFF
            self.ram[op.a] = v
            self._setz(v)
        elif name == "DECFSZ":         # file[f]-- し, 0 なら次を飛ばす
            v = (self.ram[op.a] - 1) & 0xFF
            self.ram[op.a] = v
            nxt = self.pc + 2 if v == 0 else self.pc + 1
        elif name == "BTFSS":          # file[f] の bit が 1 なら次を飛ばす
            bit = (self.ram[op.a] >> op.b) & 1
            nxt = self.pc + 2 if bit else self.pc + 1
        elif name == "BTFSC":          # file[f] の bit が 0 なら次を飛ばす
            bit = (self.ram[op.a] >> op.b) & 1
            nxt = self.pc + 2 if not bit else self.pc + 1
        elif name == "GOTO":
            nxt = op.a
        elif name == "CALL":
            self._push(self.pc + 1)
            nxt = op.a
        elif name == "RETURN":
            nxt = self._pop()
        elif name == "YIELD":          # 協調型スケジューラへの自発的な明け渡し
            self.pc = nxt              # YIELD の次から再開できるよう先に進めておく
            return "yield"
        elif name == "HALT":
            return "halt"
        else:
            raise ValueError(f"未知の命令: {name}")

        self.pc = nxt
        return "run"

    def run_slice(self, max_steps=10000):
        """YIELD か HALT に当たるまで走らせる (協調型の 1 スライス)。

        戻り値 (status, steps)。max_steps は暴走タスクの保険。
        """
        steps = 0
        while steps < max_steps:
            status = self.step()
            steps += 1
            if status != "run":
                return status, steps
        return "timeout", steps

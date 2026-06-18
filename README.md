# pic-rtos-lab 🧵

**A tiny cooperative scheduler ("RTOS-like") for PIC, built to see what the
hardware return stack does to a context switch.** Two versions: a real PIC18
kernel in assembly that runs on the **gpsim** simulator, and a pure-Python
teaching VM of the same idea. No hardware, no proprietary tools — `apt install`
and run.

> 日本語: PIC で最小の協調スケジューラ（RTOS もどき）を作る実験です。本物の PIC18 を
> アセンブラで書いて gpsim で動かす版と、同じ仕組みを純 Python で書いた教材 VM の
> 二本立て。狙いは「31 段しかないハードウェアリターンスタックが、文脈切り替えに何を
> 強いるのか」を、実機なし・OSS だけで観察すること。

---

## なぜ作ったか

普通の CPU の文脈切り替えは、スタックポインタ 1 個を差し替えれば済みます。PIC は
戻り番地が専用の「ハードウェアリターンスタック」に積まれ、深さに上限があります
（PIC18 で 31 段）。だから切り替えのたびに、走行中タスクの戻り番地を TOS から各
タスクの保存領域（TCB）へ逃がし、次タスクのを積み直す必要がある。これを怠ると
31 段の壁にぶつかります。その「逃がす／積み直す」を最小限で書いて、動かして見ます。

## 構成

- **`pic18/`** — 本物の PIC18 版。gpasm でアセンブル、gpsim で実行。詳細は
  [`pic18/README.md`](pic18/README.md)。
- **ルート直下**（`picvm.py` / `picasm.py` / `rtos.py` / `demo.asm` / `run.py`）—
  同じ仕組みを純 Python で書いた教材 VM。

## 動かす: 本物の PIC18 版（gpsim）

```sh
sudo apt install gputils gpsim     # どちらも OSS
cd pic18
make run            # 協調 2 タスク: STKPTR が 0〜1 から増えない
make run-overflow   # 落とし穴: yield せず潜って 31 段の壁にぶつかる
```

`make run` は 2 つのタスクが交互に走り（戻り番地を TCB へ逃がすので STKPTR は 0〜1）、
`make run-overflow` は逃がさずに潜り続けてハードスタックを 31 段まで埋める様子を、
gpsim のレジスタで観察します。読み方は [`pic18/README.md`](pic18/README.md) に。

## 動かす: 純 Python の教材 VM

```sh
python3 run.py
```

PIC 風の極小 VM 上でスケジューラを回し、どのタスクがいつ走ったかをタイムラインで
表示します（標準ライブラリだけ）。こちらは本物の PIC 命令ではなく「PIC 風の教材 VM」
である点を割り切っています（詳細は `picvm.py` 冒頭のコメント）。

## License

MIT — see [LICENSE](LICENSE).

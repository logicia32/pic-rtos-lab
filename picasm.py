"""極小 2 パスアセンブラ。

PIC 風ニーモニックのテキストを picvm.Instr のリストに変換する。
ラベル (タスクの入口) とレジスタ名 (EQU) を解決するだけの素朴なもの。

書式:
    NAME EQU 0x20      ; レジスタ名やシンボルの定義
    label:             ; ラベル (この位置の命令アドレスを覚える)
        MOVLW 1        ; 命令 + オペランド
    ; のあとはコメント

制約 (教材なので割り切り):
- EQU の右辺は「その行までに定義済み」のシンボルのみ (後方参照は不可)。
- オペランドはカンマ / 空白どちらの区切りでも可。
"""

from __future__ import annotations

from picvm import Instr

# オペランドを 2 個取る命令 (BTFSS f,b の bit 指定など)
TWO_ARG = {"BTFSS", "BTFSC"}
# オペランドを取らない命令
ZERO_ARG = {"NOP", "RETURN", "YIELD", "HALT"}


def _resolve(token, symbols):
    """シンボル名・16進・10進のいずれかを整数に解決する。"""
    if token in symbols:
        return symbols[token]
    t = token.lower()
    if t.startswith("0x"):
        return int(t, 16)
    return int(t, 10)


def assemble(text):
    """ソース文字列を (program, symbols) に変換する。

    program : list[Instr]
    symbols : dict[str, int]   (ラベルと EQU の両方を含む)
    """
    # --- パス 1: ラベルと EQU を集め、命令行だけ取り出す ---
    symbols = {}
    raw = []   # [(mnemonic, [operand_token, ...]), ...]
    for line in text.splitlines():
        line = line.split(";", 1)[0].strip()   # コメント除去
        if not line:
            continue

        # EQU 定義
        parts = line.split()
        if len(parts) == 3 and parts[1].upper() == "EQU":
            symbols[parts[0]] = _resolve(parts[2], symbols)
            continue

        # 行頭のラベル (複数・命令併記も許す)
        while parts and parts[0].endswith(":"):
            symbols[parts[0][:-1]] = len(raw)   # 次に積む命令のアドレス
            parts = parts[1:]
        if not parts:
            continue

        mnem = parts[0].upper()
        # オペランドはカンマ区切り。"F,0" でも "F, 0" でも同じに割る。
        operands = " ".join(parts[1:]).replace(",", " ").split()
        raw.append((mnem, operands))

    # --- パス 2: オペランドを解決して Instr を作る ---
    program = []
    for mnem, operands in raw:
        if mnem in ZERO_ARG:
            program.append(Instr(mnem, None, None))
        elif mnem in TWO_ARG:
            a = _resolve(operands[0], symbols)
            b = _resolve(operands[1], symbols)
            program.append(Instr(mnem, a, b))
        else:
            a = _resolve(operands[0], symbols)
            program.append(Instr(mnem, a, None))

    return program, symbols

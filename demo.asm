; ====================================================================
;  RTOS もどき デモ: 3 つのタスクを協調型で回す
;  各タスクは自分の「LED レジスタ」を進めて YIELD するだけ。
;  どのタスクがいつ走ったかは run.py のタイムラインで見える。
;
;  注意: これは picvm 用の「PIC 風」アセンブリで、本物の PIC18 に
;  そのままはかけられない (YIELD は本 VM 専用の自作命令。本物では
;  GOTO が 2 ワード命令なので DECFSZ で飛ばすと壊れる、等)。本物の
;  PIC18 機械語版は pic18/ にある。
; ====================================================================

; --- 共有ファイルレジスタの割り当て (タスクごとに別領域) ---
LED0   EQU 0x20        ; task0 用カウンタ
LED1   EQU 0x21        ; task1 用カウンタ
LED2   EQU 0x22        ; task2 用 "点滅" 出力
DLY2   EQU 0x30        ; task2 のディレイカウンタ

; --- task0: 毎回 +1 する一番せっかちなタスク ---
task0:
        INCF  LED0
        YIELD
        GOTO  task0

; --- task1: 毎回 +2 する ---
task1:
        MOVF  LED1
        ADDLW 2
        MOVWF LED1
        YIELD
        GOTO  task1

; --- task2: 3 回明け渡すごとに LED2 を 1 回 +1 する (遅い点滅相当) ---
task2:
        MOVLW 3
        MOVWF DLY2
t2loop:
        YIELD
        DECFSZ DLY2          ; DLY2-- して 0 になったら次の GOTO を飛ばす
        GOTO  t2loop
        INCF  LED2
        GOTO  task2

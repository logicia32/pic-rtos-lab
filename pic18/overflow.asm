; ====================================================================
;  落とし穴デモ: ハードウェアリターンスタックを溢れさせる
;
;  RTOS もどき(rtos18.asm)では、文脈切替のたびに走行中タスクの戻り番地を
;  TCB へ逃がしていた。だから 31 段のハードスタックは食い潰されなかった。
;
;  ここでは逆に「キリのいい所で yield せず、戻りもせず、ひたすら深く
;  rcall し続けるダメなタスク」を動かす。戻り番地がハードスタックに
;  積み上がり、PIC18 の上限 31 段にぶつかる。
;
;  見どころ:
;    depth   … コードが「これだけ潜った」と信じている呼び出し段数
;    STKPTR  … 実際に積めた段数 (bit0..4)。最初は depth+1 で一緒に増えるが
;              (start->rcall sink の 1 段ぶん)、31 で頭打ちし bit7=STKFUL が立つ。
;              以後は depth だけが増え続ける。
;  STKPTR が 31 で凍ってからの depth との差が、取りこぼした戻り番地の数
;  ＝もう正しく戻れない深さ。
;
;  CONFIG STVR = OFF にしてあるので、あふれてもリセットせず STKFUL を
;  観察できる。STVR = ON にすると同じバグが「即リセット」に化ける(README参照)。
;  (満杯後に STKPTR が 31 で飽和する/STKFUL が立つ等の細部は gpsim 上の
;   観測。実機での正確な満杯時動作は STVREN と各デバイスの datasheet を参照。)
; ====================================================================

        LIST    P=18F452
        #include <p18f452.inc>

        CONFIG  OSC  = HS
        CONFIG  WDT  = OFF
        CONFIG  LVP  = OFF
        CONFIG  STVR = OFF       ; あふれてもリセットしない (STKFUL を見たい)

        errorlevel -302

F       EQU 1

        CBLOCK 0x00
            depth                ; 到達したと“信じている”呼び出し段数
        ENDC

        org     0x0000
        goto    start
        org     0x0020
start:
        clrf    depth, A
        rcall   sink             ; yield しないダメなタスクへ
        bra     $                ; (実質ここへは戻ってこない)

; sink: 自分自身を rcall し続ける。return には決して到達しない。
;       1 回潜るごとに戻り番地が 1 段積まれていく。
sink:
        incf    depth, F, A      ; 「また 1 段潜った」と記録
        rcall   sink             ; さらに深く
        return                   ; 到達しない (=戻り番地が溢れる原因そのもの)

        END

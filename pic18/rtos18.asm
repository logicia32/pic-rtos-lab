; ====================================================================
;  RTOS もどき (本物の PIC18 版) — 協調型ラウンドロビン 2 タスク
;
;  これは「PIC風VM」ではなく、本物の PIC18 機械語。
;    gpasm でアセンブル → gpsim で実行できる。
;
;  記事の核心 (PIC ならではの一点):
;    戻り番地は「ハードウェアリターンスタック」に積まれる。深さに上限が
;    あり (PIC18 で 31 段)、CPU から直接は中身を“持ち運べない”。そこで
;    文脈切り替えのたびに、走行中タスクの戻り番地を TOS (TOSU:TOSH:TOSL)
;    からタスク制御ブロック(TCB)へ退避し、次タスクの戻り番地を積み直す。
;    STKPTR は 0〜1 を行き来するだけ — タスクの“続き”は各 TCB が持つ。
;    これが「普通の CPU との違い」で、os_yield がそれを実際にやっている。
;
;  協調型なので、各タスクは自分のキリのいい所で rcall os_yield して
;  CPU を明け渡す (yield のときスタックは最上位 1 段だけ = この単純さの肝)。
; ====================================================================

        LIST    P=18F452
        #include <p18f452.inc>

        CONFIG  OSC = HS         ; シミュレータ用。実機なら水晶に合わせる
        CONFIG  WDT = OFF        ; ウォッチドッグは切る (協調ループを邪魔させない)
        CONFIG  LVP = OFF

; --- オペランド記号。W/A/ACCESS は inc 定義済み。F だけ自前 ---
F       EQU 1                    ; 演算結果の格納先 = ファイルレジスタ

; access-high の SFR (FSR0L/PRODL/TOS など) を ,A で触ると出る
; advisory(302)。意図通りなので黙らせる。
        errorlevel -302

; --- TCB レイアウト (1 タスク 6 バイト) ---
TCB_SIZE  EQU 6
RET_L     EQU 0                  ; 戻り番地 下位
RET_H     EQU 1                  ; 戻り番地 中位
RET_U     EQU 2                  ; 戻り番地 上位 (PIC18 の PC は 21bit)
W_S       EQU 3                  ; W レジスタ退避
STAT_S    EQU 4                  ; STATUS 退避
NTASK     EQU 2                  ; タスク数

; --- アクセスRAM の変数 (0x00〜) ---
        CBLOCK 0x00
            cur                  ; 現在のタスク番号 (0..NTASK-1)
            COUNT0               ; task0 の出力カウンタ
            COUNT1               ; task1 の出力カウンタ
            tmpL                 ; 退避中の戻り番地 (作業用)
            tmpH
            tmpU
            tmpW
            tmpS
        ENDC

TCB0      EQU 0x10               ; TCB 配列の先頭
TCB1      EQU TCB0 + TCB_SIZE    ; = 0x16

; ====================================================================
;  ベクタ
; ====================================================================
        org     0x0000
        goto    start
        org     0x0008
        retfie                   ; 高優先度割り込み (未使用)
        org     0x0018
        retfie                   ; 低優先度割り込み (未使用)

; ====================================================================
;  初期化 → スケジューラ起動
; ====================================================================
        org     0x0020
start:
        ; TCB0 にタスク0の入口アドレスを仕込む
        movlw   low task0
        movwf   TCB0+RET_L, A
        movlw   high task0
        movwf   TCB0+RET_H, A
        movlw   upper task0
        movwf   TCB0+RET_U, A
        clrf    TCB0+W_S, A
        clrf    TCB0+STAT_S, A
        ; TCB1 にタスク1の入口アドレスを仕込む
        movlw   low task1
        movwf   TCB1+RET_L, A
        movlw   high task1
        movwf   TCB1+RET_H, A
        movlw   upper task1
        movwf   TCB1+RET_U, A
        clrf    TCB1+W_S, A
        clrf    TCB1+STAT_S, A
        ; 出力カウンタと現在タスクを初期化
        clrf    COUNT0, A
        clrf    COUNT1, A
        clrf    cur, A
        goto    os_start         ; task0 を起動 (ここへは戻らない)

; ====================================================================
;  FSR0 を「現在のタスクの TCB 先頭」に向ける
;    addr = TCB0 + cur * TCB_SIZE  (8x8 ハード乗算 MULLW を使う)
; ====================================================================
; 注意: このルーチンは FSR0 と PRODL/PRODH を破壊する。タスク側はこれらを
;       またいで使わない前提 (この最小デモの割り切り)。
point_fsr0:
        movf    cur, W, A
        mullw   TCB_SIZE         ; PRODL = cur * 6 (小さいので PRODH=0)
        movf    PRODL, W, A
        addlw   TCB0
        movwf   FSR0L, A
        clrf    FSR0H, A
        return

; ====================================================================
;  os_start: 最初のタスク(task0)へ制御を渡す“発射台”
; ====================================================================
os_start:
        clrf    cur, A
        rcall   point_fsr0
        movff   POSTINC0, tmpL
        movff   POSTINC0, tmpH
        movff   POSTINC0, tmpU
        movff   POSTINC0, tmpW
        movff   POSTINC0, tmpS
        push                     ; 戻り番地用に 1 段確保 (TOS は直後に上書き)
        movf    tmpU, W, A       ; TOS は MOVFF の書込み先にできないので movf/movwf
        movwf   TOSU, A
        movf    tmpH, W, A
        movwf   TOSH, A
        movf    tmpL, W, A
        movwf   TOSL, A
        movff   tmpS, STATUS     ; STATUS/W は最後に復元 (movf が汚した分を上書き)
        movff   tmpW, WREG
        return                   ; task0 の入口へ "戻る"

; ====================================================================
;  os_yield: 文脈切り替えの本体 (協調型)
;    タスクが rcall os_yield した時点で、TOS には「そのタスクへの戻り番地」
;    が載っている。それを TCB に退避し、次タスクの戻り番地を積み直して
;    return すれば、次タスクが“続きから”動き出す。
; ====================================================================
os_yield:
        ; --- 1. 走行中タスクの戻り番地をハードスタックから取り出す ---
        movff   TOSL, tmpL
        movff   TOSH, tmpH
        movff   TOSU, tmpU
        pop                      ; ハードスタックを 1 段降ろす (中身は退避済み)
        movwf   tmpW, A          ; W を退避
        movff   STATUS, tmpS     ; STATUS を退避

        ; --- 2. いまのタスクの TCB へ書き込む ---
        rcall   point_fsr0       ; ここでの rcall/return はスタック ±1 で相殺
        movff   tmpL, POSTINC0
        movff   tmpH, POSTINC0
        movff   tmpU, POSTINC0
        movff   tmpW, POSTINC0
        movff   tmpS, POSTINC0

        ; --- 3. 次のタスクへ (ラウンドロビン) ---
        incf    cur, F, A
        movlw   NTASK
        cpfslt  cur, A           ; cur < NTASK なら次の clrf を飛ばす
        clrf    cur, A           ; cur >= NTASK のとき 0 へ巻き戻し

        ; --- 4. 次タスクのコンテキストを TCB から読み出す ---
        rcall   point_fsr0
        movff   POSTINC0, tmpL
        movff   POSTINC0, tmpH
        movff   POSTINC0, tmpU
        movff   POSTINC0, tmpW
        movff   POSTINC0, tmpS

        ; --- 5. 戻り番地をハードスタックへ積み直す ---
        push                     ; 1 段確保
        movf    tmpU, W, A       ; TOS は MOVFF の書込み先にできない
        movwf   TOSU, A
        movf    tmpH, W, A
        movwf   TOSH, A
        movf    tmpL, W, A
        movwf   TOSL, A

        ; --- 6. STATUS / W を復元して次タスクへ戻る (movf が汚した分を上書き) ---
        movff   tmpS, STATUS
        movff   tmpW, WREG
        return                   ; 次タスクの“続き”へ

; ====================================================================
;  タスク本体 (どちらも無限ループ。自分のカウンタを進めて明け渡す)
; ====================================================================
task0:
        incf    COUNT0, F, A     ; COUNT0 += 1
        rcall   os_yield
        bra     task0

task1:
        movlw   2
        addwf   COUNT1, F, A     ; COUNT1 += 2
        rcall   os_yield
        bra     task1

        END

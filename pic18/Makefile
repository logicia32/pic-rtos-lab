# 本物の PIC18 版 RTOS もどき: アセンブル & gpsim 実行
#
#   make            … rtos18 と overflow を両方アセンブル
#   make run        … 正しい RTOS もどき (STKPTR が 0〜1 から増えない)
#   make run-overflow … 落とし穴デモ (yield せず潜ってハードスタックを溢れさせる)
#   make clean      … 生成物を消す
#
# 必要なツール (どちらも OSS):
#   Ubuntu/Debian:  sudo apt install gputils gpsim
#
# gputils のヘッダ場所は環境で違う。標準パスに無ければ INCDIR を上書き:
#   make INCDIR=/path/to/gputils/header

INCDIR   ?= $(HOME)/.local/share/gputils/header

# このマシンの local ビルドは libgpsim を ~/.local/lib に置いている。
# apt 版なら標準パスにあるので下行は無害 (存在しなければ無視される)。
GPSIM_ENV := LD_LIBRARY_PATH=$(HOME)/.local/lib:$$LD_LIBRARY_PATH

.PHONY: all run run-overflow clean
all: rtos18.hex overflow.hex

# %.asm -> %.hex (gpasm は同名の .cod/.lst も一緒に吐く)
%.hex: %.asm
	gpasm -I "$(INCDIR)" -o $@ $<

# 正しい RTOS もどき: 戻り番地は TCB に逃がすので STKPTR は 0〜1 のまま
run: rtos18.hex
	$(GPSIM_ENV) gpsim -i -c run.stc

# 落とし穴: yield せず rcall で潜り続け、31 段の壁にぶつかる
run-overflow: overflow.hex
	$(GPSIM_ENV) gpsim -i -c overflow.stc

clean:
	rm -f *.hex *.cod *.lst *.err

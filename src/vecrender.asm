; ===== vector picture renderer (original Tomato-hime format) =====
; buffer rows 0-127 at $8000-$cfff, rows 128-167 at $e000-$f8ff (RAM, $01=$35 while drawing)
v_ZX0    = $40
v_ZY0    = $41
v_ZX1    = $42
v_ZY1    = $43
v_COL    = $44
v_DX     = $45
v_DY     = $46
v_SX     = $47
v_SY     = $48
v_ERRL   = $49
v_ERRH   = $4a
v_CNT    = $4b
v_VP     = $4c      ; vector pointer (2)
v_CX     = $4e
v_CY     = $4f
v_BP     = $50      ; buffer pointer (2)
v_T0     = $52
v_T1     = $53
v_SEED   = $54
v_PA     = $55      ; pattern colour even
v_PB     = $56      ; pattern colour odd
v_XL     = $57
v_XR     = $58
v_SPL    = $59      ; v_fill stack pointer (2)
v_BX0    = $5b
v_BX1    = $5c
v_BY0    = $5d
v_BY1    = $5e
v_PICN   = $5f
v_BG     = $60
v_C1     = $61
v_C2     = $62
v_C3     = $63
v_OUTP   = $64      ; (2)
v_SCRP   = $66      ; (2)
v_CELLX  = $68
v_CELLY  = $69
v_RY     = $6a
v_T2     = $6b
v_T3     = $6c
v_FX     = $6d
v_FY     = $6e
v_OUTCOL = $6f      ; (2)
v_LCNT = $71
v_FB   = $72
v_FBI  = $73
v_FM   = $74
v_CA   = $75      ; (2)
v_CB   = $77      ; (2)
v_LMX  = $79
v_LMY  = $7a
v_RL   = $7b      ; (2)
v_T4   = $7d
v_T5   = $7e
v_T6   = $7f
v_T7   = $80
v_pres = $02      ; (8) colour presence flags
v_LSROW = $0a
v_LSC0 = $0b
v_LSC1 = $0c
v_LASTF = $81

VSTACK = $f900    ; v_fill stack $f900-$fff7
DIRTY  = $0748    ; dirty cell bitmask 21x5

; render: v_VP = vector data -> bitmap $6000, screen $4400, colour ram, PICBG
render: lda #0               ; background ($d021) is always black: no colour change at the text split
        sta v_BG
        sta PICBG
        lda #$18               ; picture area: multicolour bitmap $6000 / screen $4400
        sta M16
        sta M18
        sei
        lda #<irqram
        sta $fffe
        lda #>irqram
        sta $ffff
        lda #$35
        sta $01
        lda #1
        sta RAMMODE
        cli
        jsr v_initscr
        lda #$3b
        sta D011B
        jsr v_drawpic
        jsr v_flush
        sei
        lda #$36
        sta $01
        lda #0
        sta RAMMODE
        cli
        rts

; screen = all white canvas
v_initscr:
        lda #0
        sta v_T1               ; bitmap byte
        sta v_T2               ; screen byte
        lda v_BG
        cmp #7
        beq v_is1
        lda #$55
        sta v_T1
        lda #$10               ; white (1) in high nibble
        sta v_T2
v_is1:  lda #<$6000
        sta v_BP
        lda #>$6000
        sta v_BP+1
        ldx #26                ; 26 pages + 64 bytes = 6720
        ldy #0
        lda v_T1
v_is2:  sta (v_BP),y
        iny
        bne v_is2
        inc v_BP+1
        dex
        bne v_is2
        ldy #63
v_is2b: sta $7a00,y
        dey
        bpl v_is2b
        ldx #0                 ; bitmap below the picture ($7a40-$7f3f) must stay empty
        lda #0
v_is2c: sta $7a40,x
        sta $7b40,x
        sta $7c40,x
        sta $7d40,x
        sta $7e40,x
        inx
        bne v_is2c
        ldx #0
v_is3:  lda v_T2
        sta $4400,x
        sta $4500,x
        sta $4600,x
        lda #0
        sta $d800,x
        sta $d900,x
        sta $da00,x
        inx
        bne v_is3
        ldx #$47
v_is4:  lda v_T2
        sta $4700,x
        lda #0
        sta $db00,x
        dex
        bpl v_is4
        ldx #104
        lda #0
v_is5:  sta DIRTY,x
        dex
        bpl v_is5
        lda #0
        sta v_LCNT
        lda #$ff
        sta v_LMX
        sta v_LSROW
        rts

; mark cell of pixel X,Y dirty (preserves X,Y)
v_mark: stx v_T0
        sty v_T1
        tya
        lsr
        lsr
        lsr
        cmp v_LMY
        bne v_mk1
        txa
        lsr
        lsr
        cmp v_LMX
        bne v_mk0
        rts                    ; same cell as last time
v_mk0:  lda v_LMY
v_mk1:  sta v_LMY
        tay                    ; cell row
        txa
        lsr
        lsr
        sta v_LMX
        lda v_mul5,y
        sta v_T3
        txa
        lsr
        lsr                    ; cell x
        tax
        lsr
        lsr
        lsr
        clc
        adc v_T3
        tay
        txa
        and #7
        tax
        lda DIRTY,y
        ora v_bit,x
        sta DIRTY,y
        ldx v_T0
        ldy v_T1
        rts

; convert all dirty cells
v_flush:
        lda #$ff
        sta v_LMX
        sta v_LSROW
        lda #0
        sta v_LCNT
        sta v_CELLY
v_fy:   lda v_CELLY
        tay
        lda v_mul5,y
        sta v_FB
        lda #0
        sta v_FBI
v_fb:   lda v_FB
        clc
        adc v_FBI
        tay
        lda DIRTY,y
        beq v_fbn
        sta v_FM
        lda #0
        sta DIRTY,y
        lda v_FBI
        asl
        asl
        asl
        sta v_CELLX
v_fbit: lsr v_FM
        bcc v_fbn2
        lda v_CELLX
        cmp #40
        bcs v_fbn2
        jsr v_cell
v_fbn2: inc v_CELLX
        lda v_FM
        bne v_fbit
v_fbn:  inc v_FBI
        lda v_FBI
        cmp #5
        bne v_fb
        inc v_CELLY
        lda v_CELLY
        cmp #21
        bne v_fy
        rts

v_mul5: .byte 0,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80,85,90,95,100
v_bit:  .byte 1,2,4,8,16,32,64,128

; ------------------------------------------------ interpreter
v_drawpic:
        lda #$80
        ldx #80
        jsr v_clr
        lda #$e0
        ldx #25
        jsr v_clr
        lda #0
        sta v_CX
        sta v_CY
v_dp_l:   ldy #0
        lda (v_VP),y
        and #$c0
        bne v_dp_1
        rts
v_dp_1:   sta v_T2
        lda (v_VP),y
        lsr
        lsr
        lsr
        and #7
        sta v_COL
        lda (v_VP),y
        and #3
        lsr
        ror
        ror
        sta v_T0               ; (c&3)<<6
        iny
        lda (v_VP),y
        lsr
        lsr
        ora v_T0
        sta v_ZX1
        iny
        lda (v_VP),y
        sta v_ZY1
        lda v_T2
        cmp #$40
        beq v_dp_m
        cmp #$80
        beq v_dp_ln
        iny
        lda (v_VP),y
        sta v_T0
        lsr
        lsr
        lsr
        lsr
        and #7
        sta v_PA
        lda v_T0
        and #7
        sta v_PB
        lda #4
        jsr v_advvp
        jsr v_fill
        jsr v_tick
        jmp v_dp_l
v_dp_m:   lda #3
        jsr v_advvp
        lda v_ZX1
        sta v_CX
        lda v_ZY1
        sta v_CY
        jmp v_dp_l
v_dp_ln:  lda #3
        jsr v_advvp
        lda v_CX
        sta v_ZX0
        lda v_CY
        sta v_ZY0
        jsr v_line
        jsr v_tick
        lda v_ZX1
        sta v_CX
        lda v_ZY1
        sta v_CY
        jmp v_dp_l
v_advvp:  clc
        adc v_VP
        sta v_VP
        bcc v_av1
        inc v_VP+1
v_av1:    rts

; ------------------------------------------------ v_line (v_ZX0,v_ZY0)-(v_ZX1,v_ZY1) colour v_COL; X=x, Y=y during loop
v_plot:   cpx #160
        bcs v_pl_r
        cpy #168
        bcs v_pl_r
        sty v_T3
        lda vrowlo,y
        sta v_BP
        lda vrowhi,y
        sta v_BP+1
        txa
        tay
        lda v_COL
        sta (v_BP),y
        ldy v_T3
        jsr v_mark
v_pl_r:   rts

v_line:   lda #1
        sta v_SX
        sta v_SY
        sec
        lda v_ZX1
        sbc v_ZX0
        bcs v_ln1
        eor #$ff
        adc #1
        ldx #$ff
        stx v_SX
v_ln1:    sta v_DX
        sec
        lda v_ZY1
        sbc v_ZY0
        bcs v_ln2
        eor #$ff
        adc #1
        ldx #$ff
        stx v_SY
v_ln2:    sta v_DY
        ldx v_ZX0
        ldy v_ZY0
        lda v_DX
        cmp v_DY
        bcc v_ln_y
        lda v_DX
        sta v_CNT
        lsr
        sta v_ERRL
        lda #0
        sta v_ERRH
v_lx_l:   jsr v_plot
        lda v_CNT
        beq v_ln_r
        dec v_CNT
        txa
        clc
        adc v_SX
        tax
        sec
        lda v_ERRL
        sbc v_DY
        sta v_ERRL
        lda v_ERRH
        sbc #0
        sta v_ERRH
        bpl v_lx_l
        clc
        lda v_ERRL
        adc v_DX
        sta v_ERRL
        lda v_ERRH
        adc #0
        sta v_ERRH
        tya
        clc
        adc v_SY
        tay
        jmp v_lx_l
v_ln_y:   lda v_DY
        sta v_CNT
        lsr
        sta v_ERRL
        lda #0
        sta v_ERRH
v_ly_l:   jsr v_plot
        lda v_CNT
        beq v_ln_r
        dec v_CNT
        tya
        clc
        adc v_SY
        tay
        sec
        lda v_ERRL
        sbc v_DX
        sta v_ERRL
        lda v_ERRH
        sbc #0
        sta v_ERRH
        bpl v_ly_l
        clc
        lda v_ERRL
        adc v_DY
        sta v_ERRL
        lda v_ERRH
        adc #0
        sta v_ERRH
        txa
        clc
        adc v_SX
        tax
        jmp v_ly_l
v_ln_r:   rts

; ------------------------------------------------ scanline flood v_fill at (v_ZX1,v_ZY1), pattern v_PA/v_PB
; pixels written get bit7 = inverse of the seed's bit7, so they never match the seed again
v_fill:   ldx v_ZX1
        ldy v_ZY1
        cpx #160
        bcs v_fl_rr
        cpy #168
        bcc v_fl_go
v_fl_rr:  rts
v_fl_go:  lda vrowlo,y
        sta v_BP
        lda vrowhi,y
        sta v_BP+1
        txa
        tay
        lda (v_BP),y
        sta v_SEED
        and #$80
        eor #$80
        sta v_T1               ; mark bit
        ora v_PA
        sta v_PA
        lda v_PB
        ora v_T1
        sta v_PB
        lda #<VSTACK
        sta v_SPL
        lda #>VSTACK
        sta v_SPL+1
        ldy v_ZY1
        jsr v_push
v_fl_pop: lda v_SPL
        cmp #<VSTACK
        bne v_fl_p1
        lda v_SPL+1
        cmp #>VSTACK
        bne v_fl_p1
        rts
v_fl_p1:  sec
        lda v_SPL
        sbc #2
        sta v_SPL
        bcs v_fl_p2
        dec v_SPL+1
v_fl_p2:  ldy #0
        lda (v_SPL),y
        sta v_FX
        iny
        lda (v_SPL),y
        sta v_FY
        tax
        lda vrowlo,x
        sta v_BP
        lda vrowhi,x
        sta v_BP+1
        ldy v_FX
        lda (v_BP),y
        cmp v_SEED
        bne v_fl_pop
v_fl_sl:  dey                  ; scan left (Y = x)
        cpy #$ff
        beq v_fl_sl2
        lda (v_BP),y
        cmp v_SEED
        beq v_fl_sl
v_fl_sl2: iny
        sty v_XL
        ; pattern phase: colour = v_PA if (x+y) even else v_PB
        tya
        clc
        adc v_FY
        and #1
        tax                  ; X = phase
        bne v_fl_odd
v_fl_sr:  lda v_PA
        sta (v_BP),y
        iny
        cpy #160
        bcs v_fl_sr2
        lda (v_BP),y
        cmp v_SEED
        bne v_fl_sr2
v_fl_odd: lda v_PB
        sta (v_BP),y
        iny
        cpy #160
        bcs v_fl_sr2
        lda (v_BP),y
        cmp v_SEED
        beq v_fl_sr
v_fl_sr2: dey
        sty v_XR
        jsr v_markspan
        ldx v_FY
        dex
        cpx #$ff
        beq v_fl_nb2
        jsr v_scanrow
v_fl_nb2: ldx v_FY
        inx
        cpx #168
        bcs v_fl_nb3
        jsr v_scanrow
v_fl_nb3: jmp v_fl_pop

; scan row X between v_XL..v_XR, v_push the first pixel of each seed run
v_scanrow:                       ; row X, columns XL..XR: push the first pixel of each seed run
        stx v_T2
        lda vrowlo,x
        sta v_BP
        lda vrowhi,x
        sta v_BP+1
        ldx v_XR
        inx
        stx v_T3               ; XR+1
        ldy v_XL
        lda v_SEED
v_sr_out: cmp (v_BP),y
        beq v_sr_fnd
        iny
        cpy v_T3
        bne v_sr_out
        rts
v_sr_fnd: sty v_T0             ; push (x=Y, y=T2)
        tya
        ldy #0
        sta (v_SPL),y
        iny
        lda v_T2
        sta (v_SPL),y
        lda v_SPL
        clc
        adc #2
        sta v_SPL
        bcc v_sr_p1
        inc v_SPL+1
        lda v_SPL+1
        cmp #$ff
        bcc v_sr_p1
        dec v_SPL+1            ; overflow: drop
v_sr_p1:  ldy v_T0
        lda v_SEED
v_sr_in:  iny
        cpy v_T3
        beq v_sr_r
        cmp (v_BP),y
        beq v_sr_in
        iny
        cpy v_T3
        bne v_sr_out
v_sr_r:   rts

v_push:   ; X = x, Y = y  (clobbers A)
        sty v_T1
        ldy #0
        txa
        sta (v_SPL),y
        iny
        lda v_T1
        sta (v_SPL),y
        ldy v_T1
        clc
        lda v_SPL
        adc #2
        sta v_SPL
        bcc v_ps1
        inc v_SPL+1
v_ps1:    lda v_SPL+1
        cmp #$ff
        bcc v_ps2
        dec v_SPL+1            ; overflow: drop
v_ps2:    rts

; ------------------------------------------------ convert buffer -> multicolour bitmap
v_cell:   ldy v_CELLY
        lda v_m40lo,y
        clc
        adc v_CELLX
        sta v_SCRP
        sta v_OUTCOL
        lda v_m40hi,y
        adc #0
        sta v_T3
        clc
        adc #$44
        sta v_SCRP+1
        lda v_T3
        clc
        adc #$d8
        sta v_OUTCOL+1
        lda v_SCRP              ; OUTP = $6000 + idx*8
        sta v_OUTP
        lda v_T3
        asl v_OUTP
        rol
        asl v_OUTP
        rol
        asl v_OUTP
        rol
        clc
        adc #$60
        sta v_OUTP+1
        lda #0                 ; clear colour presence flags (1-7; 0 = background)
        sta v_pres+1
        sta v_pres+2
        sta v_pres+3
        sta v_pres+4
        sta v_pres+5
        sta v_pres+6
        sta v_pres+7
        lda v_CELLY
        asl
        asl
        asl
        tax
        lda vrowlo,x
        sta v_BP
        lda vrowhi,x
        sta v_BP+1
        lda v_CELLX
        asl
        asl
        sta v_FX               ; x offset of cell
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+0
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+1
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+2
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+3
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr0
        inc v_BP+1
v_cr0:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+4
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+5
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+6
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+7
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr1
        inc v_BP+1
v_cr1:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+8
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+9
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+10
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+11
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr2
        inc v_BP+1
v_cr2:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+12
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+13
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+14
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+15
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr3
        inc v_BP+1
v_cr3:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+16
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+17
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+18
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+19
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr4
        inc v_BP+1
v_cr4:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+20
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+21
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+22
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+23
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr5
        inc v_BP+1
v_cr5:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+24
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+25
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+26
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+27
        tax
        sta v_pres,x
        clc
        lda v_BP
        adc #160
        sta v_BP
        bcc v_cr6
        inc v_BP+1
v_cr6:
        ldy v_FX
        lda (v_BP),y
        and #7
        sta v_pixb+28
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+29
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+30
        tax
        sta v_pres,x
        iny
        lda (v_BP),y
        and #7
        sta v_pixb+31
        tax
        sta v_pres,x
        ldy #0                 ; list the colours present
        lda v_pres+1
        beq v_cl1
        sta v_lst,y
        iny
v_cl1:
        lda v_pres+2
        beq v_cl2
        sta v_lst,y
        iny
v_cl2:
        lda v_pres+3
        beq v_cl3
        sta v_lst,y
        iny
v_cl3:
        lda v_pres+4
        beq v_cl4
        sta v_lst,y
        iny
v_cl4:
        lda v_pres+5
        beq v_cl5
        sta v_lst,y
        iny
v_cl5:
        lda v_pres+6
        beq v_cl6
        sta v_lst,y
        iny
v_cl6:
        lda v_pres+7
        beq v_cl7
        sta v_lst,y
        iny
v_cl7:
        cpy #0
        bne v_c_some
        tya                    ; all background: empty cell
        sta (v_SCRP),y
        sta (v_OUTCOL),y
        ldy #7
v_c_z:  sta (v_OUTP),y
        dey
        bpl v_c_z
        rts
v_c_some:
        cpy #4
        bcc v_c_few
        jmp v_c_many
v_c_few:
        lda #0                 ; 1-3 colours: use them as they are
        sta v_C2
        sta v_C3
        ldx v_lst
        stx v_C1
        lda #$40
        sta v_cm6,x
        lda #$10
        sta v_cm4,x
        lda #$04
        sta v_cm2,x
        lda #$01
        sta v_cm0,x
        cpy #2
        bcc v_c_set
        ldx v_lst+1
        stx v_C2
        lda #$80
        sta v_cm6,x
        lda #$20
        sta v_cm4,x
        lda #$08
        sta v_cm2,x
        lda #$02
        sta v_cm0,x
        cpy #3
        bcc v_c_set
        ldx v_lst+2
        stx v_C3
        lda #$c0
        sta v_cm6,x
        lda #$30
        sta v_cm4,x
        lda #$0c
        sta v_cm2,x
        lda #$03
        sta v_cm0,x
v_c_set:
        ldx v_C1
        lda v_pc2c64,x
        asl
        asl
        asl
        asl
        ldx v_C2
        ora v_pc2c64,x
        ldy #0
        sta (v_SCRP),y
        ldx v_C3
        lda v_pc2c64,x
        sta (v_OUTCOL),y
        ldx v_pixb+0
        lda v_cm6,x
        ldx v_pixb+1
        ora v_cm4,x
        ldx v_pixb+2
        ora v_cm2,x
        ldx v_pixb+3
        ora v_cm0,x
        ldy #0
        sta (v_OUTP),y
        ldx v_pixb+4
        lda v_cm6,x
        ldx v_pixb+5
        ora v_cm4,x
        ldx v_pixb+6
        ora v_cm2,x
        ldx v_pixb+7
        ora v_cm0,x
        ldy #1
        sta (v_OUTP),y
        ldx v_pixb+8
        lda v_cm6,x
        ldx v_pixb+9
        ora v_cm4,x
        ldx v_pixb+10
        ora v_cm2,x
        ldx v_pixb+11
        ora v_cm0,x
        ldy #2
        sta (v_OUTP),y
        ldx v_pixb+12
        lda v_cm6,x
        ldx v_pixb+13
        ora v_cm4,x
        ldx v_pixb+14
        ora v_cm2,x
        ldx v_pixb+15
        ora v_cm0,x
        ldy #3
        sta (v_OUTP),y
        ldx v_pixb+16
        lda v_cm6,x
        ldx v_pixb+17
        ora v_cm4,x
        ldx v_pixb+18
        ora v_cm2,x
        ldx v_pixb+19
        ora v_cm0,x
        ldy #4
        sta (v_OUTP),y
        ldx v_pixb+20
        lda v_cm6,x
        ldx v_pixb+21
        ora v_cm4,x
        ldx v_pixb+22
        ora v_cm2,x
        ldx v_pixb+23
        ora v_cm0,x
        ldy #5
        sta (v_OUTP),y
        ldx v_pixb+24
        lda v_cm6,x
        ldx v_pixb+25
        ora v_cm4,x
        ldx v_pixb+26
        ora v_cm2,x
        ldx v_pixb+27
        ora v_cm0,x
        ldy #6
        sta (v_OUTP),y
        ldx v_pixb+28
        lda v_cm6,x
        ldx v_pixb+29
        ora v_cm4,x
        ldx v_pixb+30
        ora v_cm2,x
        ldx v_pixb+31
        ora v_cm0,x
        ldy #7
        sta (v_OUTP),y
        rts

v_c_many:                      ; more than 3 colours: keep the 3 most frequent, map the others to the nearest
        lda #0
        ldx #7
v_cy0:  sta v_cnt8,x
        dex
        bpl v_cy0
        ldy #31
v_cy1:  ldx v_pixb,y
        inc v_cnt8,x
        dey
        bpl v_cy1
        lda #0
        sta v_cnt8             ; background is not a candidate
        jsr v_pickmax
        sta v_C1
        jsr v_pickmax
        sta v_C2
        jsr v_pickmax
        sta v_C3
        ldx #7
v_cy2:  txa
        jsr v_nearest          ; code 0-3 (preserves X)
        tay
        lda v_k6,y
        sta v_cm6,x
        lda v_k4,y
        sta v_cm4,x
        lda v_k2,y
        sta v_cm2,x
        tya
        sta v_cm0,x
        dex
        bne v_cy2
        jmp v_c_set

v_k6:   .byte $00,$40,$80,$c0
v_k4:   .byte $00,$10,$20,$30
v_k2:   .byte $00,$04,$08,$0c
v_cm6:  .fill 8
v_cm4:  .fill 8
v_cm2:  .fill 8
v_cm0:  .fill 8


v_pickmax:                       ; colour index with the largest count (>0), cleared; else BG
        ldx #0
        ldy #$ff
        lda #0
        sta v_T3
v_pm_l: lda v_cnt8,x
        beq v_pm_n
        cmp v_T3
        bcc v_pm_n
        beq v_pm_n
        sta v_T3
        txa
        tay
v_pm_n: inx
        cpx #8
        bne v_pm_l
        cpy #$ff
        beq v_pm_bg
        lda #0
        sta v_cnt8,y
        tya
        rts
v_pm_bg:
        lda v_BG
        rts

v_nearest:                      ; A = pc colour -> code (0=v_BG,1=v_C1,2=v_C2,3=v_C3) of v_nearest available
        sta v_T6
        asl
        asl
        asl                  ; *8 : row in preference table
        sta v_T7
        ldy #0
v_nr_l:   tya
        clc
        adc v_T7
        stx v_T5
        tax
        lda vpref,x
        ldx v_T5
        cmp v_BG
        beq v_nr_0
        cmp v_C1
        beq v_nr_1
        cmp v_C2
        beq v_nr_2
        cmp v_C3
        beq v_nr_3
        iny
        cpy #8
        bne v_nr_l
v_nr_0:   lda #0
        rts
v_nr_1:   lda #1
        rts
v_nr_2:   lda #2
        rts
v_nr_3:   lda #3
        rts

v_pc2c64: .byte 0,6,2,4,5,3,7,1
v_histl:  .fill 8
v_histh:  .fill 8
v_cnt8:   .fill 8
v_pixb:   .fill 32
v_lst:    .fill 8


v_clr:  sta v_BP+1
        lda #0
        sta v_BP
        ldy #0
        lda #7
v_clr1: sta (v_BP),y
        iny
        bne v_clr1
        inc v_BP+1
        dex
        bne v_clr1
        rts

; mark cells XL..XR on row FY
v_markspan:                      ; mark cells XL..XR of pixel row FY dirty
        lda v_FY
        lsr
        lsr
        lsr
        tay
        lda v_XL
        lsr
        lsr
        sta v_T0               ; first cell
        lda v_XR
        lsr
        lsr
        sta v_T1               ; last cell
        cpy v_LSROW            ; already covered by the previous span of this cell row?
        bne v_ms_do
        lda v_T0
        cmp v_LSC0
        bcc v_ms_do
        lda v_LSC1
        cmp v_T1
        bcc v_ms_do
        rts
v_ms_do:
        sty v_LSROW
        lda v_T0
        sta v_LSC0
        lda v_T1
        sta v_LSC1
        lda v_mul5,y
        sta v_T3
        lda v_T1
        lsr
        lsr
        lsr
        clc
        adc v_T3
        sta v_T2               ; index of last byte
        lda v_T0
        lsr
        lsr
        lsr
        clc
        adc v_T3
        tax                    ; index of first byte
        lda v_T0
        and #7
        tay
        lda v_lmask,y
        cpx v_T2
        bne v_ms_multi
        sta v_T3
        lda v_T1
        and #7
        tay
        lda v_rmask,y
        and v_T3
        ora DIRTY,x
        sta DIRTY,x
        jmp v_ms_done
v_ms_multi:
        ora DIRTY,x
        sta DIRTY,x
        inx
v_ms_mid:
        cpx v_T2
        beq v_ms_last
        lda #$ff
        sta DIRTY,x
        inx
        jmp v_ms_mid
v_ms_last:
        lda v_T1
        and #7
        tay
        lda v_rmask,y
        ora DIRTY,x
        sta DIRTY,x
v_ms_done:
        lda #$ff
        sta v_LMX
        rts
v_lmask: .byte $ff,$fe,$fc,$f8,$f0,$e0,$c0,$80
v_rmask: .byte $01,$03,$07,$0f,$1f,$3f,$7f,$ff
v_m40lo: .byte <0,<40,<80,<120,<160,<200,<240,<280,<320,<360,<400,<440,<480,<520,<560,<600,<640,<680,<720,<760,<800
v_m40hi: .byte >0,>40,>80,>120,>160,>200,>240,>280,>320,>360,>400,>440,>480,>520,>560,>600,>640,>680,>720,>760,>800

; RLE: n<$80 -> n+1 literals, n>=$80 -> next byte repeated n-$7e times; 1680 bytes total
v_cellrle:
        lda #<$4000
        sta v_CA
        lda #>$4000
        sta v_CA+1
        lda #<1680
        sta v_RL
        lda #>1680
        sta v_RL+1
v_rl_l: ldy #0
        lda (v_VP),y
        jsr v_vpinc
        cmp #$80
        bcs v_rl_run
        tax
        inx
v_rl_lit:
        lda (v_VP),y
        jsr v_vpinc
        jsr v_rlput
        dex
        bne v_rl_lit
        jmp v_rl_chk
v_rl_run:
        sec
        sbc #$7e
        tax
        lda (v_VP),y
        jsr v_vpinc
v_rl_r2:
        jsr v_rlput
        dex
        bne v_rl_r2
v_rl_chk:
        lda v_RL
        ora v_RL+1
        bne v_rl_l
        rts
v_vpinc:
        inc v_VP
        bne v_vi1
        inc v_VP+1
v_vi1:  rts
v_rlput:                         ; store A at CA, advance (skip from $4348 to $0400), count down
        sta (v_CA),y
        inc v_CA
        bne v_rp1
        inc v_CA+1
v_rp1:  pha
        lda v_CA
        cmp #<$4348
        bne v_rp2
        lda v_CA+1
        cmp #>$4348
        bne v_rp2
        lda #<$0400
        sta v_CA
        lda #>$0400
        sta v_CA+1
v_rp2:  lda v_RL
        bne v_rp3
        dec v_RL+1
v_rp3:  dec v_RL
        pla
        rts


v_tick:                          ; flush dirty cells about 5 times a second (frame counter from the raster IRQ)
        lda FRAMES
        sec
        sbc v_LASTF
        cmp #10
        bcc v_tk1
        lda FRAMES
        sta v_LASTF
        jmp v_flush
v_tk1:  rts

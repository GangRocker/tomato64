WRAPON = 0
; ===== Tomato Hime C64 adventure engine (menu driven, half-width kana text) =====
; zero page
PTR    = $fb
PTR2   = $fd
CURX   = $10
CURY   = $11
T1     = $12
T2     = $13
SEL    = $14
CNT    = $15
VERB   = $16
NOUN   = $17
ROOM   = $18
NENT   = $1a
SCRP   = $1b
RP     = $1f
SP_    = $21
GOFLAG = $23
GT     = $24
T3     = $2f
LISTP  = $3c

FIRST  = $25
LAST   = $26
IRQPH  = $27
D011B  = $28
PICBG  = $29
LEN    = $2a
PTR3   = $2c
SCR    = $4400               ; VIC bank 1: screen/colour info at $4400
BITMAP = $6000
MENUID = $0340
MENULO = $0360
MENUHI = $0380
FLAGS  = $5f00
UNBUF  = $8000
M16    = $3a
M18    = $3b
CBUF   = $3400
PBUF   = $5000
RAMMODE = $3e
LASTV  = $3f
FRAMES = $82
MUSP   = $83               ; music: stream pointer (2)
MUSN   = $85               ; music: voices running (IRQ only)
MUSO   = $86               ; music: octave (IRQ only)
NAMEBUF = $0334
PICX   = $38
WANT   = $39
CURDISK = $37
MP     = $30
OFF    = $32
ML     = $34
TOK    = $36

V_GO    = $f0
V_ITEMS = 19
V_SYS   = $f3
ROOMB   = $3402
MODE    = $2e
NOUN2I  = $f0
CHOICEI = $f2

*=$0801
        .byte $0b,$08,$0a,$00,$9e,$32,$30,$36,$34,$00,$00,$00
*=$0810
start:
        lda #$36
        sta $01              ; BASIC ROM off (RAM visible at $A000-$BFFF), KERNAL+I/O on
        ldx #0               ; copy font to $4800 (2 KB)
fc1:    lda fontdata,x
        sta $4800,x
        lda fontdata+$100,x
        sta $4900,x
        lda fontdata+$200,x
        sta $4a00,x
        lda fontdata+$300,x
        sta $4b00,x
        lda fontdata+$400,x
        sta $4c00,x
        lda fontdata+$500,x
        sta $4d00,x
        lda fontdata+$600,x
        sta $4e00,x
        lda fontdata+$700,x
        sta $4f00,x
        inx
        bne fc1
        lda #WRAPON          ; English build: Latin letters from the C64 character ROM
        beq fc_nr
        jsr romfont
fc_nr:  lda #0
        sta $d020
        sta $d021
        sta IRQPH
        sta PICBG
        sta RAMMODE
        lda #1
        sta CURDISK
        lda #$18
        sta M16
        sta M18
        lda #0
        lda #$3b
        sta D011B
        lda #1
        sta $cc
        lda $dd00            ; VIC bank 1 ($4000-$7fff)
        and #$fc
        ora #$02
        sta $dd00
        ; clear bitmap $6000-$7fff
        lda #<BITMAP
        sta PTR
        lda #>BITMAP
        sta PTR+1
        ldx #32
        ldy #0
cb:     lda #0
        sta (PTR),y
        iny
        bne cb
        inc PTR+1
        dex
        bne cb
        ; screen RAM = spaces, colour RAM = white
        lda #$20
        ldx #0
cl1:    sta SCR,x
        sta SCR+$100,x
        sta SCR+$200,x
        sta SCR+$300,x
        inx
        bne cl1
        lda #1
        ldx #0
cl2:    sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $db00,x
        inx
        bne cl2
        jsr menucol
        ldx #0
fi:     lda flaginit,x
        sta FLAGS,x
        inx
        bne fi
        lda #$3b             ; start in bitmap mode, multicolour
        sta $d011
        lda #$18
        sta $d016
        lda #$18
        sta $d018
        jsr mus_init
        ; raster interrupts: line 217 -> text mode, line 251 -> bitmap mode
        sei
        lda #<irq
        sta $0314
        lda #>irq
        sta $0315
        lda #$ff
        sta $d019
        lda #$01
        sta $d01a
        lda #217
        sta $d012
        lda $d011
        and #$7f
        sta $d011
        cli
        jsr title
        lda #0
        sta ROOM
        jsr enterroom
cmdloop:
        jsr buildverbs
        jsr domenuv
        bcs cmdloop
        sta VERB
        lda SEL
        sta LASTV
        lda VERB
        cmp #V_ITEMS
        bne notinv
        jsr showinv
        jmp cmdloop
notinv: cmp #V_SYS
        bne notsys
        jsr sysmenu
        jmp cmdloop
notsys: jsr findverb
        lda MODE
        bne hasnoun
        lda #$ff
        sta NOUN
        jmp go_rule
hasnoun:
        jsr buildnouns
        jsr domenu
        bcs cmdloop
        cmp #$fe
        beq cmdloop
        ldx MODE
        cpx #3
        bne nrm_n
        sta VERB
        lda #$ff
nrm_n:  sta NOUN
go_rule:
        jsr clearmsg
        jsr dorule
        lda GOFLAG
        beq cmdloop
        jsr enterroom
        jmp cmdloop

; ---------------------------------------------------------------- rooms
loadroom:
        lda #<ROOMB
        sta RP
        lda #>ROOMB
        sta RP+1
        rts

enterroom:
        lda #0
        sta GOFLAG
        sta LASTV
        jsr clearmsg
        lda #$20
        ldx #39
er_cl:  sta SCR+960,x
        dex
        bpl er_cl
        jsr clrmenu
        ldx ROOM
        lda roommus,x
        jsr mus_room
        ldx ROOM
        jsr showpic
        jsr loadroom
        ldy #4
        lda (RP),y
        sta SP_
        iny
        lda (RP),y
        sta SP_+1
        ora SP_
        beq er_ret
        jsr runscript
        lda GOFLAG
        bne enterroom
er_ret: rts

dorule:
        jsr loadroom
        ldy #2
        lda (RP),y
        sta PTR
        iny
        lda (RP),y
        sta PTR+1
dr_l:   ldy #0
        lda (PTR),y
        cmp #$ff
        beq dr_none
        cmp VERB
        bne dr_next
        iny
        lda (PTR),y
        cmp NOUN
        beq dr_hit
        cmp #$ff
        beq dr_hit
        cmp #$fd
        beq dr_hit
dr_next:
        clc
        lda PTR
        adc #5
        sta PTR
        bcc dr_l
        inc PTR+1
        jmp dr_l
dr_hit: ldy #3
        lda (PTR),y
        sta SP_
        iny
        lda (PTR),y
        sta SP_+1
        jsr clrmenu          ; the chosen command is running: old choices disappear
        jmp runscript
dr_none:
        lda #<msg_nothing
        sta PTR
        lda #>msg_nothing
        sta PTR+1
        jsr printstr
        rts

; ---------------------------------------------------------------- script VM
fetch:  ldy #0
        lda (SP_),y
        inc SP_
        bne f_r
        inc SP_+1
f_r:    rts

runscript:
rs_l:   jsr fetch
        cmp #0
        bne dsp0
        jmp rs_end
dsp0:
        cmp #1
        bne dsp1
        jmp rs_text
dsp1:
        cmp #2
        bne dsp2
        jmp rs_set
dsp2:
        cmp #3
        bne dsp3
        jmp rs_ifne
dsp3:
        cmp #4
        bne dsp3b
        jmp rs_goto
dsp3b:
        cmp #6
        bne dsp3c
        jmp rs_iflt
dsp3c:
        cmp #7
        bne dsp4
        jmp rs_tref
dsp4:
        cmp #9
        bne dsp5
        jmp rs_jmp
dsp5:
        cmp #10
        bne dsp6
        jmp rs_add
dsp6:
        cmp #11
        bne dsp7
        jmp rs_tog
dsp7:
        cmp #12
        bne dsp8
        jmp rs_choose
dsp8:
        cmp #13
        bne dsp9
        jmp rs_fail
dsp9:
        cmp #5
        bne dsp10
        jmp rs_wait
dsp10:
        cmp #14
        bne dsp11
        jmp rs_pic
dsp11:
rs_end: rts
rs_text:
        lda SP_
        sta PTR
        lda SP_+1
        sta PTR+1
        jsr printstr
        inc PTR
        bne rs_t1
        inc PTR+1
rs_t1:  lda PTR
        sta SP_
        lda PTR+1
        sta SP_+1
        jmp rs_l
rs_tref:                     ; 7 lo,hi: print a pooled string
        jsr fetch
        sta PTR
        jsr fetch
        sta PTR+1
        jsr printstr
        jmp rs_l
rs_set: jsr fetch
        tax
        jsr fetch
        sta FLAGS,x
        jmp rs_l
rs_add: jsr fetch
        tax
        jsr fetch
        clc
        adc FLAGS,x
        sta FLAGS,x
        jmp rs_l
rs_tog: jsr fetch
        tax
        lda FLAGS,x
        eor #1
        sta FLAGS,x
        jmp rs_l
rs_ifne:
        jsr fetch
        tax
        jsr fetch
        sta T1
        jsr fetch
        sta T2
        jsr fetch
        sta T3
        lda FLAGS,x
        cmp T1
        bne rs_skip
        jmp rs_l
rs_iflt:                     ; 6 flag,k,len16: run the block only when FLAGS[flag] < k (unsigned)
        jsr fetch
        tax
        jsr fetch
        sta T1
        jsr fetch
        sta T2
        jsr fetch
        sta T3
        lda FLAGS,x
        cmp T1
        bcs rs_skip
        jmp rs_l
rs_jmp: jsr fetch
        sta T2
        jsr fetch
        sta T3
rs_skip:
        clc
        lda SP_
        adc T2
        sta SP_
        lda SP_+1
        adc T3
        sta SP_+1
        jmp rs_l
rs_goto:
        jsr fetch
        sta ROOM
        lda #1
        sta GOFLAG
        rts
rs_wait:
        jsr getact
        jmp rs_l
rs_fail:
        lda #<msg_fail
        sta PTR
        lda #>msg_fail
        sta PTR+1
        jsr printstr
        rts
rs_choose:
        jsr fetch            ; flag index, then inline (noun,$ff)... $ff candidate list
        pha
        ldx #0
        lda SP_
        sta PTR
        lda SP_+1
        sta PTR+1
        jsr addnouns         ; PTR ends at the $ff terminator
        inc PTR
        bne rc_a
        inc PTR+1
rc_a:   lda PTR
        pha
        lda PTR+1
        pha
        jsr addinv
        jsr backent
        jsr domenu
        bcs rc_none
        cmp #$fe
        bne rc_set
rc_none:
        lda #0
rc_set: sta T1
        jsr clrmenu
        jsr clearmsg         ; the question disappears once answered (like the original input line)
        pla
        sta SP_+1
        pla
        sta SP_
        pla
        tax
        lda T1
        sta FLAGS,x
        jmp rs_l

rs_pic: jsr fetch             ; event picture: load "Pnnn" (n = scene) from the current disk
        sta PICX
        jsr blanktop
        lda SP_
        pha
        lda SP_+1
        pha
        lda #$2b
        sta D011B
        lda #$50
        sta NAMEBUF
        lda PICX
        jsr num3
        lda #4
        ldx #<NAMEBUF
        ldy #>NAMEBUF
        jsr $ffbd
        lda #1
        ldx #8
        ldy #0
        jsr $ffba
        lda #0
        ldx #<PBUF
        ldy #>PBUF
        jsr kload
        bcs rp_err
        lda #<PBUF
        sta v_VP
        lda #>PBUF
        sta v_VP+1
        jsr render
        lda #$3b
        sta D011B
        jmp rp_done
rp_err: jsr $ffe7
        lda #$3b
        sta D011B
rp_done:
        pla
        sta SP_+1
        pla
        sta SP_
        jmp rs_l

; A = number 0..199 -> NAMEBUF+1..3 ascii
num3:   ldx #0
n3_h:   cmp #100
        bcc n3_h2
        sbc #100
        inx
        bne n3_h
n3_h2:  pha
        txa
        ora #$30
        sta NAMEBUF+1
        pla
        ldx #0
n3_t:   cmp #10
        bcc n3_t2
        sbc #10
        inx
        bne n3_t
n3_t2:  ora #$30
        sta NAMEBUF+3
        txa
        ora #$30
        sta NAMEBUF+2
        rts

; clear the screen matrix of the picture area (rows 0-20) before disk access:
; KERNAL serial I/O can hold off the raster IRQ for a whole frame, and the picture's
; colour bytes would then be displayed as characters in text mode
blanktop:
        lda #$2b
        sta D011B
        ldx #0
        txa
bt1:    sta SCR,x
        sta SCR+$100,x
        sta SCR+$200,x
        inx
        bne bt1
        ldx #$47
bt2:    sta SCR+$300,x
        dex
        bpl bt2
        rts

; ---------------------------------------------------------------- save / load
; save file "TOMATOSAV": FLAGS $c000-$c0ff ($c0ff = room)
sysmenu:
        ldx #0
        lda #1
        sta MENUID,x
        lda #<vname_save
        sta MENULO,x
        lda #>vname_save
        sta MENUHI,x
        inx
        lda #2
        sta MENUID,x
        lda #<vname_load
        sta MENULO,x
        lda #>vname_load
        sta MENUHI,x
        inx
        lda #3
        sta MENUID,x
        lda #<vname_restart
        sta MENULO,x
        lda #>vname_restart
        sta MENUHI,x
        inx
        lda #4
        sta MENUID,x
        lda #<vname_vol
        sta MENULO,x
        lda #>vname_vol
        sta MENUHI,x
        inx
        jsr backent
        jsr domenu
        bcs sy_r
        cmp #1
        beq dosave
        cmp #2
        bne sy_3
        jmp doload
sy_3:   cmp #4
        bne sy_3b
        jmp mus_volmenu
sy_3b:  cmp #3
        bne sy_r
        ldx #0
sy_fi:  lda flaginit,x
        sta FLAGS,x
        inx
        bne sy_fi
        lda #0
        sta ROOM
        jmp enterroom
sy_r:   rts

savprompt:                   ; ask for the save disk (any disk)
        lda #0
        sta WANT
        jsr textonly
        jsr clearmsg
        lda #<msg_savdisk
        sta PTR
        lda #>msg_savdisk
        sta PTR+1
        jsr printstr
sv_r:   lda $dc00
        and #$1f
        cmp #$1f
        bne sv_r
        lda #0
        sta $c6
sv_w:   jsr getact
        cmp #6
        beq sv_c
        cmp #5
        bne sv_w
        jsr clearmsg
        clc
        rts
sv_c:   jsr clearmsg
        sec
        rts

showpic_cur:                 ; picture area was blanked by textonly: reload current room
        ldx ROOM
        jmp showpic

dosave:
        jsr savprompt
        bcs ds_back
        lda ROOM
        sta FLAGS+$ff
        lda #12
        ldx #<savname_w
        ldy #>savname_w
        jsr $ffbd
        lda #1
        ldx #8
        ldy #0
        jsr $ffba
        lda #<FLAGS
        sta PTR3
        lda #>FLAGS
        sta PTR3+1
        lda #PTR3
        ldx #<(FLAGS+$100)
        ldy #>(FLAGS+$100)
        jsr ksave
        bcs ds_err
        jsr $ffb7            ; READST
        and #$83
        bne ds_err
        jsr drivestat
        bcs ds_err
        lda #<msg_saved
        ldx #>msg_saved
        jmp ds_msg
ds_err: lda #<msg_saverr
        ldx #>msg_saverr
ds_msg: sta PTR
        stx PTR+1
        jsr waitmsg
ds_back:
        jmp showpic_cur

doload:
        jsr savprompt
        bcs ds_back
        lda #9
        ldx #<savname_r
        ldy #>savname_r
        jsr $ffbd
        lda #1
        ldx #8
        ldy #0
        jsr $ffba
        lda #0
        ldx #<CBUF
        ldy #>CBUF
        jsr kload
        bcs dl_err
        jsr $ffb7
        and #$83
        bne dl_err
        lda CBUF+$ff         ; sanity: room number < 154
        cmp #154
        bcs dl_err
        ldx #0
dl_c:   lda CBUF,x
        sta FLAGS,x
        inx
        bne dl_c
        lda #<msg_loaded
        sta PTR
        lda #>msg_loaded
        sta PTR+1
        jsr waitmsg
        lda FLAGS+$ff
        sta ROOM
        jmp enterroom
dl_err: lda #<msg_loaderr
        sta PTR
        lda #>msg_loaderr
        sta PTR+1
        jsr waitmsg
        jmp ds_back

waitmsg:                     ; print (PTR) in text-only mode and wait for a button
        jsr clearmsg
        jsr printstr
wm_r:   lda $dc00
        and #$1f
        cmp #$1f
        bne wm_r
        lda #0
        sta $c6
wm_w:   jsr getact
        cmp #5
        beq wm_d
        cmp #6
        bne wm_w
wm_d:   jsr clearmsg
        rts

; read drive error channel: C=0 if "0x" (ok)
drivestat:
        lda #0
        jsr $ffbd
        lda #15
        ldx #8
        ldy #15
        jsr $ffba
        jsr $ffc0            ; OPEN
        bcs dst_e
        ldx #15
        jsr $ffc6            ; CHKIN
        jsr $ffcf            ; CHRIN: first digit
        sta T1
dst_l:  jsr $ffb7
        bne dst_x
        jsr $ffcf
        cmp #$0d
        bne dst_l
dst_x:  jsr $ffcc            ; CLRCHN
        lda #15
        jsr $ffc3            ; CLOSE
        lda T1
        cmp #$30
        bne dst_e
        clc
        rts
dst_e:  sec
        rts

savname_w: .byte $40,$30,$3a,$54,$4f,$4d,$41,$54,$4f,$53,$41,$56   ; "@0:TOMATOSAV"
savname_r: .byte $54,$4f,$4d,$41,$54,$4f,$53,$41,$56               ; "TOMATOSAV"

; ---------------------------------------------------------------- inventory
showinv:
        jsr clearmsg
        lda #<msg_items
        sta PTR
        lda #>msg_items
        sta PTR+1
        jsr printstr
        lda #0
        sta T2
        lda #<invtab
        sta PTR2
        lda #>invtab
        sta PTR2+1
si_l:   ldy #0
        lda (PTR2),y
        cmp #$ff
        beq si_done
        sta T1
        iny
        lda (PTR2),y
        tay
        lda FLAGS,y
        beq si_next
        inc T2
        ldy T1
        lda noun_lo,y
        sta PTR
        lda noun_hi,y
        sta PTR+1
        jsr printstr
        lda #$20
        jsr putch
si_next:
        clc
        lda PTR2
        adc #2
        sta PTR2
        bcc si_l
        inc PTR2+1
        jmp si_l
si_done:
        lda T2
        bne si_ret
        lda #<msg_noitems
        sta PTR
        lda #>msg_noitems
        sta PTR+1
        jsr printstr
si_ret: rts

; ---------------------------------------------------------------- menu building
skipstr:
        ldy #0
ss_l:   lda (PTR),y
        inc PTR
        bne ss_n
        inc PTR+1
ss_n:   cmp #0
        bne ss_l
        rts

; PTR -> table of (id, string0) terminated by $ff ; X = start index ; returns X
tabmenu:
tm_l:   ldy #0
        lda (PTR),y
        cmp #$ff
        beq tm_done
        sta MENUID,x
        lda PTR
        clc
        adc #1
        sta MENULO,x
        lda PTR+1
        adc #0
        sta MENUHI,x
        inx
        inc PTR
        bne tm_a
        inc PTR+1
tm_a:   jsr skipstr
        jmp tm_l
tm_done:
        rts

; room verb table: (id, mode, listlo, listhi)... $ff
buildverbs:
        jsr loadroom
        ldy #0
        lda (RP),y
        sta PTR
        iny
        lda (RP),y
        sta PTR+1
        ldx #0
bv_l:   ldy #0
        lda (PTR),y
        cmp #$ff
        beq bv_done
        ldy #1               ; mode 1 (noun list only): hide the verb when no noun of it is visible
        lda (PTR),y
        cmp #1
        bne bv_add
        iny
        lda (PTR),y
        sta PTR2
        iny
        lda (PTR),y
        sta PTR2+1
        ldy #0
bv_c:   lda (PTR2),y
        cmp #$ff
        beq bv_next
        iny
        lda (PTR2),y
        iny
        cmp #$ff
        beq bv_add
        sty T3
        tay
        lda FLAGS,y
        bne bv_add
        ldy T3
        jmp bv_c
bv_add: ldy #0
        lda (PTR),y
        sta MENUID,x
        tay
        lda vname_lo,y
        sta MENULO,x
        lda vname_hi,y
        sta MENUHI,x
        inx
bv_next:
        clc
        lda PTR
        adc #4
        sta PTR
        bcc bv_l
        inc PTR+1
        jmp bv_l
bv_done:
        lda #V_ITEMS
        sta MENUID,x
        lda #<vname_items
        sta MENULO,x
        lda #>vname_items
        sta MENUHI,x
        inx
        lda #V_SYS
        sta MENUID,x
        lda #<vname_sys
        sta MENULO,x
        lda #>vname_sys
        sta MENUHI,x
        inx
        stx NENT
        rts

; find verb entry VERB in room verb table -> MODE, LISTP (PTR2)
findverb:
        jsr loadroom
        ldy #0
        lda (RP),y
        sta PTR
        iny
        lda (RP),y
        sta PTR+1
fv_l:   ldy #0
        lda (PTR),y
        cmp VERB
        beq fv_hit
        clc
        lda PTR
        adc #4
        sta PTR
        bcc fv_l
        inc PTR+1
        jmp fv_l
fv_hit: ldy #1
        lda (PTR),y
        sta MODE
        iny
        lda (PTR),y
        sta LISTP
        iny
        lda (PTR),y
        sta LISTP+1
        rts

; PTR -> list of (noun id, flag) terminated by $ff ; adds entries whose flag is set ($ff = always)
addnouns:
anl_l:  ldy #0
        lda (PTR),y
        cmp #$ff
        beq anl_done
        sta T1
        iny
        lda (PTR),y
        cmp #$ff
        beq anl_ok
        tay
        lda FLAGS,y
        beq anl_next
anl_ok: cpx #28
        bcs anl_next
        stx T2               ; skip a noun that is already in the menu
        ldy #0
anl_d:  cpy T2
        beq anl_new
        lda MENUID,y
        cmp T1
        beq anl_next
        iny
        bne anl_d
anl_new:
        ldy T1
        tya
        sta MENUID,x
        lda noun_lo,y
        sta MENULO,x
        lda noun_hi,y
        sta MENUHI,x
        inx
anl_next:
        clc
        lda PTR
        adc #2
        sta PTR
        bcc anl_l
        inc PTR+1
        jmp anl_l
anl_done:
        rts

addinv: lda #<invtab
        sta PTR
        lda #>invtab
        sta PTR+1
        jmp addnouns

backent:
        lda #$fe
        sta MENUID,x
        lda #<name_back
        sta MENULO,x
        lda #>name_back
        sta MENUHI,x
        inx
        stx NENT
        rts

buildinv:
        ldx #0
        jsr addinv
        jmp backent

buildnouns:
        ldx #0
        lda LISTP
        sta PTR
        lda LISTP+1
        sta PTR+1
        lda MODE
        cmp #3
        beq bn_dir
        jsr addnouns
        lda MODE
        cmp #2
        bne bn_back
        jsr addinv
        jmp bn_back
bn_dir: ldy #0
        lda (PTR),y
        cmp #$ff
        beq bn_back
        sta MENUID,x
        tay
        lda dname_lo,y
        sta MENULO,x
        lda dname_hi,y
        sta MENUHI,x
        inx
        inc PTR
        bne bn_dir
        inc PTR+1
        jmp bn_dir
bn_back:
        jmp backent

; ---------------------------------------------------------------- menu display / input
namelen:                     ; X = entry -> A = length (clobbers PTR,Y)
        lda MENULO,x
        sta PTR
        lda MENUHI,x
        sta PTR+1
        ldy #0
nl_l:   lda (PTR),y
        beq nl_d
        iny
        jmp nl_l
nl_d:   tya
        rts

calcvis:                     ; from FIRST: sets LAST = last entry that fits in columns 1..38
        lda FIRST
        sta LAST
        sta T2
        lda #1
        sta T1
cv_l:   lda T2
        cmp NENT
        bcs cv_done
        tax
        jsr namelen
        clc
        adc #2
        adc T1
        cmp #40
        bcs cv_done
        sta T1
        lda T2
        sta LAST
        inc T2
        jmp cv_l
cv_done:
        rts

drawmenu:
        lda CURX             ; keep the message cursor (the menu row uses CURX/CURY too)
        pha
        lda CURY
        pha
        lda #$20
        ldx #39
dm_c:   sta SCR+960,x
        dex
        bpl dm_c
        jsr calcvis
        lda #1
        sta CURX
        lda FIRST
        sta CNT
dm_e:   lda LAST
        cmp CNT
        bcc dm_end
        lda #24
        sta CURY
        jsr calcpos
        lda CNT
        cmp SEL
        beq dm_arrow
        lda #$20
        jmp dm_put
dm_arrow:
        lda #$7f
dm_put: ldy #0
        sta (SCRP),y
        inc CURX
        ldx CNT
        lda MENULO,x
        sta PTR
        lda MENUHI,x
        sta PTR+1
        jsr printstr
        inc CURX
        inc CNT
        jmp dm_e
dm_end: lda FIRST
        beq dm_nl
        lda #$3c             ; '<'
        sta SCR+960
dm_nl:  lda NENT
        sec
        sbc #1
        cmp LAST
        beq dm_nr
        lda #$3e             ; '>'
        sta SCR+999
dm_nr:  pla
        sta CURY
        pla
        sta CURX
        rts

domenuv:                     ; verb menu: start at the last chosen entry
        lda LASTV
        cmp NENT
        bcc dv1
        lda #0
dv1:    sta SEL
        lda #0
        sta FIRST
dv2:    jsr calcvis
        lda LAST
        cmp SEL
        bcs dv3
        inc FIRST
        jmp dv2
dv3:    jsr drawmenu
        jmp dm_loop
domenu:
        lda #0
domenu_a:                    ; A = entry selected first
        sta SEL
        lda #0
        sta FIRST
        jsr drawmenu
dm_loop:
        jsr getact
        cmp #5
        beq dm_ok
        cmp #6
        beq dm_cancel
        cmp #3
        beq dm_prev
        cmp #1
        beq dm_prev
        lda SEL              ; next
        clc
        adc #1
        cmp NENT
        bcs dm_loop
        sta SEL
        jmp dm_adj
dm_prev:
        lda SEL
        beq dm_loop
        dec SEL
dm_adj: lda SEL
        cmp FIRST
        bcs dm_chk
        sta FIRST
dm_chk: jsr calcvis
        lda LAST
        cmp SEL
        bcs dm_redraw
        inc FIRST
        jmp dm_chk
dm_redraw:
        jsr drawmenu
        jmp dm_loop
dm_ok:  ldx SEL
        lda MENUID,x
        clc
        rts
dm_cancel:
        sec
        rts

; returns A: 1 up, 2 down, 3 left, 4 right, 5 ok, 6 cancel (joystick port 2 or keyboard)
getact:
ga_loop:
        lda $dc00
        and #$1f
        cmp #$1f
        bne ga_joy
        jsr $ffe4
        cmp #0
        beq ga_loop
        cmp #$91
        beq ga_up
        cmp #$11
        beq ga_dn
        cmp #$9d
        beq ga_lf
        cmp #$1d
        beq ga_rt
        cmp #$0d
        beq ga_ok
        cmp #$20
        beq ga_ok
        cmp #$5f
        beq ga_cn
        cmp #$58
        beq ga_cn
        jmp ga_loop
ga_up:  lda #1
        rts
ga_dn:  lda #2
        rts
ga_lf:  lda #3
        rts
ga_rt:  lda #4
        rts
ga_ok:  lda #5
        rts
ga_cn:  lda #6
        rts
ga_joy: sta GT
ga_rel: lda $dc00
        and #$1f
        cmp #$1f
        bne ga_rel
        lda GT
        and #$10
        bne ga_j1
        lda #5
        rts
ga_j1:  lda GT
        and #$01
        bne ga_j2
        lda #1
        rts
ga_j2:  lda GT
        and #$02
        bne ga_j3
        lda #2
        rts
ga_j3:  lda GT
        and #$04
        bne ga_j4
        lda #3
        rts
ga_j4:  lda #4
        rts

; ---------------------------------------------------------------- text output
calcpos:
        ldx CURY
        lda rowlo,x
        clc
        adc CURX
        sta SCRP
        lda rowhi,x
        adc #0
        sta SCRP+1
        rts

putch:  cmp #$0d
        bne pc_norm
        jmp newline
pc_norm:
        pha
        jsr calcpos
        pla
        ldy #0
        sta (SCRP),y
        inc CURX
        lda CURX
        cmp #40
        bcc pc_ret
        jmp newline
pc_ret: rts

newline:
        lda #0
        sta CURX
        inc CURY
        lda CURY
        cmp #24
        bcc nl_ret
        jsr pagewait
nl_ret: rts

pagewait:
        lda #$1f
        sta SCR+23*40+39
        jsr getact
        jsr clearmsg
        rts

printstr:                    ; with WRAPON (English build): word wrap, no space at a line start
        lda #1
        sta ps_ws
ps_l:   ldy #0
        lda (PTR),y
        beq ps_done
        ldx #WRAPON
        beq ps_put
        cmp #$20
        bne ps_c
        sta ps_ws            ; space: the next character starts a word
        ldx CURX
        beq ps_nx            ; drop a space at the start of a line
        bne ps_put
ps_c:   cmp #$0d
        bne ps_c2
        sta ps_ws
        bne ps_put
ps_c2:  ldx ps_ws
        beq ps_put
        ldx #0
        stx ps_ws
        iny                  ; measure the word
ps_m:   lda (PTR),y
        beq ps_me
        cmp #$20
        beq ps_me
        cmp #$0d
        beq ps_me
        iny
        cpy #40
        bcc ps_m
ps_me:  tya
        clc
        adc CURX
        cmp #40              ; keep column 39 free (the page-wait mark goes there)
        bcc ps_fit
        lda CURX
        beq ps_fit
        jsr newline
ps_fit: ldy #0
        lda (PTR),y
ps_put: jsr putch
ps_nx:  inc PTR
        bne ps_l
        inc PTR+1
        jmp ps_l
ps_done:
        rts
ps_ws:  .byte 1

clrmenu:                     ; blank the command row (old choices must not stay visible)
        lda #$20
        ldx #39
cmn_l:  sta SCR+960,x
        dex
        bpl cmn_l
        rts

clearmsg:
        lda #$20
        ldx #119
cm_l:   sta SCR+840,x
        dex
        bpl cm_l
        lda #0
        sta CURX
        lda #21
        sta CURY
        rts

; ---------------------------------------------------------------- picture / raster
; picture data: bg(1) + bitmap(6720) + screen(840) + colour(840)
showpic:
        stx PICX
        lda #$2b             ; blank the picture area while loading/copying
        sta D011B
sp_try:
sp_load:
        jsr blanktop
        ldx PICX             ; build file name "Pnnn"
        lda #$52
        sta NAMEBUF
        txa
        ldx #0
sp_h:   cmp #100
        bcc sp_h2
        sbc #100
        inx
        bne sp_h
sp_h2:  pha
        txa
        ora #$30
        sta NAMEBUF+1
        pla
        ldx #0
sp_t:   cmp #10
        bcc sp_t2
        sbc #10
        inx
        bne sp_t
sp_t2:  ora #$30
        sta NAMEBUF+3
        txa
        ora #$30
        sta NAMEBUF+2
        lda #4
        ldx #<NAMEBUF
        ldy #>NAMEBUF
        jsr $ffbd
        lda #1
        ldx #8
        ldy #0
        jsr $ffba
        lda #0
        ldx #<CBUF
        ldy #>CBUF
        jsr kload
        bcs sp_err
        clc
        lda CBUF
        adc #<(CBUF+2)
        sta v_VP
        lda CBUF+1
        adc #>(CBUF+2)
        sta v_VP+1
        ldx PICX
        lda roomdisk,x
        sta CURDISK
        jsr render
        lda #$3b
        sta D011B
        rts

sp_err: jsr $ffe7            ; CLALL
        ldx PICX
        lda roomdisk,x
        sta WANT
        jsr askdisk
        jmp sp_try

askdisk:
        jsr textonly
        jsr clearmsg
        lda #<msg_disk1
        sta PTR
        lda #>msg_disk1
        sta PTR+1
        jsr printstr
        lda WANT
        ora #$30
        jsr putch
        lda #<msg_disk2
        sta PTR
        lda #>msg_disk2
        sta PTR+1
        jsr printstr
ad_r:   lda $dc00            ; wait for fire/key release
        and #$1f
        cmp #$1f
        bne ad_r
        lda #0
        sta $c6              ; flush keyboard buffer
ad_w:   jsr getact
        cmp #5
        bne ad_w
        jsr clearmsg
        lda WANT
        sta CURDISK
        lda #$2b
        sta D011B
        lda #$18
        sta M16
        sta M18
        rts

; whole screen as plain text (blank screen RAM / colour RAM), for prompts
textonly:
        lda #$1b
        sta D011B
        lda #$08
        sta M16
        lda #$12
        sta M18
        lda #0
        sta PICBG
        lda #$20
        ldx #0
to1:    sta SCR,x
        sta SCR+$100,x
        sta SCR+$200,x
        sta SCR+$300,x
        inx
        bne to1
        lda #1
        ldx #0
to2:    sta $d800,x
        sta $d900,x
        sta $da00,x
        sta $db00,x
        inx
        bne to2
menucol:                     ; command line (row 24) in yellow
        lda #7
        ldx #39
mc1:    sta $d800+960,x
        dex
        bpl mc1
        rts


; ---------------------------------------------------------------- title screen
title:  lda #0
        jsr mus_play
        jsr textonly
        lda #<msg_t1
        ldy #>msg_t1
        ldx #8
        lda #<msg_t1
        sta PTR
        sty PTR+1
        lda #6
        jsr tline
        lda #<msg_t2
        sta PTR
        lda #>msg_t2
        sta PTR+1
        ldx #11
        lda #9
        jsr tline
        lda #<msg_t3
        sta PTR
        lda #>msg_t3
        sta PTR+1
        ldx #18
        lda #7
        jsr tline
        lda #<msg_t4
        sta PTR
        lda #>msg_t4
        sta PTR+1
        ldx #23
        lda #3
        jsr tline
ti_r:   lda $dc00
        and #$1f
        cmp #$1f
        bne ti_r
        lda #0
        sta $c6
ti_w:   jsr getact
        cmp #5
        bne ti_w
        lda #$3b
        sta D011B
        lda #$18
        sta M16
        sta M18
        rts

tline:                       ; title line: X = row, A = column (centred instead when WRAPON)
        ldy #WRAPON
        beq tl_c
        ldy #0
tl_l:   lda (PTR),y
        beq tl_e
        iny
        bne tl_l
tl_e:   tya
        eor #$ff
        sec
        adc #40
        lsr
tl_c:   clc
        adc #<SCR
        sta PTR3
        lda #>SCR
        adc #0
        sta PTR3+1
tl_r:   dex
        bpl tl_a
        jmp putstr
tl_a:
        lda PTR3
        clc
        adc #40
        sta PTR3
        bcc tl_r
        inc PTR3+1
        bne tl_r

romfont:                     ; copy ROM glyphs (lower/upper-case set) over the ASCII range
        sei
        lda #$33
        sta $01              ; character ROM at $D000
        ldx #$20
rf_l:   txa                  ; ASCII -> screen code in the lower-case character set
        cmp #$40
        bcc rf_s             ; space .. ? : same code
        beq rf_at
        cmp #$5b
        bcc rf_s             ; A-Z: 65-90
        cmp #$61
        bcc rf_n             ; [ \ ] ^ _ ` : keep the Misaki glyphs
        cmp #$7b
        bcs rf_n
        sbc #$5f             ; a-z (carry clear): 1-26
        jmp rf_s
rf_at:  lda #0
rf_s:   sta MUSO             ; (free here: the music IRQ is not running yet)
        lda #0
        sta PTR+1
        lda MUSO
        asl
        rol PTR+1
        asl
        rol PTR+1
        asl
        rol PTR+1
        sta PTR
        lda PTR+1
        ora #$d8
        sta PTR+1
        txa
        sta PTR3
        lda #0
        sta PTR3+1
        lda PTR3
        asl
        rol PTR3+1
        asl
        rol PTR3+1
        asl
        rol PTR3+1
        sta PTR3
        lda PTR3+1
        ora #$48
        sta PTR3+1
        ldy #7               ; the top pixel row of the first text line is hidden by the raster split:
        lda (PTR),y          ; glyphs with an empty bottom row move down one dot (others already
        bne rf_c             ; leave the top row empty)
        ldy #6
rf_d:   lda (PTR),y
        iny
        sta (PTR3),y
        dey
        dey
        bpl rf_d
        lda #0
        tay
        sta (PTR3),y
        beq rf_n
rf_c:   lda (PTR),y
        sta (PTR3),y
        dey
        bpl rf_c
rf_n:   inx
        cpx #$7f
        bne rf_l
        lda #$36
        sta $01
        cli
        rts

putstr: ldy #0
ps1:    lda (PTR),y
        beq ps2
        sta (PTR3),y
        iny
        bne ps1
ps2:    rts


irqram: pha                  ; IRQ entry while KERNAL ROM is banked out
        txa
        pha
        tya
        pha
irq:    lda $d019
        and #1
        bne ras
        lda RAMMODE
        bne irq_cia
        jmp $ea31            ; CIA timer interrupt: normal KERNAL work (keyboard scan etc.)
irq_cia:
        lda $dc0d            ; acknowledge CIA, skip keyboard scan
irqexit:
        pla
        tay
        pla
        tax
        pla
        rti
ras:    lda #1
        sta $d019
        lda IRQPH
        bne ph1
        ldx #$12
        ldy #0
ph0:    lda $d012            ; wait until the text rows begin (line 219)
        cmp #219
        bcc ph0
        sty $d021            ; background black first (bitmap below the picture is empty)
        lda #$1b
        sta $d011            ; text mode
        stx $d018            ; screen $4400, charset $4800
        lda #$08
        sta $d016
        lda #1
        sta IRQPH
        lda #251
        sta $d012
        jmp irqexit
ph1:    inc FRAMES
        lda D011B
        sta $d011            ; bitmap mode
        lda M16
        sta $d016            ; multicolour (or text-only mode)
        lda M18
        sta $d018            ; screen $4400, bitmap $6000
        lda PICBG
        sta $d021
        lda #0
        sta IRQPH
        lda #217
        sta $d012
        jsr mus_tick
        jmp irqexit



; ---------------------------------------------------------------- music (SID, driven from the raster IRQ)
mus_on:   .byte $80          ; bit 7 = music enabled (volume > 0)
mus_lvl:  .byte 4            ; volume level 0 (off) .. 5
mvoltab:  .byte 0,3,6,9,12,15
mvlabs:   .word vname_v0,vname_v1,vname_v2,vname_v3,vname_v4,vname_v5
mus_cur:  .byte $ff          ; song playing / selected
mus_act:  .byte 0            ; 1 = playing
mus_hld:  .byte 0            ; 1 = paused (disk access)
mus_ntsc: .byte 0
mus_nc:   .byte 5
mus_spd:  .byte 6
mus_fc:   .byte 1
mus_fv:   .byte 0            ; fading: current master volume (0 = no fade)
mus_ff:   .byte 0            ; frames until the next fade step
mvlo:     .byte 0,0,0
mvhi:     .byte 0,0,0
mslo:     .byte 0,0,0
mshi:     .byte 0,0,0
mvtk:     .byte 0,0,0        ; ticks left of the current event (0 = voice ended)
mvln:     .byte 4,4,4
mvct:     .byte 0,0,0        ; waveform of the current instrument
msid:     .byte 0,7,14
mfqlo:    .byte 0,0,0,0,0,0,0,0,0,0,0,0
mfqhi:    .byte 0,0,0,0,0,0,0,0,0,0,0,0

mus_init:                    ; PAL/NTSC check (highest raster line), frequency table, SID volume
        sei
mi_1:   bit $d011
        bpl mi_1
        lda #0
        sta T1
mi_2:   lda $d012
        cmp T1
        bcc mi_3
        sta T1
mi_3:   bit $d011
        bmi mi_2
        ldx #11
        lda T1
        cmp #$20
        bcc mi_n
mi_p:   lda mfq_pal_lo,x
        sta mfqlo,x
        lda mfq_pal_hi,x
        sta mfqhi,x
        dex
        bpl mi_p
        bmi mi_v
mi_n:   lda #1
        sta mus_ntsc
mi_nl:  lda mfq_ntsc_lo,x
        sta mfqlo,x
        lda mfq_ntsc_hi,x
        sta mfqhi,x
        dex
        bpl mi_nl
mi_v:   ldx #$18
        lda #0
mi_c:   sta $d400,x
        dex
        bpl mi_c
        ldx mus_lvl
        lda mvoltab,x
        sta $d418
        cli
        rts

mus_room:                    ; A = song for the room: start it unless it is already selected
        cmp mus_cur
        bne mus_play
        rts

mus_play:                    ; A = song number
        sta mus_cur
        bit mus_on
        bmi mp_go
        rts
mp_go:  php
        sei
        sta T1
        asl
        asl
        asl
        sec
        sbc T1               ; *7
        tay
        ldx #0
mp_v:   lda msongs,y
        sta mvlo,x
        sta mslo,x
        iny
        lda msongs,y
        sta mvhi,x
        sta mshi,x
        iny
        lda #1
        sta mvtk,x
        lda #4
        sta mvln,x
        txa
        pha
        lda msid,x
        tax
        lda #0
        sta $d404,x
        pla
        tax
        inx
        cpx #3
        bne mp_v
        lda msongs,y
        sta mus_spd
        lda #0
        sta mus_fv
        ldy mus_lvl
        lda mvoltab,y
        sta $d418
        lda #1
        sta mus_fc
        sta mus_act
        plp
        rts

mus_stop:
        lda #0
        sta mus_act
mus_off:                     ; release all voices
        lda #0
        sta $d404
        sta $d40b
        sta $d412
        rts

mus_volmenu:                 ; System > ｵﾝﾘｮｳ: ｵﾌ 1 2 3 4 5
        ldx #0
        ldy #0
mv_b:   txa
        sta MENUID,x
        lda mvlabs,y
        sta MENULO,x
        lda mvlabs+1,y
        sta MENUHI,x
        iny
        iny
        inx
        cpx #6
        bne mv_b
        jsr backent
        lda mus_lvl
        jsr domenu_a
        bcs mv_r
        cmp #6
        bcs mv_r
        sta mus_lvl
        tax
        lda mvoltab,x
        sta $d418
        cpx #0
        bne mv_on
        lda #0
        sta mus_on
        jmp mus_stop
mv_on:  bit mus_on
        bmi mv_r             ; already playing: only the volume changes
        lda #$80
        sta mus_on
        ldx ROOM
        lda roommus,x
        jmp mus_play
mv_r:   rts

kload:  jsr mus_pause
        jsr $ffd5
        jmp mus_resume
ksave:  jsr mus_pause
        jsr $ffd8
mus_resume:
        php
        pha
        lda #0
        sta mus_hld
        pla
        plp
        rts
mus_pause:
        pha
        lda #1
        sta mus_hld
        jsr mus_off
        pla
        rts

mus_tick:                    ; once per frame from the raster IRQ
        lda mus_act
        beq mt_r
        lda mus_hld
        bne mt_r
        lda mus_ntsc
        beq mt_1
        dec mus_nc
        bpl mt_1
        lda #5
        sta mus_nc
mt_r:   rts
mt_1:   lda mus_fv
        beq mt_1b
        dec mus_ff
        bne mt_1b
        lda #10
        sta mus_ff
        dec mus_fv
        lda mus_fv
        sta $d418
        bne mt_1b
        sta mus_act          ; faded out: stop
        jmp mus_off
mt_1b:  dec mus_fc
        lda mus_fc
        cmp #2               ; two frames before a note ends: release it
        bne mt_2
        ldx #2
mt_g:   lda mvtk,x
        cmp #1
        bne mt_g2
        ldy msid,x
        lda mvct,x
        sta $d404,y
mt_g2:  dex
        bpl mt_g
        rts
mt_2:   lda mus_fc
        bne mt_r
        lda mus_spd
        sta mus_fc
        ldx #2
        lda #0
        sta MUSN               ; voices still running
mt_v:   lda mvtk,x
        beq mt_nx
        inc MUSN
        dec mvtk,x
        bne mt_nx
        jsr mus_ev
mt_nx:  dex
        bpl mt_v
        lda MUSN
        bne mt_r2
        sta mus_act
mt_r2:  rts

mus_ev:                      ; voice X: read events until a note or rest
        lda mvlo,x
        sta MUSP
        lda mvhi,x
        sta MUSP+1
me_l:   ldy #0
        lda (MUSP),y
        inc MUSP
        bne me_1
        inc MUSP+1
me_1:   cmp #$fd
        bne me_1b
        ldy mus_lvl          ; $fd: start fading out
        lda mvoltab,y
        sta mus_fv
        lda #10
        sta mus_ff
        jmp me_l
me_1b:  cmp #$fe
        bcc me_2
        bne me_end
        lda mslo,x           ; $fe: loop
        sta MUSP
        lda mshi,x
        sta MUSP+1
        jmp me_l
me_end: ldy msid,x           ; $ff: voice ends
        lda mvct,x
        sta $d404,y
        lda #0
        sta mvtk,x
        rts
me_2:   cmp #$c0
        bcc me_3
        and #$0f             ; instrument
        asl
        asl
        tay
        lda mins,y
        sta mvct,x
        txa
        pha
        lda msid,x
        tax
        lda mins+1,y
        sta $d405,x
        lda mins+2,y
        sta $d406,x
        lda mins+3,y
        sta $d403,x
        lda #0
        sta $d402,x
        pla
        tax
        jmp me_l
me_3:   cmp #$80
        bcc me_4
        and #$3f             ; length
        sta mvln,x
        jmp me_l
me_4:   pha
        lda mvln,x
        sta mvtk,x
        lda MUSP
        sta mvlo,x
        lda MUSP+1
        sta mvhi,x
        pla
        bne me_n
        ldy msid,x           ; rest
        lda mvct,x
        sta $d404,y
        rts
me_n:   sec                  ; note 1..84 -> octave / semitone
        sbc #1
        ldy #0
me_o:   cmp #12
        bcc me_o2
        sbc #12
        iny
        bne me_o
me_o2:  sty MUSO               ; octave 0..6
        tay
        lda mfqlo,y
        sta MUSP
        lda mfqhi,y
        sta MUSP+1
        lda #6
        sec
        sbc MUSO
        tay
        beq me_s2
me_s:   lsr MUSP+1
        ror MUSP
        dey
        bne me_s
me_s2:  ldy msid,x
        lda MUSP
        sta $d400,y
        lda MUSP+1
        sta $d401,y
        lda mvct,x
        sta $d404,y          ; gate off then on: retrigger
        ora #1
        sta $d404,y
        rts

;@MUSIC@
;@VECRENDER@
;@ROWTABLES2@
;@GAMEDATA@

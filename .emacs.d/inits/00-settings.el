;;emacs本体の設定

; ツールバーを消す
(tool-bar-mode 0)
; 対応する括弧を光らせる。
(show-paren-mode t)
; ウィンドウ内に収まらないときだけ括弧内も光らせる。
(setq show-paren-style 'mixed)
; 行番号を表示
(line-number-mode t)

;; 現在行を目立たせる
;(global-hl-line-mode)
; カーソルの位置が何文字目かを表示する
(column-number-mode t)
; カーソルの位置が何行目かを表示する
(line-number-mode t)

; 文字の色を設定します。
(add-to-list 'default-frame-alist '(foreground-color . "white"))
; 背景色を設定します。
(add-to-list 'default-frame-alist '(background-color . "black"))
; カーソルの色を設定します。
(add-to-list 'default-frame-alist '(cursor-color . "white"))
; マウスポインタの色を設定します。
(add-to-list 'default-frame-alist '(mouse-color . "white"))

;emacsのクリップボードをOSと共有
(setq x-select-enable-clipboard t)

;保存時に行末の空白を削除
(add-hook 'before-save-hook 'delete-trailing-whitespace)

; 保存時に末尾に改行を自動挿入
; TODO: ファイルの種類ごとに挿入するか否かを自動判定したい
(setq require-final-newline t)

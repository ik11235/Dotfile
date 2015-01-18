(require 'auto-complete)
(add-to-list 'ac-dictionary-directories "~/.emacs.d/dict")
(require 'auto-complete-config)
(ac-config-default)

(global-auto-complete-mode t)


;; 標準設定でないモードでも動くように
(add-to-list 'ac-modes 'enh-ruby-mode)
(add-to-list 'ac-modes 'yatex-mode)
(add-to-list 'ac-modes 'markdown-mode)

(custom-set-variables
  ;; custom-set-variables was added by Custom.
  ;; If you edit it by hand, you could mess it up, so be careful.
  ;; Your init file should contain only one such instance.
  ;; If there is more than one, they won't work right.
 '(inhibit-startup-screen t))
(custom-set-faces
  ;; custom-set-faces was added by Custom.
  ;; If you edit it by hand, you could mess it up, so be careful.
  ;; Your init file should contain only one such instance.
  ;; If there is more than one, they won't work right.
 )


;;; ロードパスの追加
(setq load-path (append
                 '("~/.emacs.d"
                   "~/.emacs.d/packages"
		   "~/.emacs.d/auto-install/"
		   "~/.emacs.d/yatex1.74/"
		   "~/.emacs.d/twittering-mode-2.0.0"
		   "~/.emacs.d/zencoding"
		   "~/.emacs.d/metaweblog.el"
		   "~/.emacs.d/org2blog"
		   )
                 load-path))
;;; キーバインド
(define-key global-map (kbd "C-h") 'delete-backward-char) ; 削除
(define-key global-map (kbd "M-?") 'help-for-help)        ; ヘルプ
(define-key global-map (kbd "C-z") 'undo)                 ; undo
(define-key global-map (kbd "C-c i") 'indent-region)      ; インデント
(define-key global-map (kbd "C-c C-i") 'hippie-expand)    ; 補完
(define-key global-map (kbd "C-c ;") 'comment-dwim)       ; コメントアウト
(define-key global-map (kbd "C-o") 'toggle-input-method)  ; 日本語入力切替
(define-key global-map (kbd "M-C-g") 'grep)               ; grep
(define-key global-map (kbd "C-[ M-C-g") 'goto-line)      ; 指定行へ移動

;;日本語をデフォルトに
;(set-language-environment "Japanese")


;;; メニューバーを消す
(menu-bar-mode nil)
;;; ツールバーを消す
(tool-bar-mode nil)
;;; 対応する括弧を光らせる。
(show-paren-mode t)
;;; ウィンドウ内に収まらないときだけ括弧内も光らせる。
(setq show-paren-style 'mixed)
;;; 行番号を表示
(line-number-mode t)


;;; 現在行を目立たせる
;(global-hl-line-mode)
;;; カーソルの位置が何文字目かを表示する
(column-number-mode t)
;;; カーソルの位置が何行目かを表示する
(line-number-mode t)
;;; カーソルの場所を保存する
(require 'saveplace)
(setq-default save-place t)

;; 文字の色を設定します。
(add-to-list 'default-frame-alist '(foreground-color . "white"))
;; 背景色を設定します。
(add-to-list 'default-frame-alist '(background-color . "black"))
;; カーソルの色を設定します。
(add-to-list 'default-frame-alist '(cursor-color . "white"))
;; マウスポインタの色を設定します。
(add-to-list 'default-frame-alist '(mouse-color . "white"))

(require 'auto-install)
(setq auto-install-directory "~/.emacs.d/auto-install/")
(auto-install-update-emacswiki-package-name t)
(auto-install-compatibility-setup) 


;;anything設定
;http://d.hatena.ne.jp/tomoya/20090423/1240456834
(require 'anything)
(define-key global-map (kbd "C-x b") 'anything) ; ありえるの人はこれらしい
(define-key global-map (kbd "C-x C-b") 'anything)    ; anything
;;設定は .emacs に書いた後、いちいち再起動せずとも、行末で C-x C-e で評価すればすぐに有効になります。評価については、Emacs設定講座 その3「scratch バッファと eval(評価)」。をどうぞ。

(require 'anything-config)
;;anything 最近開いたファイル表示設定
(require 'recentf)
(setq recentf-max-saved-items 100)
(recentf-mode 1)

;;flymake設定
;http://moimoitei.blogspot.com/2010/05/flymake-in-emacs.html
(require 'flymake)

;; GUIの警告は表示しない
(setq flymake-gui-warnings-enabled nil)

;; 全てのファイルで flymakeを有効化
(add-hook 'find-file-hook 'flymake-find-file-hook)

;; M-p/M-n で警告/エラー行の移動
(global-set-key "\M-p" 'flymake-goto-prev-error)
(global-set-key "\M-n" 'flymake-goto-next-error)

;; 警告エラー行の表示
(define-key global-map (kbd "\C-c e") 'flymake-display-err-menu-for-current-line)


(defun flymake-simple-generic-init (cmd &optional opts)
  (let* ((temp-file  (flymake-init-create-temp-buffer-copy
                      'flymake-create-temp-inplace))
         (local-file (file-relative-name
                      temp-file
                      (file-name-directory buffer-file-name))))
    (list cmd (append opts (list local-file)))))

;; Makefile が無くてもC/C++のチェック
(defun flymake-simple-make-or-generic-init (cmd &optional opts)
  (if (file-exists-p "Makefile")
      (flymake-simple-make-init)
    (flymake-simple-generic-init cmd opts)))

(defun flymake-c-init ()
 (flymake-simple-make-or-generic-init
 "gcc" '("-Wall" "-Wextra" "-pedantic" "-fsyntax-only")))
(defun flymake-c-golf-init ()
  (flymake-simple-make-or-generic-init
   "gcc" '("-w" "-pedantic" "-fsyntax-only")))

(defun flymake-cc-init ()
  (flymake-simple-make-or-generic-init
   "g++" '("-Wall" "-Wextra" "-pedantic" "-fsyntax-only")))

(push '("\\.[cC]\\'" flymake-c-init) flymake-allowed-file-name-masks)
(push '("\\\+.[cC]\\'" flymake-c-golf-init) flymake-allowed-file-name-masks)
(push '("\\.\\(?:cc\|cpp\|CC\|CPP\\)\\'" flymake-cc-init) flymake-allowed-file-name-masks)

;;yatex設定
(autoload 'yatex-mode "yatex" "Yet Another LaTeX mode" t)

;; YaTeX-mode
(setq auto-mode-alist
      (cons (cons "\\.tex$" 'yatex-mode) auto-mode-alist))
(setq dvi2-command "xdvi"
      tex-command "platex"
      dviprint-command-format "dvips %s | lpr"
      YaTeX-kanji-code 3)

;; YaHtml-mode
(setq auto-mode-alist
      (cons (cons "\\.html$" 'yahtml-mode) auto-mode-alist))
(autoload 'yahtml-mode "yahtml" "Yet Another HTML mode" t)
(setq yahtml-www-browser "netscape")

;; twittering-mode設定
(require 'twittering-mode)
;;twittering-mode proxy設定
(setq twittering-proxy-use t)
(setq twittering-proxy-server "127.0.0.1")
(setq twittering-proxy-port 8080)


;;auto-complete設定
(require 'auto-complete+)
'(global-auto-complete-mode t)

;;smart-compile
(require 'smart-compile+)


;org-modeレポート設定
;;jditaa設定
(setq org-ditaa-jar-path "~/.emacs.d/ditaa0_9/ditaa0_9.jar")

;;tex設定
(setq org-export-latex-date-format "%Y-%m-%d")
(setq org-export-latex-classes nil)
(add-to-list 'org-export-latex-classes
	     '("jarticle"
	       "\\documentclass[a4j]{jarticle}"
	       ("\\section{%s}" . "\\section*{%s}")
	       ("\\subsection{%s}" . "\\subsection*{%s}")
	       ("\\subsubsection{%s}" . "\\subsubsection*{%s}")
	       ("\\paragraph{%s}" . "\\paragraph*{%s}")
	       ("\\subparagraph{%s}" . "\\subparagraph*{%s}")
	       ))

;;picture設定
(add-hook 'picture-mode-hook 'picture-mode-init)
(autoload 'picture-mode-init "picture-init")

;;font設定
(set-default-font "-unknown-Takaoゴシック-normal-normal-normal-*-14-*-*-*-d-0-iso10646-1")
;;"-unknown-Takaoゴシック-normal-normal-normal-*-13-*-*-*-d-0-iso10646-1"       

;;zen-coding設定
(require 'zencoding-mode)
(add-hook 'yahtml-mode-hook 'zencoding-mode)
(add-hook 'html-mode-hook 'zencoding-mode)
(add-hook 'sgml-mode-hook 'zencoding-mode) ;; html-modeとかで自動出来にzencodingできるようにする
(define-key zencoding-mode-keymap "\C-i" 'zencoding-expand-line)

;yatex文字コード
(setq YaTeX-kanji-code nil)

;;mozc使用設定
(require 'mozc) ; or (load-file "/path/to/mozc.el")
(setq default-input-method "japanese-mozc")

;;org2blog設定

;; OS if version
(cond
((string-match "apple-darwin" system-configuration)
;ここに Mac の設定を書く
(define-key global-map [?¥] [?\\])  ;; ¥の代わりにバックスラッシュを入力する
)
((string-match "linux" system-configuration)
;ここに Linux での設定を書く
)
((string-match "mingw" system-configuration)
;ここに Windows での設定を書く
 )
);終了
(put 'narrow-to-region 'disabled nil)

;brew経由のemacsをGUIで起動した際、そのままではcommit messageを入力できないため、以下で対応
;;http://qiita.com/dtan4/items/658a8a7ca06aa8c2da4c
(set-variable 'magit-emacsclient-executable "/usr/local/bin/emacsclient")

;; Mac用フォント設定
;; http://tcnksm.sakura.ne.jp/blog/2012/04/02/emacs/
;; http://minus9d.hatenablog.com/entry/20131103/1383475472

;; 英語
(set-face-attribute 'default nil
		    :family "Menlo" ;; font
		    :height 140)    ;; font size
;; 日本語
(set-fontset-font
 nil 'japanese-jisx0208
 (font-spec :family "Hiragino Kaku Gothic ProN")) ;; font
;; 半角と全角の比を1:2にしたければ
(setq face-font-rescale-alist
      ;;        '((".*Hiragino_Mincho_pro.*" . 1.2)))
      '((".*Hiragino_Kaku_Gothic_ProN.*" . 1.2)))

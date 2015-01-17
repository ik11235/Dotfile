(require 'helm-config)
(helm-mode 1)

(define-key global-map (kbd "C-x b") 'helm-for-files)
(define-key global-map (kbd "C-x C-b") 'helm-for-files)

;http://d.hatena.ne.jp/a_bicky/20140104/1388822688
(define-key global-map (kbd "M-x")     'helm-M-x)
(define-key global-map (kbd "C-x C-f") 'helm-find-files)
(define-key global-map (kbd "C-x C-r") 'helm-recentf)
(define-key global-map (kbd "M-y")     'helm-show-kill-ring)
(define-key global-map (kbd "C-c i")   'helm-imenu)


;http://konbu13.hatenablog.com/entry/2014/01/15/223014
;http://fukuyama.co/nonexpansion
;; TABで補完
(define-key helm-c-read-file-map (kbd "TAB") 'helm-execute-persistent-action)
(define-key helm-find-files-map (kbd "TAB") 'helm-execute-persistent-action)
(define-key helm-read-file-map (kbd "TAB") 'helm-execute-persistent-action)


;buffやcommand選択時もTABで補完
;;http://aki2o.hatenablog.jp/entry/2014/02/23/anything/helm%E3%81%AE%E3%82%B3%E3%83%9E%E3%83%B3%E3%83%89%E5%8B%95%E4%BD%9C%E4%B8%AD%E3%81%AE%E3%82%AD%E3%83%BC%E3%83%90%E3%82%A4%E3%83%B3%E3%83%89%E3%82%92%E7%B0%A1%E5%8D%98%E3%81%AB%E8%A8%AD%E5%AE%9A
;(defvar ~helm-modify-keymap-required nil)
;(defvar ~helm-modify-keymap-finished nil)

;(defadvice helm-get-candidate-number (before mod-keymap activate)
;  (when (and ~helm-modify-keymap-required
;             (not ~helm-modify-keymap-finished))
;    
;    ;; ここにキーバインドを羅列
;    (define-key helm-map (kbd "TAB") 'helm-execute-persistent-action)
;    
;    (setq ~helm-modify-keymap-finished t)))
;
;(defadvice helm-read-pattern-maybe (around mod-keymap activate)
;  (let ((~helm-modify-keymap-required t)
;        (~helm-modify-keymap-finished nil))
;    ad-do-it))

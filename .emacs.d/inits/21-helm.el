(require 'helm-config)
(helm-mode 1)

(define-key global-map (kbd "C-x C-b") 'helm-for-files)

<<<<<<< HEAD
;http://d.hatena.ne.jp/a_bicky/20140104/1388822688
;http://d.hatena.ne.jp/a_bicky/20140104/1388822688
(define-key global-map (kbd "M-x")     'helm-M-x)
(define-key global-map (kbd "C-x C-f") 'helm-find-files)
(define-key global-map (kbd "C-x C-r") 'helm-recentf)
(define-key global-map (kbd "M-y")     'helm-show-kill-ring)
(define-key global-map (kbd "C-c i")   'helm-imenu)
(define-key global-map (kbd "C-x b")   'helm-buffers-list)

(define-key helm-map (kbd "C-h") 'delete-backward-char)
(define-key helm-find-files-map (kbd "C-h") 'delete-backward-char)


;http://konbu13.hatenablog.com/entry/2014/01/15/223014
;http://fukuyama.co/nonexpansion
;; TABで補完
(define-key helm-c-read-file-map (kbd "TAB") 'helm-execute-persistent-action)
(define-key helm-find-files-map (kbd "TAB") 'helm-execute-persistent-action)
(define-key helm-read-file-map (kbd "TAB") 'helm-execute-persistent-action)

(require 'helm-config)
(helm-mode 1)

(define-key global-map (kbd "C-x b") 'helm-for-files)
(define-key global-map (kbd "C-x C-b") 'helm-for-files)

;http://konbu13.hatenablog.com/entry/2014/01/15/223014
;; TABで補完
(define-key helm-read-file-map (kbd "<tab>") 'helm-execute-persistent-action)

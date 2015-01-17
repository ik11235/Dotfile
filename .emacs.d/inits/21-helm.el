(require 'helm-config)
(helm-mode 1)

(define-key global-map (kbd "C-x b") 'helm-for-files)
(define-key global-map (kbd "C-x C-b") 'helm-for-files)

(define-key helm-map (kbd "C-h") 'delete-backward-char)
(define-key helm-find-files-map (kbd "C-h") 'delete-backward-char)

;http://konbu13.hatenablog.com/entry/2014/01/15/223014
;http://fukuyama.co/nonexpansion
;; TABで補完
(define-key helm-c-read-file-map (kbd "TAB") 'helm-execute-persistent-action)

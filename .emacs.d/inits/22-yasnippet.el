(require 'yasnippet)
;yasnippetのインストールパスを取得
;;http://gongo.hatenablog.com/entry/2013/02/05/232633
;;http://yohshiy.blog.fc2.com/blog-entry-272.html
(setq yas-install-dir (concat (file-name-directory (find-library-name "yasnippet")) "snippets"))

(setq yas-snippet-dirs
      '("~/.emacs.d/snippets"
	yas-install-dir
	;;"~/.emacs.d/elpa/yasnippet-20141223.303/snippets/"
	))
(yas-global-mode 1)

;; 単語展開キーバインド (ver8.0から明記しないと機能しない)
(custom-set-variables '(yas-trigger-key "TAB"))

;; 既存スニペットを挿入する
(define-key yas-minor-mode-map (kbd "C-x y i") 'yas-insert-snippet)
;; 新規スニペットを作成するバッファを用意する
(define-key yas-minor-mode-map (kbd "C-x y n") 'yas-new-snippet)
;; 既存スニペットを閲覧・編集する
(define-key yas-minor-mode-map (kbd "C-x y v") 'yas-visit-snippet-file)


;; helm interface
;; http://d.hatena.ne.jp/syohex/20121207/1354885367
;; https://github.com/sugyan/dotfiles/blob/master/.emacs.d/inits/04-yasnippet.el
(eval-after-load "helm"
  '(progn
     (defun my-yas/prompt (prompt choices &optional display-fn)
       (let* ((names (loop for choice in choices
                           collect (or (and display-fn (funcall display-fn choice))
                                       choice)))
              (selected (helm-other-buffer
                         `(((name . ,(format "%s" prompt))
                            (candidates . names)
                            (action . (("Insert snippet" . (lambda (arg) arg))))))
                         "*helm yas/prompt*")))
         (if selected
             (let ((n (position selected names :test 'equal)))
               (nth n choices))
           (signal 'quit "user quit!"))))
     (custom-set-variables '(yas/prompt-functions '(my-yas/prompt)))))

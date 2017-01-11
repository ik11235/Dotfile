;; ~/.emacs.d/site-lisp 以下全部読み込み
(let ((default-directory (expand-file-name "~/.emacs.d/site-lisp")))
  (add-to-list 'load-path default-directory)
  (if (fboundp 'normal-top-level-add-subdirs-to-load-path)
      (normal-top-level-add-subdirs-to-load-path)))

;;init-loaderをpackage経由でインストールするため、packageの設定、必要パッケージの自動インストール
(require 'package)
(add-to-list 'package-archives '("melpa" . "http://melpa.milkbox.net/packages/"))
(add-to-list 'package-archives '("marmalade" . "http://marmalade-repo.org/packages/"))
(package-initialize)

(require 'cl)

(defvar installing-package-list
  '(
    ;; ここに使っているパッケージを書く。
    init-loader
    helm
    markdown-mode
    magit
    popwin
    google-translate
    yasnippet
    enh-ruby-mode
    ruby-block
    smartparens
    auto-complete
    php-mode
    flycheck
    helm-flycheck
    web-mode
    org2blog
    editorconfig
    scss-mode
    open-junk-file
    ))

(let ((not-installed (loop for x in installing-package-list
                            when (not (package-installed-p x))
                            collect x)))
  (when not-installed
    (package-refresh-contents)
    (dolist (pkg not-installed)
        (package-install pkg))))



(require 'init-loader)
(setq init-loader-show-log-after-init nil)
(init-loader-load "~/.emacs.d/inits")
(custom-set-variables
 ;; custom-set-variables was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 '(google-translate-default-source-language "ja")
 '(google-translate-default-target-language "en")
 '(package-selected-packages
   (quote
    (json-mode open-junk-file yasnippet yaml-mode web-mode ssh-config-mode smartparens slim-mode scss-mode ruby-block popwin php-mode php-completion org2blog markdown-mode init-loader highlight-indentation helm-gtags helm-flycheck helm-ag google-translate git-rebase-mode git-commit-mode enh-ruby-mode editorconfig-core editorconfig coffee-mode auto-complete)))
 '(yas-prompt-functions (quote (my-yas/prompt)))
 '(yas-trigger-key "TAB"))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )

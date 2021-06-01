;; ~/.emacs.d/site-lisp 以下全部読み込み
(let ((default-directory (expand-file-name "~/.emacs.d/site-lisp")))
  (add-to-list 'load-path default-directory)
  (if (fboundp 'normal-top-level-add-subdirs-to-load-path)
      (normal-top-level-add-subdirs-to-load-path)))

;;init-loaderをpackage経由でインストールするため、packageの設定、必要パッケージの自動インストール
(require 'package)
(add-to-list 'package-archives '("melpa" . "https://melpa.org/packages/") t)
(add-to-list 'package-archives '("org" . "https://orgmode.org/elpa/") t)
(add-to-list 'package-archives '("gnu" . "https://elpa.gnu.org/packages/") t)
(package-initialize)

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
    ;;ruby-block
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

;; installing-package-listからインストールしていないパッケージをインストール
(dolist (package installing-package-list)
  (unless (package-installed-p package)
    (package-install package)))


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
   '(nginx-mode js2-mode json-mode open-junk-file yasnippet yaml-mode web-mode ssh-config-mode smartparens slim-mode scss-mode ruby-block popwin php-mode php-completion org2blog markdown-mode init-loader highlight-indentation helm-gtags helm-flycheck helm-ag google-translate git-rebase-mode git-commit-mode enh-ruby-mode editorconfig-core editorconfig coffee-mode auto-complete))
 '(yas-prompt-functions '(my-yas/prompt))
 '(yas-trigger-key "TAB"))
(custom-set-faces
 ;; custom-set-faces was added by Custom.
 ;; If you edit it by hand, you could mess it up, so be careful.
 ;; Your init file should contain only one such instance.
 ;; If there is more than one, they won't work right.
 )

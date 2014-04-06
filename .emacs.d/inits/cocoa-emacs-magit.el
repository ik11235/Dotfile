;brew経由のemacsをGUIで起動した際、そのままではcommit messageを入力できないため、以下で対応
;;http://qiita.com/dtan4/items/658a8a7ca06aa8c2da4c
(set-variable 'magit-emacsclient-executable "/usr/local/Cellar/emacs/24.3/bin/emacsclient")

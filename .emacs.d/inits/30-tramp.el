;; .zshrc に tramp に不都合な設定があるらしい
;; bash なら問題は起こらない
;;http://qiita.com/catatsuy/items/f9fad90fa1352a4d3161
(eval-after-load 'tramp '(setenv "SHELL" "/bin/bash"))

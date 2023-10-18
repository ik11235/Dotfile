if ! test -e ~/.config/fish/functions/fisher.fish && ! set -q FISHER_INSTALL_PROCESS
  echo "fisher not exists."
  set -x FISHER_INSTALL_PROCESS 1
  curl -sL git.io/fisher | source && fisher install jorgebucaran/fisher
  fisher update
end

if ! test -e ~/.config/fish/functions/fisher.fish
  echo "fisher not exists."
  curl -sL git.io/fisher | source && fisher install jorgebucaran/fisher
  fisher update
end

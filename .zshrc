DOTHOME=${HOME}
source ${DOTHOME}/.zsh.d/zshrc_global
case "${OSTYPE}" in
# Mac(Unix)
darwin*)

    # ここに設定
	source ${DOTHOME}/.zsh.d/zshrc_mac
    ;;
# Linux
linux*)
	source ${DOTHOME}/.zsh.d/zshrc_linux
    ;;
esac

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/yuichi/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/yuichi/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/Users/yuichi/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/yuichi/google-cloud-sdk/completion.zsh.inc'; fi

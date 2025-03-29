#!/bin/bash -eu

# powerline
# clone
git clone https://github.com/powerline/fonts.git --depth=1
# install
cd fonts
./install.sh
# clean-up a bit
cd ..
rm -rf fonts

#UDEV Gothic
UDEV_GITHUB_API_URL="https://api.github.com/repos/yuru7/udev-gothic/releases/latest"

json=$(curl -s "$UDEV_GITHUB_API_URL")

# JSON の中から "browser_download_url" の行を抽出し、
# UDEVGothic_NF を含み、拡張子が .zip の URL を取り出す
download_url=$(echo "$json" | grep -o '"browser_download_url": "[^"]*"' | grep "UDEVGothic_NF" | grep "\.zip" | sed 's/.*"browser_download_url": "\(.*\)".*/\1/')

# URL が見つからなかった場合はエラーメッセージを表示して終了
if [ -z "$download_url" ]; then
    echo "UDEVGothic_NF の zip ファイルが見つかりませんでした。"
    exit 1
fi

tmp_dir=$(mktemp -d)
ZIP_PATH="/${tmp_dir}/UDEVGothic_NF.zip"
FONT_DIR="${HOME}/Library/Fonts/"

curl -L -o "${ZIP_PATH}" "$download_url"
unzip "${ZIP_PATH}" -d "${tmp_dir}"
find "$tmp_dir" -type f -name "*.ttf" -exec mv {} "${FONT_DIR}" \;
rm -rf "${tmp_dir}"

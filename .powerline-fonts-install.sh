#!/bin/bash -eu

if [ "$(uname)" != "Darwin" ]; then
  echo "Warning: .powerline-fonts-install.sh は現状macOSのみ対応。Linux対応は今後実装予定のためskipします。" >&2
  exit 0
fi

# powerline
# 既存 fonts ディレクトリが残っていれば削除（前回の実行中断に備える）
rm -rf fonts
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

json=$(curl -fsSL --retry 3 "$UDEV_GITHUB_API_URL")

# JSON の中から "browser_download_url" の行を抽出し、
# UDEVGothic_NF を含み、拡張子が .zip の URL を取り出す
download_url=$(echo "$json" | grep -o '"browser_download_url": "[^"]*"' | grep "UDEVGothic_NF" | grep "\.zip" | sed 's/.*"browser_download_url": "\(.*\)".*/\1/')

# URL が見つからなかった場合はエラーメッセージを表示して終了
if [ -z "$download_url" ]; then
    echo "UDEVGothic_NF の zip ファイルが見つかりませんでした。" >&2
    exit 1
fi

tmp_dir=$(mktemp -d)
ZIP_PATH="${tmp_dir}/UDEVGothic_NF.zip"
FONT_DIR="${HOME}/Library/Fonts/"

curl -fL --retry 3 -o "${ZIP_PATH}" "$download_url"
unzip -q "${ZIP_PATH}" -d "${tmp_dir}"
find "$tmp_dir" -type f -name "*.ttf" -exec mv {} "${FONT_DIR}" \;
rm -rf "${tmp_dir}"

# macOS-specific configuration (nix-darwin)
{ pkgs, ... }: {
  # Nix settings
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    # https://github.com/NixOS/nix/issues/7273
    auto-optimise-store = false;
  };

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # macOS system-level packages (shared across all users)
  environment.systemPackages = with pkgs; [
  ];

  # Enable touch ID for sudo
  security.pam.services.sudo_local.touchIdAuth = true;

  # Used for backwards compatibility
  system.stateVersion = 6;

  # nix-daemon is managed unconditionally by nix-darwin when nix.enable is on

  # Create /etc/zshrc that loads the nix-darwin environment
  programs.zsh.enable = true;
  programs.fish.enable = true;

  # ============================================================
  # macOS system defaults (migrated from .mac-init.sh)
  # ============================================================

  system.defaults = {
    # Finder
    finder = {
      AppleShowAllFiles = true;          # 不可視ファイルを表示
      AppleShowAllExtensions = true;     # 全ての拡張子を表示
    };

    # Dock / Mission Control
    dock = {
      wvous-bl-corner = 13;             # 左下ホットコーナー → 画面ロック
    };

    # Global domain
    NSGlobalDomain = {
      AppleShowAllExtensions = true;              # 全ての拡張子を表示
      NSAutomaticCapitalizationEnabled = false;   # 自動大文字の無効化
      AppleKeyboardUIMode = 3;                    # フルキーボードアクセスを有効
      KeyRepeat = 2;                              # キーのリピート速度
      InitialKeyRepeat = 15;                      # リピート入力認識までの時間
    };

    CustomUserPreferences = {
      # 左下ホットコーナーの修飾キーなし (nix-darwinにオプションがないため)
      "com.apple.dock" = {
        wvous-bl-modifier = 0;
      };
      # .DS_Store抑制
      # https://support.apple.com/ja-jp/HT208209
      "com.apple.desktopservices" = {
        DSDontWriteNetworkStores = true;   # ネットワークドライブ
        DSDontWriteUSBStores = true;       # USBストレージ
      };
      # Bluetooth音質向上: bitpoolの最低値を上げる
      # https://news.mynavi.jp/article/osxhack-63/
      "com.apple.BluetoothAudioAgent" = {
        "Apple Bitpool Min (editable)" = 40;
      };
      # TextEditのデフォルトをプレーンテキストに
      "com.apple.TextEdit" = {
        RichText = 0;
      };
    };
  };

  # sudo権限が必要な設定やlaunchctl操作はactivation scriptで実行
  # https://minatokobe.com/wp/os-x/mac/post-75289.html
  system.activationScripts.postActivation.text = ''
    # Bluetooth aptX/AAC有効化 (sudo必要)
    sudo defaults write bluetoothaudiod "Enable AptX codec" -bool true
    sudo defaults write bluetoothaudiod "Enable AAC codec" -bool true

    # 起動音を小さく (sudo必要)
    sudo nvram SystemAudioVolume=%01

    # Bluetoothイヤホン接続時にミュージックが起動しないように
    launchctl unload -w /System/Library/LaunchAgents/com.apple.rcd.plist 2>/dev/null || true
  '';
}

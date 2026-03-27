# Homebrew casks and Mac App Store apps managed via nix-darwin
# CLI tools are managed by Nix directly (see home.nix / common.nix)
{ ... }: {
  homebrew = {
    enable = true;

    # Remove formulae/casks not listed here on `darwin-rebuild switch`
    onActivation = {
      autoUpdate = true;
      cleanup = "zap";
      upgrade = true;
    };

    taps = [
      "homebrew/command-not-found"
      "ynqa/tap"
      "yt-dlp/taps"
    ];

    # CLI tools that are not available in nixpkgs or have issues on macOS via Nix
    # Most CLI tools are in home.nix via Nix packages
    brews = [
    ];

    # GUI applications (macOS only)
    casks = [
      "android-file-transfer"
      "android-platform-tools"
      "arc"
      "background-music"
      "battery"
      "calibre"
      "claude-code"
      "cursor"
      "discord"
      "docker"
      "emacs"
      "google-chrome"
      "google-chrome@canary"
      "google-cloud-sdk"
      "google-japanese-ime"
      "iterm2"
      "jetbrains-toolbox"
      "jordanbaird-ice"
      "keepassxc"
      "kindle"
      "loupedeck"
      "melonbooksviewer"
      "obs"
      "obsidian"
      "phantomjs"
      "raycast"
      "sequel-ace"
      "skitch"
      "slack@beta"
      "steam"
      "sync"
      "visual-studio-code@insiders"
      "vivaldi"
      "vlc"
      "warp"
      "windsurf"
      "xquartz"
    ];

    masApps = {
      "Windows App" = 1295203466;
    };
  };
}

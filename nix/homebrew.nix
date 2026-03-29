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
    ];

    # CLI tools not available in nixpkgs
    brews = [
      "codex"        # OpenAI Codex CLI (npm package, not in nixpkgs)
      "mas"          # Mac App Store CLI (macOS-only, not in nixpkgs)
      "mise"         # Version manager (nixpkgs build has cgo issues on some environments)
      "mysql"        # MySQL (nixpkgs only has mariadb)
      "pinentry-mac" # macOS-specific pinentry (not in nixpkgs)
      "redpen"       # Document proofreader (not in nixpkgs)
      "watchman"     # File watcher (nixpkgs build fails due to edencommon)
      "f3"           # USB flash drive tester
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
      "docker-desktop" # renamed from "docker"
      "emacs"
      "google-chrome"
      "google-chrome@canary"
      "gcloud-cli"    # renamed from "google-cloud-sdk"
      "google-japanese-ime"
      "iterm2"
      "jetbrains-toolbox"
      "jordanbaird-ice"
      "keepassxc"
      # "kindle"      # discontinued
      "loupedeck"
      # "melonbooksviewer" # no longer available in Homebrew
      "obs"
      "obsidian"
      # "phantomjs"   # discontinued
      "raycast"
      "sequel-ace"
      # "skitch"      # no longer available in Homebrew
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

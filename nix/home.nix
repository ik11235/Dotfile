# home-manager configuration (shared between macOS and Linux)
{ pkgs, lib, ... }: {
  home.stateVersion = "24.11";

  # Let home-manager manage itself
  programs.home-manager.enable = true;

  # Common packages (installed on both macOS and Linux)
  home.packages = with pkgs; [
    # Core utilities
    coreutils
    findutils
    curl
    gnumake
    tree
    jq
    p7zip
    nkf
    rename

    # Development tools
    git
    git-crypt
    gh
    ghq
    fzf
    peco
    tig
    tmux
    shellcheck
    protobuf
    jnv

    # Languages / runtimes
    openjdk
    scala
    sbt

    # Media / graphics
    ffmpeg
    imagemagick
    jpegoptim
    mozjpeg
    poppler-utils # xpdf replacement (pdftotext, pdfinfo, etc.)
    yt-dlp
    graphviz

    # Network
    aria2
    autossh
    nmap
    sshuttle
    inetutils # telnet
    wakeonlan

    # Other tools
    aspell
    fish
    gnupg
    fdupes
    mise
    minio-client # minio-mc
    watchman
    awscli2

    # macOS-only packages
  ] ++ lib.optionals pkgs.stdenv.isDarwin [
    cocoapods
    scrcpy
  ] ++ lib.optionals pkgs.stdenv.isLinux [
    f3  # USB flash drive tester (Linux-only practical use)
  ];
}

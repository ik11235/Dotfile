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
    # minimal set for Phase 0
  ];

  # Enable touch ID for sudo
  security.pam.services.sudo_local.touchIdAuth = true;

  # Used for backwards compatibility
  system.stateVersion = 6;

  # Auto-upgrade nix package and the daemon service
  services.nix-daemon.enable = true;

  # Create /etc/zshrc that loads the nix-darwin environment
  programs.zsh.enable = true;
  programs.fish.enable = true;
}

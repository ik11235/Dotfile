# home-manager configuration (shared between macOS and Linux)
{ pkgs, lib, ... }: {
  home.stateVersion = "24.11";

  # Let home-manager manage itself
  programs.home-manager.enable = true;

  # Common packages (installed on both macOS and Linux)
  home.packages = with pkgs; [
    # minimal set for Phase 0 - will be expanded in Phase 1
  ];
}

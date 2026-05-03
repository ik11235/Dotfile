{
  description = "ik11235 Dotfiles - minimal Nix bootstrap";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = ["aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux"];
    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
  in {
    packages = forAllSystems (pkgs: {
      default = pkgs.buildEnv {
        name = "dotfiles-cli";
        paths = with pkgs; [
          alejandra
          nil
        ];
      };
    });

    formatter = forAllSystems (pkgs: pkgs.alejandra);
  };
}

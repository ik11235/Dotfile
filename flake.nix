{
  description = "ik11235 Dotfiles - nix-darwin + home-manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

    nix-darwin = {
      url = "github:LnL7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ nixpkgs, nix-darwin, home-manager, ... }: let
    # User-specific config (gitignored). Copy user-config.json.example to create.
    userConfig = builtins.fromJSON (builtins.readFile ./nix/user-config.json);
    username = userConfig.username;
    hostname = userConfig.hostname;
    system = userConfig.system;
  in {
    darwinConfigurations.${hostname} = nix-darwin.lib.darwinSystem {
      inherit system;
      modules = [
        ./nix/darwin.nix
        ./nix/homebrew.nix
        home-manager.darwinModules.home-manager
        {
          home-manager.useGlobalPkgs = true;
          home-manager.useUserPackages = true;
          home-manager.users.${username} = import ./nix/home.nix;
        }
        {
          system.primaryUser = username;
          users.users.${username} = {
            name = username;
            home = "/Users/${username}";
          };
          networking.hostName = hostname;
        }
      ];
    };

    # Linux: standalone home-manager configuration
    homeConfigurations.linux = home-manager.lib.homeManagerConfiguration {
      pkgs = nixpkgs.legacyPackages.${userConfig.linuxSystem or "x86_64-linux"};
      modules = [
        ./nix/home.nix
        {
          home.username = userConfig.linuxUsername;
          home.homeDirectory = userConfig.linuxHomeDirectory;
        }
      ];
    };
  };
}

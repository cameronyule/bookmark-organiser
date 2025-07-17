{
  inputs = {
    # keep-sorted start block=yes
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
    };
    nixpkgs = {
      url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    };
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # keep-sorted end
  };

  outputs = inputs @ {
    # keep-sorted start
    flake-parts,
    nixpkgs,
    self,
    treefmt-nix,
    # keep-sorted end
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = [
        "x86_64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];
      perSystem = {pkgs, ...}: let
        treefmtEval = treefmt-nix.lib.evalModule pkgs ./internal/nix/treefmt.nix;
      in {
        formatter = treefmtEval.config.build.wrapper;
        checks.formatting = treefmtEval.config.build.check self;

        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            ollama
            (python313.withPackages (
              ps:
                with ps; [
                  uv
                ]
            ))
          ];
          shellHook = ''
            export UV_PYTHON_PREFERENCE="only-system"
            export UV_PYTHON=${pkgs.python313}
            uv venv --allow-existing .venv
            source .venv/bin/activate
            export TOKENIZERS_PARALLELISM=false
          '';
        };
      };
    };
}

{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default =
          with pkgs;
          mkShell {
            packages = [
              (python313.withPackages (
                ps: with ps; [
                  uv
                ]
              ))
            ];
            shellHook = ''
              export UV_PYTHON_PREFERENCE="only-system"
              export UV_PYTHON=${pkgs.python313}
              uv venv --allow-existing bookmark-processor/.venv
              source bookmark-processor/.venv/bin/activate
            '';
          };

        formatter = pkgs.nixfmt-rfc-style;
      }
    );
}

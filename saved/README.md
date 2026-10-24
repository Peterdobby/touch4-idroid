# saved/

Local generated files, downloads, dependencies, complete packages, logs, device-specific inputs, and frozen successful snapshots belong here. Git tracks this README and empty directory markers only.

- `build/`: builds, diagnostics, and host-check outputs.
- `releases/`: complete tool packages and read-only successful snapshots.
- `packages/`: runtime materials imported from an owned package.
- `state/`: installation logs, component caches, and audit records for the new entry point.
- `downloads/`, `sources/`, `research/`, `toolchain/`, `dependencies/`: upstream inputs and tools.
- `private/`: local configuration, tickets, and calibration.
- `history/`, `experiments/`: historical materials and failed versions.

The original working tree retains compatibility symlinks such as `build/` and `releases/`; their actual contents are stored here. Frozen successful versions remain unchanged. New experiments use new version directories.

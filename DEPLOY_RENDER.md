# Deploy notes for Render: building Rust-backed Python packages

Problem
-------
When deploying to Render, building packages like `pydantic-core` may require compiling Rust extensions via `maturin`. On some Render plans the default system cargo registry path (`/usr/local/cargo/...`) is read-only which causes errors like:

  Read-only file system (os error 30)

Fix options
-----------
1) Preferred — Use a Python runtime that already has prebuilt wheels (e.g. Python 3.11 or 3.12) in Render. If possible, change the service's Python version to `3.11.x` to avoid compiling Rust.

2) If you must build from source (Python 3.14 or missing wheels), set the build command in Render to run the included script which installs a user-local Rust toolchain and uses a writable cargo cache:

In Render Dashboard → Service → Settings → Build Command set to:

  bash backend/render-build.sh

This script will:
- set `CARGO_HOME` and `RUSTUP_HOME` to `$HOME` locations (writable)
- install `rustup` and the stable toolchain
- install `maturin` into the Python environment
- install Python dependencies from `requirements.txt`

Environment variables
---------------------
You can optionally set these in Render's Environment → Environment Variables to persist them in the build environment:

  CARGO_HOME = $HOME/.cargo
  RUSTUP_HOME = $HOME/.rustup

Notes and alternatives
----------------------
- If you can pin `pydantic-core` to a version that provides prebuilt manylinux wheels for your Python/runtime, add that pinned version to `requirements.txt` to avoid compilation.
- If your repo uses a `pip` step managed by Render, make sure to replace the default build command so the `render-build.sh` runs before `pip`'s install step, or include the `pip install -r requirements.txt` in the script as done above.

If you want, I can also:
- Create a Dockerfile to fully control the build environment (recommended for reproducible builds).
- Try switching your Render service to Python 3.11 and testing a deploy (I can provide the exact steps).

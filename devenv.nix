{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:

{
  packages = [ pkgs.git ];

  env = {
    LD_LIBRARY_PATH = lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib ];
    PLAYWRIGHT_BROWSERS_PATH = ".devenv/state/playwright-browsers";
  };

  languages = {
    javascript = {
      enable = true;
      npm.enable = true;
    };
    python = {
      enable = true;
      version = "3.13";
      directory = "./backend";
      venv = {
        enable = true;
        requirements = ./backend/requirements.txt;
      };
    };
  };

  enterShell = ''
    python --version
    npm --version
    echo "Browser: playwright install chromium"
    echo "Frontend: npm --prefix frontend ci"
    echo "Run API:  uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 5000"
    echo "Run UI:   npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173"
    echo "Run both: devenv tasks run dev:all"
  '';

  # https://devenv.sh/tasks/
  tasks = {
    "playwright:backend".exec = ".devenv/state/venv/bin/playwright install chromium";
    "dev:backend".exec =
      ".devenv/state/venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 5000";
    "lint:backend".exec = ".devenv/state/venv/bin/ruff check backend";
    "check:backend".exec = ''
      .devenv/state/venv/bin/ruff check backend
      .devenv/state/venv/bin/python -m compileall backend/app
    '';
    "install:frontend".exec = "npm --prefix frontend ci";
    "dev:frontend".exec = ''
      if [ ! -d frontend/node_modules ]; then
        devenv tasks run install:frontend
      fi

      npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173
    '';
    "check:frontend".exec = "npm --prefix frontend run build";
    "dev:all".exec = ''
      set -euo pipefail
      backend_pid=""
      frontend_pid=""

      cleanup() {
        trap - INT TERM EXIT

        for pid in "$frontend_pid" "$backend_pid"; do
          if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
          fi
        done

        wait 2>/dev/null || true
      }

      require_port_free() {
        port="$1"
        name="$2"

        if ss -H -ltn "sport = :$port" | read -r _; then
          echo "$name port $port is already in use. Stop the existing server before running dev:all." >&2
          ss -ltnp "sport = :$port" >&2 || true
          exit 1
        fi
      }

      trap cleanup INT TERM EXIT

      require_port_free 5000 "Backend"
      require_port_free 5173 "Frontend"

      setsid .devenv/state/venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 5000 &
      backend_pid=$!

      if [ ! -d frontend/node_modules ]; then
        devenv tasks run install:frontend
      fi

      setsid npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 &
      frontend_pid=$!

      wait -n "$backend_pid" "$frontend_pid"
    '';
  };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';
}

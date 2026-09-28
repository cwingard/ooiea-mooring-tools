"""Thin wrapper so `python append_deploy.py ...` works without -m.

See asset_deploy/cli.py for the actual implementation and full --help.
"""
from asset_deploy.cli import main

if __name__ == '__main__':
    main()

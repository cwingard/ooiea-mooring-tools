"""Per-platform deployment-row builders.

Each module exposes a `build_deployment(config, previous_version_number)`
function returning a DeploymentResult, plus the platform's REFDES_SENSOR
table and deploy_filename/config_filename conventions used by the CLI.
"""

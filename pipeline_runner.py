import argparse

from src.fairsea.analysis.scripts.main_pipeline import run_pipeline


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="fairsea_pipeline",
        description="Analyze, compare, and plot AIS trajectories",
        epilog=None,
    )
    parser.add_argument(
        "-c",
        "--config",
        default="pipeline_config.toml",
        help="Specify a configuration file",
    )

    args = parser.parse_args()
    run_pipeline(args.config, __name__)

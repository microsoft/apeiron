import sys
import os
import argparse
from streamlit.web.cli import main as streamlit_main
from .tracer import activate_tracer

def main():
    parser = argparse.ArgumentParser(description="An advanced tracer for Streamlit apps.")
    parser.add_argument("run", choices=['run'], help="Command to execute a streamlit script.")
    parser.add_argument("script_path", help="Path to the Streamlit python script.")
    parser.add_argument(
        "--log-dir",
        default="./.trace_logs",
        help="Directory to save the trace logs."
    )
    
    args, unknown_args = parser.parse_known_args()

    # Create the log directory if it doesn't exist
    os.makedirs(args.log_dir, exist_ok=True)

    # Activate the tracer, passing the directory
    activate_tracer(app_script_path=args.script_path, log_dir=args.log_dir)

    print(f"--- Starting Streamlit with advanced tracing ---")
    print(f"--- Trace logs will be saved to: {args.log_dir} ---")

    sys.argv = ["streamlit", "run", args.script_path] + unknown_args
    streamlit_main()